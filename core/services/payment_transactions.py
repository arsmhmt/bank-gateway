from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from django.utils.crypto import get_random_string

from core.constants import DEFAULT_CURRENCY
from core.models import (
    DepositRequest,
    GatewayType,
    PaymentTransaction,
    WithdrawalRequest,
)

if TYPE_CHECKING:
    from card.models import CardPayment
    from crypto.models import CryptoPayment


def _resolve_ref_code(prefix: str, fallback: Optional[str] = None) -> str:
    if fallback:
        return fallback[:64]
    return f"{prefix}{get_random_string(12)}"


def create_payment_transaction_for_deposit(deposit: DepositRequest) -> Optional[PaymentTransaction]:
    branch = getattr(deposit, "branch", None)
    if branch is None:
        return None

    ref_code = _resolve_ref_code(
        "BANKDEP-",
        getattr(deposit, "payment_token", None) or (deposit.id and f"BANKDEP-{deposit.id}"),
    )

    currency = deposit.currency or DEFAULT_CURRENCY

    defaults = {
        "branch": branch,
        "gateway": GatewayType.BANK,
        "direction": PaymentTransaction.DIRECTION_IN,
        "amount": deposit.amount,
        "currency": currency,
        "user_name": deposit.user_name,
        "status": deposit.status,
    }
    transaction, created = PaymentTransaction.objects.get_or_create(ref_code=ref_code, defaults=defaults)
    if not created:
        transaction.branch = branch
        transaction.gateway = GatewayType.BANK
        transaction.direction = PaymentTransaction.DIRECTION_IN
        transaction.amount = deposit.amount
        transaction.currency = currency
        transaction.user_name = deposit.user_name
        transaction.status = deposit.status
        transaction.save(update_fields=[
            "branch",
            "gateway",
            "direction",
            "amount",
            "currency",
            "user_name",
            "status",
            "updated_at",
        ])
    return transaction


def create_payment_transaction_for_card(card_payment: "CardPayment") -> Optional[PaymentTransaction]:
    branch = getattr(card_payment, "branch", None)
    if branch is None:
        return None

    ref_code = _resolve_ref_code("CARDEP-", card_payment.id and f"CARDEP-{card_payment.id}")

    currency = getattr(card_payment, "currency", None) or DEFAULT_CURRENCY

    defaults = {
        "branch": branch,
        "gateway": GatewayType.CARD,
        "direction": PaymentTransaction.DIRECTION_IN,
        "amount": card_payment.amount,
        "currency": currency,
        "user_name": card_payment.user_name,
        "status": card_payment.status,
        "card_payment": card_payment,
    }

    transaction, created = PaymentTransaction.objects.get_or_create(ref_code=ref_code, defaults=defaults)
    if not created:
        transaction.branch = branch
        transaction.gateway = GatewayType.CARD
        transaction.direction = PaymentTransaction.DIRECTION_IN
        transaction.amount = card_payment.amount
        transaction.currency = currency
        transaction.user_name = card_payment.user_name
        transaction.status = card_payment.status
        transaction.card_payment = card_payment
        transaction.save(update_fields=[
            "branch",
            "gateway",
            "direction",
            "amount",
            "currency",
            "user_name",
            "status",
            "card_payment",
            "updated_at",
        ])

    return transaction


def create_payment_transaction_for_crypto(crypto_payment: "CryptoPayment") -> Optional[PaymentTransaction]:
    branch = getattr(crypto_payment, "branch", None)
    if branch is None:
        return None

    ref_code = _resolve_ref_code("CRDEP-", crypto_payment.id and f"CRDEP-{crypto_payment.id}")

    currency = getattr(crypto_payment, "currency", None) or DEFAULT_CURRENCY

    defaults = {
        "branch": branch,
        "gateway": GatewayType.CRYPTO,
        "direction": PaymentTransaction.DIRECTION_IN,
        "amount": crypto_payment.amount,
        "currency": currency,
        "user_name": crypto_payment.address,
        "status": crypto_payment.status,
        "crypto_payment": crypto_payment,
    }

    transaction, created = PaymentTransaction.objects.get_or_create(ref_code=ref_code, defaults=defaults)
    if not created:
        transaction.branch = branch
        transaction.gateway = GatewayType.CRYPTO
        transaction.direction = PaymentTransaction.DIRECTION_IN
        transaction.amount = crypto_payment.amount
        transaction.currency = currency
        transaction.user_name = crypto_payment.address
        transaction.status = crypto_payment.status
        transaction.crypto_payment = crypto_payment
        transaction.save(update_fields=[
            "branch",
            "gateway",
            "direction",
            "amount",
            "currency",
            "user_name",
            "status",
            "crypto_payment",
            "updated_at",
        ])

    return transaction


def create_payment_transaction_for_withdraw(
    withdrawal: WithdrawalRequest,
) -> Optional[PaymentTransaction]:
    branch = getattr(withdrawal, "branch", None)
    if branch is None:
        return None

    ref_code = _resolve_ref_code(
        "BANKWDR-",
        getattr(withdrawal, "payment_token", None) or (withdrawal.id and f"BANKWDR-{withdrawal.id}"),
    )

    currency = withdrawal.currency or DEFAULT_CURRENCY

    defaults = {
        "branch": branch,
        "gateway": GatewayType.BANK,
        "direction": PaymentTransaction.DIRECTION_OUT,
        "amount": withdrawal.amount,
        "currency": currency,
        "user_name": withdrawal.user_name,
        "status": withdrawal.status,
    }
    transaction, created = PaymentTransaction.objects.get_or_create(ref_code=ref_code, defaults=defaults)
    if not created:
        transaction.branch = branch
        transaction.gateway = GatewayType.BANK
        transaction.direction = PaymentTransaction.DIRECTION_OUT
        transaction.amount = withdrawal.amount
        transaction.currency = currency
        transaction.user_name = withdrawal.user_name
        transaction.status = withdrawal.status
        transaction.save(update_fields=[
            "branch",
            "gateway",
            "direction",
            "amount",
            "currency",
            "user_name",
            "status",
            "updated_at",
        ])
    return transaction
