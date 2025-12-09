from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal, InvalidOperation

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from api.utils import api_error, api_success
from branches.models import Branch, SiteGatewayConfig
from card.models import CardPayment
from card.services import initiate_psp_checkout
from client_api.views import _select_available_bank
from core.constants import ALLOWED_CURRENCIES, DEFAULT_CURRENCY
from core.models import (
    DepositRequest,
    GatewayType,
    PaymentTransaction,
    WithdrawalRequest,
)
from crypto.models import CryptoPayment
from crypto.services import provision_crypto_address
from crypto.models import CryptoWalletConfig
from crypto.services import provision_crypto_address
from core.services.payment_transactions import (
    create_payment_transaction_for_deposit,
    create_payment_transaction_for_crypto,
    create_payment_transaction_for_withdraw,
)

logger = logging.getLogger(__name__)


def _parse_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _authenticate_branch(request, body):
    api_key = request.headers.get("X-API-KEY") or request.GET.get("api_key")
    if not api_key:
        return None, api_error("AUTH_MISSING_HEADERS", "Missing X-API-KEY header.", status=401)

    branch = Branch.objects.filter(api_key=api_key).first()
    if not branch:
        return None, api_error("AUTH_INVALID_API_KEY", "Invalid API key.", status=401)

    merchant_id = body.get("merchant_id")
    if merchant_id:
        branch_by_code = Branch.objects.filter(site_code=merchant_id).first()
        if not branch_by_code or not branch_by_code.is_active:
            return None, api_error("AUTH_MERCHANT_DISABLED", "Merchant disabled or not found.", status=403)
        branch = branch_by_code

    if not branch.is_active:
        return None, api_error("AUTH_MERCHANT_DISABLED", "Merchant disabled.", status=403)

    return branch, None


def _validate_gateway(branch, gateway_value):
    if not gateway_value:
        return None, api_error("GATEWAY_UNKNOWN", "gateway is required.", status=400)

    gateway_value = gateway_value.upper()
    if gateway_value not in GatewayType.values:
        return None, api_error("GATEWAY_UNKNOWN", f"Unsupported gateway '{gateway_value}'.", status=400)

    enabled = SiteGatewayConfig.objects.filter(
        branch=branch,
        gateway=gateway_value,
        is_enabled=True,
    ).exists()
    if not enabled:
        return None, api_error(
            "GATEWAY_DISABLED",
            "This gateway is not enabled for this merchant.",
            status=403,
        )

    return gateway_value, None


def _validate_amount(body):
    amount_raw = body.get("amount")
    try:
        amount = Decimal(str(amount_raw))
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, TypeError):
        return None, api_error("VALIDATION_INVALID_AMOUNT", "Invalid amount.", status=400)
    return amount, None


def _validate_currency(body):
    currency = (body.get("currency") or DEFAULT_CURRENCY).upper()
    if currency not in ALLOWED_CURRENCIES:
        return None, api_error(
            "VALIDATION_CURRENCY_INVALID",
            f"Unsupported currency '{currency}'.",
            status=400,
            data={"allowed": sorted(ALLOWED_CURRENCIES)},
        )
    return currency, None


def _build_transaction(branch, gateway, direction, amount, currency, user_name, card_payment=None, crypto_payment=None):
    ref_code = f"API-{gateway}-{uuid.uuid4().hex[:10]}"
    return PaymentTransaction.objects.create(
        branch=branch,
        gateway=gateway,
        direction=direction,
        amount=amount,
        currency=currency,
        user_name=user_name,
        status=PaymentTransaction.STATUS_PENDING,
        ref_code=ref_code,
        card_payment=card_payment,
        crypto_payment=crypto_payment,
    )


def _select_bank_account_or_error():
    bank_account = _select_available_bank()
    if not bank_account:
        return None, api_error(
            "GATEWAY_NOT_READY",
            "No active bank providers are available right now.",
            status=503,
        )
    return bank_account, None


@csrf_exempt
@require_POST
def init_deposit(request):
    body = _parse_json_body(request)
    if body is None:
        return api_error("VALIDATION_INVALID_REQUEST", "Invalid JSON body.", status=400)

    branch, error = _authenticate_branch(request, body)
    if error:
        return error

    gateway, error = _validate_gateway(branch, body.get("gateway"))
    if error:
        return error

    amount, error = _validate_amount(body)
    if error:
        return error

    currency, error = _validate_currency(body)
    if error:
        return error

    user_name = body.get("user_name")
    if not user_name:
        return api_error("VALIDATION_INVALID_USER", "user_name is required.", status=400)

    try:
        if gateway == GatewayType.BANK:
            bank_account, error = _select_bank_account_or_error()
            if error:
                return error

            provider = bank_account.provider
            payment_token = uuid.uuid4().hex
            external_user_id = body.get("external_user_id") or ""

            deposit = DepositRequest.objects.create(
                branch=branch,
                client=None,
                bank_account=bank_account,
                provider=provider,
                user_name=user_name,
                external_user_id=external_user_id,
                amount=amount,
                original_amount=amount,
                payment_token=payment_token,
                status="pending",
            )

            transaction = _build_transaction(
                branch,
                gateway,
                PaymentTransaction.DIRECTION_IN,
                amount,
                currency,
                user_name,
            )

            data = {
                "transaction_id": transaction.id,
                "gateway": gateway,
                "status": transaction.status,
                "amount": str(amount),
                "currency": currency,
                "payment_token": payment_token,
                "bank_account_id": bank_account.id,
                "deposit_id": deposit.id,
            }
            return api_success(data)

        if gateway == GatewayType.CARD:
            card_payment = CardPayment.objects.create(
                branch=branch,
                amount=amount,
                user_name=user_name,
                status=CardPayment.STATUS_PENDING,
            )
            payload = initiate_psp_checkout(card_payment)

            transaction = _build_transaction(
                branch,
                gateway,
                PaymentTransaction.DIRECTION_IN,
                amount,
                currency,
                user_name,
                card_payment=card_payment,
            )

            data = {
                "transaction_id": transaction.id,
                "gateway": gateway,
                "status": card_payment.status,
                "amount": str(amount),
                "currency": currency,
                "psp_redirect_url": payload.redirect_url,
                "card_payment_id": card_payment.id,
            }
            return api_success(data)

        if gateway == GatewayType.CRYPTO:
            coin = body.get("coin")
            network = body.get("network")
            if not coin or not network:
                return api_error(
                    "VALIDATION_INVALID_BANK",
                    "coin and network are required for crypto gateway.",
                    status=400,
                )

            provisioned = provision_crypto_address(coin.upper(), network.upper(), branch.public_code)
            crypto_payment = CryptoPayment.objects.create(
                branch=branch,
                coin=coin.upper(),
                network=network.upper(),
                amount=amount,
                address=provisioned.address,
                status=CryptoPayment.STATUS_PENDING,
            )

            transaction = _build_transaction(
                branch,
                gateway,
                PaymentTransaction.DIRECTION_IN,
                amount,
                currency,
                user_name,
                crypto_payment=crypto_payment,
            )

            data = {
                "transaction_id": transaction.id,
                "gateway": gateway,
                "status": transaction.status,
                "amount": str(amount),
                "currency": currency,
                "address": crypto_payment.address,
                "coin": crypto_payment.coin,
                "network": crypto_payment.network,
                "crypto_payment_id": crypto_payment.id,
            }
            return api_success(data)

        return api_error(
            "GATEWAY_UNKNOWN",
            f"Gateway '{gateway}' is not implemented.",
            status=400,
        )
    except Exception as exc:
        logger.exception("Deposit API failed: %s", exc)
        return api_error("INTERNAL_ERROR", "An unexpected error occurred.", status=500)


@csrf_exempt
@require_POST
def init_withdraw(request):
    body = _parse_json_body(request)
    if body is None:
        return api_error("VALIDATION_INVALID_REQUEST", "Invalid JSON body.", status=400)

    branch, error = _authenticate_branch(request, body)
    if error:
        return error

    gateway, error = _validate_gateway(branch, body.get("gateway"))
    if error:
        return error

    amount, error = _validate_amount(body)
    if error:
        return error

    currency, error = _validate_currency(body)
    if error:
        return error

    user_name = body.get("user_name")
    if not user_name:
        return api_error("VALIDATION_INVALID_USER", "user_name is required.", status=400)

    if gateway != GatewayType.BANK:
        return api_error(
            "GATEWAY_UNKNOWN",
            "Withdraw API currently supports BANK gateway only.",
            status=400,
        )

    iban = body.get("iban")
    if not iban:
        return api_error("VALIDATION_INVALID_IBAN", "iban is required.", status=400)

    try:
        bank_account, error = _select_bank_account_or_error()
        if error:
            return error

        provider = bank_account.provider

        withdrawal = WithdrawalRequest.objects.create(
            branch=branch,
            client=None,
            provider=provider,
            user_name=user_name,
            iban=iban,
            amount=amount,
            status="pending",
        )

        transaction = _build_transaction(
            branch,
            gateway,
            PaymentTransaction.DIRECTION_OUT,
            amount,
            currency,
            user_name,
        )

        data = {
            "transaction_id": transaction.id,
            "gateway": gateway,
            "status": transaction.status,
            "amount": str(amount),
            "currency": currency,
            "withdrawal_id": withdrawal.id,
        }
        return api_success(data)
    except Exception as exc:
        logger.exception("Withdraw API failed: %s", exc)
        return api_error("INTERNAL_ERROR", "An unexpected error occurred.", status=500)


@csrf_exempt
def deposit_create(request):
    """API v1: create deposit (BANK or CRYPTO). Supports idempotency via payment_token."""
    if request.method != "POST":
        return api_error("METHOD_NOT_ALLOWED", "POST required.", status=405)

    body = _parse_json_body(request)
    if body is None:
        return api_error("VALIDATION_INVALID_REQUEST", "Invalid JSON body.", status=400)

    # basic required fields
    required = ["external_user_id", "amount", "currency", "gateway"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return api_error("VALIDATION_REQUIRED_FIELDS", f"Missing: {', '.join(missing)}", status=400)

    branch, error = _authenticate_branch(request, body)
    if error:
        return error

    gateway, error = _validate_gateway(branch, body.get("gateway"))
    if error:
        return error

    # amount & currency
    amount, error = _validate_amount(body)
    if error:
        return error

    currency, error = _validate_currency(body)
    if error:
        return error

    payment_token = body.get("payment_token") or None

    # idempotency: if payment_token provided and exists, return existing
    if payment_token:
        # check bank deposit
        exists_dep = DepositRequest.objects.filter(payment_token=payment_token).first()
        if exists_dep:
            tx = create_payment_transaction_for_deposit(exists_dep)
            return api_success({
                "transaction_id": tx.id if tx else None,
                "payment_token": exists_dep.payment_token,
                "deposit_id": exists_dep.id,
                "status": exists_dep.status,
            })
        # check crypto payment
        exists_cr = CryptoPayment.objects.filter(payment_token=payment_token).first()
        if exists_cr:
            tx = create_payment_transaction_for_crypto(exists_cr)
            return api_success({
                "transaction_id": tx.id if tx else None,
                "payment_token": exists_cr.payment_token,
                "crypto_payment_id": exists_cr.id,
                "status": exists_cr.status,
            })

    user_name = body.get("user_name") or body.get("external_user_id")

    try:
        if gateway == GatewayType.BANK:
            bank_account, error = _select_bank_account_or_error()
            if error:
                return error

            provider = bank_account.provider

            deposit = DepositRequest.objects.create(
                branch=branch,
                client=None,
                bank_account=bank_account,
                provider=provider,
                user_name=user_name,
                external_user_id=body.get("external_user_id") or "",
                amount=amount,
                original_amount=amount,
                payment_token=payment_token or uuid.uuid4().hex,
                status="pending",
            )

            transaction = create_payment_transaction_for_deposit(deposit)

            data = {
                "transaction_id": transaction.id if transaction else None,
                "gateway": gateway,
                "status": deposit.status,
                "amount": str(amount),
                "currency": currency,
                "payment_token": deposit.payment_token,
                "bank_account_id": bank_account.id,
                "deposit_id": deposit.id,
            }
            return api_success(data)

        if gateway == GatewayType.CRYPTO:
            # coin/network optional; choose from active deposit-enabled wallets if not provided
            coin = (body.get("coin") or "").upper()
            network = (body.get("network") or "").upper()

            wallets = CryptoWalletConfig.objects.filter(branch=branch, is_active=True, is_deposit_enabled=True)
            if not wallets.exists():
                return api_error("GATEWAY_NOT_READY", "No active deposit wallets configured for this branch.", status=503)

            if not coin or not network:
                # pick first wallet
                w = wallets.order_by("coin", "network").first()
                coin = w.coin.upper()
                network = w.network.upper()
            else:
                w = wallets.filter(coin__iexact=coin, network__iexact=network).first()
                if not w:
                    return api_error("WALLET_NOT_FOUND", "Requested coin/network not available for branch.", status=404)

            # create crypto payment
            address = w.address or provision_crypto_address(coin, network, branch.public_code).address

            crypto_payment = CryptoPayment.objects.create(
                branch=branch,
                coin=coin,
                network=network,
                amount=amount,
                currency=currency,
                direction=CryptoPayment.DIRECTION_IN,
                user_name=user_name,
                address=address,
                payment_token=payment_token or uuid.uuid4().hex,
                status=CryptoPayment.STATUS_PENDING,
            )

            transaction = create_payment_transaction_for_crypto(crypto_payment)

            data = {
                "transaction_id": transaction.id if transaction else None,
                "gateway": gateway,
                "status": crypto_payment.status,
                "amount": str(amount),
                "currency": currency,
                "payment_token": crypto_payment.payment_token,
                "address": crypto_payment.address,
                "coin": crypto_payment.coin,
                "network": crypto_payment.network,
                "crypto_payment_id": crypto_payment.id,
            }
            return api_success(data)

        return api_error("GATEWAY_UNKNOWN", f"Gateway '{gateway}' is not implemented.", status=400)
    except Exception as exc:
        logger.exception("Deposit API create failed: %s", exc)
        return api_error("INTERNAL_ERROR", "An unexpected error occurred.", status=500)


@csrf_exempt
def withdraw_create(request):
    if request.method != "POST":
        return api_error("METHOD_NOT_ALLOWED", "POST required.", status=405)

    body = _parse_json_body(request)
    if body is None:
        return api_error("VALIDATION_INVALID_REQUEST", "Invalid JSON body.", status=400)

    required = ["external_user_id", "amount", "currency", "gateway"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return api_error("VALIDATION_REQUIRED_FIELDS", f"Missing: {', '.join(missing)}", status=400)

    branch, error = _authenticate_branch(request, body)
    if error:
        return error

    gateway, error = _validate_gateway(branch, body.get("gateway"))
    if error:
        return error

    if gateway != GatewayType.BANK:
        return api_error("GATEWAY_UNKNOWN", "Withdraw API currently supports BANK gateway only.", status=400)

    amount, error = _validate_amount(body)
    if error:
        return error

    currency, error = _validate_currency(body)
    if error:
        return error

    payment_token = body.get("payment_token") or None

    # idempotency
    if payment_token:
        exists_wdr = WithdrawalRequest.objects.filter(payment_token=payment_token).first()
        if exists_wdr:
            tx = create_payment_transaction_for_withdraw(exists_wdr)
            return api_success({
                "transaction_id": tx.id if tx else None,
                "payment_token": exists_wdr.payment_token,
                "withdrawal_id": exists_wdr.id,
                "status": exists_wdr.status,
            })

    user_name = body.get("user_name") or body.get("external_user_id")
    iban = body.get("iban")
    if not iban:
        return api_error("VALIDATION_INVALID_IBAN", "iban is required.", status=400)

    try:
        bank_account, error = _select_bank_account_or_error()
        if error:
            return error

        provider = bank_account.provider

        withdrawal = WithdrawalRequest.objects.create(
            branch=branch,
            client=None,
            provider=provider,
            user_name=user_name,
            iban=iban,
            amount=amount,
            payment_token=payment_token or uuid.uuid4().hex,
            status="pending",
        )

        transaction = create_payment_transaction_for_withdraw(withdrawal)

        data = {
            "transaction_id": transaction.id if transaction else None,
            "gateway": gateway,
            "status": withdrawal.status,
            "amount": str(amount),
            "currency": currency,
            "withdrawal_id": withdrawal.id,
            "payment_token": withdrawal.payment_token,
        }
        return api_success(data)
    except Exception as exc:
        logger.exception("Withdraw API create failed: %s", exc)
        return api_error("INTERNAL_ERROR", "An unexpected error occurred.", status=500)


def transaction_status(request):
    token = request.GET.get("payment_token")
    if not token:
        return api_error("VALIDATION_REQUIRED_FIELDS", "payment_token is required.", status=400)

    # search deposit, crypto payment, withdrawal
    dep = DepositRequest.objects.filter(payment_token=token).first()
    if dep:
        tx = PaymentTransaction.objects.filter(ref_code__icontains=dep.payment_token).first()
        return api_success({
            "type": "bank_deposit",
            "id": dep.id,
            "status": dep.status,
            "payment_token": dep.payment_token,
            "transaction_id": tx.id if tx else None,
            "provider_id": getattr(dep.bank_account, "provider_id", None),
        })

    cp = CryptoPayment.objects.filter(payment_token=token).first()
    if cp:
        tx = PaymentTransaction.objects.filter(crypto_payment=cp).first()
        return api_success({
            "type": "crypto",
            "id": cp.id,
            "status": cp.status,
            "payment_token": cp.payment_token,
            "transaction_id": tx.id if tx else None,
            "tx_hash": cp.tx_hash,
            "coin": cp.coin,
            "network": cp.network,
        })

    w = WithdrawalRequest.objects.filter(payment_token=token).first()
    if w:
        tx = PaymentTransaction.objects.filter(ref_code__icontains=w.payment_token).first()
        return api_success({
            "type": "withdrawal",
            "id": w.id,
            "status": w.status,
            "payment_token": w.payment_token,
            "transaction_id": tx.id if tx else None,
        })

    return api_error("NOT_FOUND", "No transaction found for this payment_token.", status=404)

