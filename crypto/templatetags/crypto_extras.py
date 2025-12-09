from django import template
from django.conf import settings

register = template.Library()


@register.filter
def crypto_explorer_url(payment):
    """
    Return a blockchain explorer URL for a given CryptoPayment, if possible.

    v1: only USDT on TRC20 is supported. Others return empty string.
    """
    if not payment or not getattr(payment, "tx_hash", None):
        return ""

    if getattr(payment, "coin", None) == "USDT" and getattr(payment, "network", None) == "TRC20":
        base = getattr(
            settings,
            "CRYPTO_TRON_EXPLORER_TX_URL",
            "https://tronscan.org/#/transaction/",
        )
        return f"{base}{payment.tx_hash}"

    return ""
