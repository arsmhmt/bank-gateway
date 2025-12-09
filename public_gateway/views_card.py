from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from card.forms import CardDepositForm
from card.models import CardPayment
from card.services import initiate_psp_checkout
from core.models import GatewayType

from .utils import (
    build_deposit_tabs,
    ensure_gateway_enabled,
    extract_prefill_params,
    get_branch_or_404,
    get_gateway_label,
)


def deposit_form(request: HttpRequest, code: str) -> HttpResponse:
    branch = get_branch_or_404(code)
    disabled_response = ensure_gateway_enabled(request, branch, GatewayType.CARD)
    if disabled_response:
        return disabled_response

    prefill_initial, prefill_display = extract_prefill_params(request)

    form_kwargs = {"branch": branch}
    if request.method != "POST" and prefill_initial:
        form_kwargs["initial"] = prefill_initial

    form = CardDepositForm(request.POST or None, **form_kwargs)
    card_payment = None
    psp_redirect_url = None

    if request.method == "POST" and form.is_valid():
        card_payment = CardPayment.objects.create(
            branch=branch,
            amount=form.cleaned_data["amount"],
            user_name=form.cleaned_data["player_name"],
            status=CardPayment.STATUS_PENDING,
        )
        payload = initiate_psp_checkout(card_payment)
        psp_redirect_url = payload.redirect_url
        form = CardDepositForm(branch=branch)  # reset form after success

    context = {
        "branch": branch,
        "form": form,
        "card_payment": card_payment,
        "psp_redirect_url": psp_redirect_url or getattr(card_payment, "psp_redirect_url", None),
        "prefill": prefill_display,
        "gateway_tabs": build_deposit_tabs(branch, GatewayType.CARD),
        "gateway_label": get_gateway_label(GatewayType.CARD),
    }
    return render(request, "public/card_deposit.html", context)


def withdraw_form(request: HttpRequest, code: str) -> HttpResponse:
    branch = get_branch_or_404(code)
    disabled_response = ensure_gateway_enabled(request, branch, GatewayType.CARD)
    if disabled_response:
        return disabled_response

    _, prefill_display = extract_prefill_params(request)
    context = {
        "branch": branch,
        "gateway": GatewayType.CARD,
        "gateway_label": get_gateway_label(GatewayType.CARD),
        "prefill": prefill_display,
    }
    return render(request, "public/gateway_placeholder.html", context)
