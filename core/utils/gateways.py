from __future__ import annotations

from typing import Dict

from django.urls import reverse

from branches.models import SiteGatewayConfig
from core.models import GatewayType


def ensure_branch_gateway_configs(branch) -> None:
    """Ensure every gateway has a SiteGatewayConfig row for the branch."""

    for gateway, _ in GatewayType.choices:
        SiteGatewayConfig.objects.get_or_create(branch=branch, gateway=gateway)


def build_gateway_public_urls(branch) -> Dict[str, Dict[str, str]]:
    """Return deposit/withdraw URLs for each gateway using branch.public_code."""

    if not branch:
        return {}

    public_code = branch.public_code
    if not public_code:
        return {}

    return {
        GatewayType.BANK: {
            "label": GatewayType.BANK.label,
            "deposit": reverse("public_bank_deposit", args=[public_code]),
            "withdraw": reverse("public_bank_withdraw", args=[public_code]),
        },
        GatewayType.CARD: {
            "label": GatewayType.CARD.label,
            "deposit": reverse("public_card_deposit", args=[public_code]),
            "withdraw": reverse("public_card_withdraw", args=[public_code]),
        },
        GatewayType.CRYPTO: {
            "label": GatewayType.CRYPTO.label,
            "deposit": reverse("public_crypto_deposit", args=[public_code]),
            "withdraw": reverse("public_crypto_withdraw", args=[public_code]),
        },
    }


def get_branch_gateway_flags(branch) -> Dict[str, bool]:
    """Return a dict of gateway -> enabled bool for a branch."""

    flags = {gateway: False for gateway, _ in GatewayType.choices}
    if not branch:
        return flags

    ensure_branch_gateway_configs(branch)
    configs = branch.gateway_configs.values_list("gateway", "is_enabled")
    for gateway, is_enabled in configs:
        flags[gateway] = is_enabled
    return flags
