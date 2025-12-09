from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Dict, Tuple, Optional, List

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from branches.models import Branch, SiteGatewayConfig
from core.models import GatewayType

PrefillPayload = Tuple[Dict[str, Decimal | str], Dict[str, Decimal | str]]

GATEWAY_LABELS = {
    GatewayType.BANK: "Bank",
    GatewayType.CARD: "Credit Card",
    GatewayType.CRYPTO: "Crypto",
}

DEPOSIT_URL_NAMES = {
    GatewayType.BANK: "public_bank_deposit",
    GatewayType.CARD: "public_card_deposit",
    GatewayType.CRYPTO: "public_crypto_deposit",
}


def get_branch_or_404(public_code: str) -> Branch:
    return get_object_or_404(Branch, public_code=public_code, is_active=True)


def is_gateway_enabled(branch: Branch, gateway: str) -> bool:
    return SiteGatewayConfig.objects.filter(
        branch=branch,
        gateway=gateway,
        is_enabled=True,
    ).exists()


def get_gateway_label(gateway: str) -> str:
    return GATEWAY_LABELS.get(gateway, gateway)


def build_deposit_tabs(branch: Branch, selected_gateway: Optional[str] = None) -> List[Dict[str, str]]:
    tabs: List[Dict[str, str]] = []
    for gateway, url_name in DEPOSIT_URL_NAMES.items():
        if not is_gateway_enabled(branch, gateway):
            continue
        tab = {
            "code": gateway,
            "label": get_gateway_label(gateway),
            "url": reverse(url_name, args=[branch.public_code]),
            "is_active": bool(selected_gateway and gateway == selected_gateway),
        }
        tabs.append(tab)
    if tabs and not any(tab["is_active"] for tab in tabs):
        tabs[0]["is_active"] = True
    return tabs


def render_gateway_disabled(request: HttpRequest, branch: Branch, gateway: str) -> HttpResponse:
    context = {
        "branch": branch,
        "gateway": gateway,
        "gateway_label": get_gateway_label(gateway),
    }
    return render(request, "public/errors/gateway_disabled.html", context, status=403)


def ensure_gateway_enabled(
    request: HttpRequest, branch: Branch, gateway: str
) -> Optional[HttpResponse]:
    if is_gateway_enabled(branch, gateway):
        return None
    return render_gateway_disabled(request, branch, gateway)


def extract_prefill_params(request: HttpRequest) -> PrefillPayload:
    if request.method != "GET":
        return {}, {}

    initial: Dict[str, Decimal | str] = {}
    display: Dict[str, Decimal | str] = {}

    user_value = (
        request.GET.get("user")
        or request.GET.get("username")
        or request.GET.get("player")
        or request.GET.get("u")
    )
    if user_value:
        user_value = user_value.strip()
        if user_value:
            initial["player_id"] = user_value
            display["player_id"] = user_value

    amount_value = request.GET.get("amount") or request.GET.get("amt")
    if amount_value:
        try:
            amount_decimal = Decimal(amount_value)
            if amount_decimal > 0:
                initial["amount"] = amount_decimal
                display["amount"] = amount_decimal
        except (InvalidOperation, TypeError):
            pass

    return initial, display
