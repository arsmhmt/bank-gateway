from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import logging
from typing import Optional

import requests
from django.conf import settings

from core.models import GatewayType, PaymentTransaction
from core.services.payment_transactions import create_payment_transaction_for_crypto
from .models import CryptoPayment

logger = logging.getLogger(__name__)

USDT_TRC20_CONTRACT = getattr(
    settings,
    "CRYPTO_USDT_TRC20_CONTRACT",
    "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
)

MIN_CONFIRMATIONS = getattr(settings, "CRYPTO_TRC20_MIN_CONFIRMATIONS", 1)
AMOUNT_TOLERANCE = getattr(settings, "CRYPTO_TRC20_AMOUNT_TOLERANCE", "0.000001")


@dataclass
class ProvisionedAddress:
    address: str
    wallet_label: str


def _wallet_map():
    return getattr(settings, "CRYPTO_COLD_WALLETS", {})


def provision_crypto_address(coin: str, network: str, branch_code: str) -> ProvisionedAddress:
    wallets = _wallet_map()
    key = f"{coin}:{network}".upper()
    address = wallets.get(key) or f"{network}-{branch_code}-{coin}"
    return ProvisionedAddress(address=address, wallet_label=key)


def mark_crypto_confirmed(payment: CryptoPayment, tx_hash: str) -> CryptoPayment:
    payment.tx_hash = tx_hash
    payment.status = CryptoPayment.STATUS_APPROVED
    payment.save(update_fields=["tx_hash", "status", "updated_at"])
    create_payment_transaction_for_crypto(payment)
    return payment


def fail_crypto_payment(payment: CryptoPayment, reason: Optional[str] = None) -> CryptoPayment:
    payment.status = CryptoPayment.STATUS_FAILED
    payment.save(update_fields=["status", "updated_at"])
    create_payment_transaction_for_crypto(payment)
    return payment


def get_crypto_rate(coin: str, fiat_currency: str = "TRY") -> Optional[Decimal]:
    """
    Return the price for 1 unit of `coin` in `fiat_currency`.

    v1 scaffold: always returns None until a live rate provider is integrated.
    """
    # TODO: integrate with CoinGecko or internal pricing service and cache responses.
    return None


def _fetch_trc20_transfers(address: str) -> list[dict]:
    """
    Fetch TRC20 transfers to a given address from Tron explorer.

    v1: assumes a TronGrid-like API shape. Adjust URL/params when wiring a real provider.
    """

    base_url = getattr(settings, "CRYPTO_TRON_EXPLORER_API_URL", "").rstrip("/")
    api_key = getattr(settings, "CRYPTO_TRON_EXPLORER_API_KEY", "")

    if not base_url:
        logger.warning("CRYPTO_TRON_EXPLORER_API_URL not configured; skipping auto-confirm.")
        return []

    url = f"{base_url}/v1/accounts/{address}/transactions/trc20"

    headers = {}
    if api_key:
        headers["TRON-PRO-API-KEY"] = api_key

    try:
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.exception("Error calling Tron explorer for address %s: %s", address, exc)
        return []

    items = data.get("data") or data.get("transactions") or []
    return items


def check_deposit_confirmation(payment: CryptoPayment) -> bool:
    """
    Decide whether a given CryptoPayment (IN/deposit) is confirmed on-chain.

    v1 behavior:
    - Only USDT on TRC20 is considered for future auto-confirmation.
    - All other coins/networks always return False (manual confirmation).
    - NO real explorer integration yet; just structure and TODO.
    """

    if payment.direction != CryptoPayment.DIRECTION_IN:
        return False

    if payment.coin != "USDT" or payment.network != "TRC20":
        return False

    if not payment.address or payment.amount is None:
        return False

    transfers = _fetch_trc20_transfers(payment.address)
    if not transfers:
        return False

    try:
        expected = Decimal(str(payment.amount))
        tolerance = Decimal(str(AMOUNT_TOLERANCE))
    except (InvalidOperation, TypeError) as exc:
        logger.warning("Invalid amount/tolerance for payment %s: %s", payment.pk, exc)
        return False

    for tx in transfers:
        try:
            token_info = tx.get("token_info") or {}
            symbol = token_info.get("symbol")
            contract = token_info.get("address")

            to_address = tx.get("to")
            raw_value = tx.get("value")
            confirmed = tx.get("confirmed", True)
            confirmations = tx.get("confirmations")

            if confirmations is not None and confirmations < MIN_CONFIRMATIONS:
                continue

            if not confirmed:
                continue

            if symbol and symbol.upper() != "USDT":
                continue

            if contract and contract != USDT_TRC20_CONTRACT:
                continue

            if not to_address or to_address != payment.address:
                continue

            if raw_value is None:
                continue

            value_dec = Decimal(str(raw_value)) / Decimal("1000000")

            if abs(value_dec - expected) <= tolerance:
                logger.info(
                    "Auto-confirmed USDT/TRC20 payment %s for address %s",
                    payment.pk,
                    payment.address,
                )

                if not payment.tx_hash:
                    tx_id = tx.get("transaction_id") or tx.get("txid")
                    if tx_id:
                        payment.tx_hash = tx_id
                        payment.save(update_fields=["tx_hash"])

                return True

        except Exception as exc:
            logger.warning("Error parsing TRC20 transfer for payment %s: %s", payment.pk, exc)
            continue

    return False


def process_pending_deposits():
    """
    Iterate over pending IN crypto deposits and try to confirm them.
    v1: Only USDT/TRC20 has a future path to auto-confirmation.
    """

    pending_deposits = CryptoPayment.objects.filter(
        direction=CryptoPayment.DIRECTION_IN,
        status=CryptoPayment.STATUS_PENDING,
    )

    for payment in pending_deposits:
        if not check_deposit_confirmation(payment):
            continue

        payment.status = CryptoPayment.STATUS_APPROVED
        payment.save(update_fields=["status", "updated_at"])

        tx = PaymentTransaction.objects.filter(
            gateway=GatewayType.CRYPTO,
            crypto_payment=payment,
        ).first()
        if tx:
            tx.status = PaymentTransaction.STATUS_APPROVED
            tx.save(update_fields=["status", "updated_at"])
