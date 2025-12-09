from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from card.models import CardPayment
from core.services.payment_transactions import create_payment_transaction_for_card


@dataclass
class PSPRedirect:
    redirect_url: str
    tx_id: str


def initiate_psp_checkout(card_payment: CardPayment) -> PSPRedirect:
    """
    Placeholder PSP initiation; in production replace with real PSP API call.
    """

    tx_id = f"PSP-{card_payment.id}"
    redirect_url = reverse(
        "card_psp_pending",
        kwargs={"payment_id": card_payment.id},
    )

    card_payment.psp_tx_id = tx_id
    card_payment.psp_redirect_url = redirect_url
    card_payment.status = CardPayment.STATUS_REQUIRES_ACTION
    card_payment.save(update_fields=["psp_tx_id", "psp_redirect_url", "status", "updated_at"])
    create_payment_transaction_for_card(card_payment)

    return PSPRedirect(redirect_url=redirect_url, tx_id=tx_id)


def finalize_psp_checkout(card_payment: CardPayment, success: bool) -> None:
    card_payment.status = CardPayment.STATUS_APPROVED if success else CardPayment.STATUS_FAILED
    card_payment.save(update_fields=["status", "updated_at"])
    create_payment_transaction_for_card(card_payment)
