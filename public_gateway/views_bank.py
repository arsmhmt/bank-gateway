from __future__ import annotations

import secrets
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from client_api.forms import PublicDepositForm, PublicWithdrawForm
from client_api.security import check_public_rate_limits, log_public_request
from client_api.views import _select_available_bank
from core.models import DepositRequest, WithdrawalRequest, GatewayType
from core.services.payment_transactions import (
    create_payment_transaction_for_deposit,
    create_payment_transaction_for_withdraw,
)
from core.utils.limitor import (
    sync_bank_active_state,
    sync_provider_bank_states,
)

from .utils import (
    build_deposit_tabs,
    ensure_gateway_enabled,
    extract_prefill_params,
    get_branch_or_404,
)


def deposit_form(request: HttpRequest, code: str) -> HttpResponse:
    branch = get_branch_or_404(code)
    disabled_response = ensure_gateway_enabled(request, branch, GatewayType.BANK)
    if disabled_response:
        return disabled_response

    prefill_initial, prefill_display = extract_prefill_params(request)

    form_kwargs = {"branch": branch}
    if request.method != "POST" and prefill_initial:
        form_kwargs["initial"] = prefill_initial

    form = PublicDepositForm(request.POST or None, **form_kwargs)
    created_deposit: Optional[DepositRequest] = None
    selected_bank = None

    if request.method == "POST":
        rate_info = check_public_rate_limits(branch, request, "deposit")
        if rate_info.is_limited:
            form.add_error(
                None,
                "Çok sayıda deneme tespit edildi. Lütfen birkaç dakika sonra tekrar deneyin.",
            )
            log_public_request(
                branch,
                "deposit",
                request,
                was_limited=True,
                limit_scope=rate_info.scope or "",
                metadata={"retry_after": rate_info.retry_after},
            )
        elif form.is_valid():
            selected_bank = _select_available_bank()
            if not selected_bank:
                form.add_error(
                    None,
                    "Şu anda aktif banka hesabı bulunamadı. Lütfen daha sonra tekrar deneyin.",
                )
                log_public_request(
                    branch,
                    "deposit",
                    request,
                    metadata={"status": "no_bank_available"},
                )
            else:
                provider = selected_bank.provider
                amount = form.cleaned_data["amount"]
                payment_token = secrets.token_hex(16)
                created_deposit = DepositRequest.objects.create(
                    branch=branch,
                    client=None,
                    bank_account=selected_bank,
                    provider=provider,
                    user_name=form.cleaned_data["player_name"],
                    external_user_id=form.cleaned_data.get("player_id") or "",
                    amount=amount,
                    original_amount=amount,
                    payment_token=payment_token,
                    status="pending",
                )
                create_payment_transaction_for_deposit(created_deposit)
                sync_bank_active_state(selected_bank)
                sync_provider_bank_states(provider)
                log_public_request(
                    branch,
                    "deposit",
                    request,
                    metadata={
                        "status": "created",
                        "deposit_id": created_deposit.id,
                        "bank_account": selected_bank.id,
                    },
                )
                form = PublicDepositForm(branch=branch)
        else:
            log_public_request(
                branch,
                "deposit",
                request,
                metadata={"status": "invalid_form", "errors": list(form.errors.keys())},
            )

    context = {
        "branch": branch,
        "form": form,
        "created_deposit": created_deposit,
        "selected_bank": selected_bank or getattr(created_deposit, "bank_account", None),
        "prefill": prefill_display,
        "gateway_tabs": build_deposit_tabs(branch, GatewayType.BANK),
    }
    return render(request, "public/bank_deposit.html", context)


def withdraw_form(request: HttpRequest, code: str) -> HttpResponse:
    branch = get_branch_or_404(code)
    disabled_response = ensure_gateway_enabled(request, branch, GatewayType.BANK)
    if disabled_response:
        return disabled_response

    prefill_initial, prefill_display = extract_prefill_params(request)

    form_kwargs = {"branch": branch}
    if request.method != "POST" and prefill_initial:
        form_kwargs["initial"] = prefill_initial

    form = PublicWithdrawForm(request.POST or None, **form_kwargs)
    created_withdrawal: Optional[WithdrawalRequest] = None

    if request.method == "POST":
        rate_info = check_public_rate_limits(branch, request, "withdraw")
        if rate_info.is_limited:
            form.add_error(
                None,
                "Çok sayıda deneme tespit edildi. Lütfen birkaç dakika sonra tekrar deneyin.",
            )
            log_public_request(
                branch,
                "withdraw",
                request,
                was_limited=True,
                limit_scope=rate_info.scope or "",
                metadata={"retry_after": rate_info.retry_after},
            )
        elif form.is_valid():
            selected_bank = _select_available_bank()
            if not selected_bank:
                form.add_error(
                    None,
                    "Şu anda çekim taleplerini karşılayacak aktif sağlayıcı bulunamadı.",
                )
                log_public_request(
                    branch,
                    "withdraw",
                    request,
                    metadata={"status": "no_provider_available"},
                )
            else:
                provider = selected_bank.provider
                created_withdrawal = WithdrawalRequest.objects.create(
                    branch=branch,
                    client=None,
                    provider=provider,
                    user_name=form.cleaned_data["player_name"],
                    iban=form.cleaned_data["iban"],
                    amount=form.cleaned_data["amount"],
                    status="pending",
                )
                create_payment_transaction_for_withdraw(created_withdrawal)
                sync_provider_bank_states(provider)
                log_public_request(
                    branch,
                    "withdraw",
                    request,
                    metadata={
                        "status": "created",
                        "withdrawal_id": created_withdrawal.id,
                        "provider": provider.id,
                    },
                )
                form = PublicWithdrawForm(branch=branch)
        else:
            log_public_request(
                branch,
                "withdraw",
                request,
                metadata={"status": "invalid_form", "errors": list(form.errors.keys())},
            )

    context = {
        "branch": branch,
        "form": form,
        "created_withdrawal": created_withdrawal,
        "prefill": prefill_display,
    }
    return render(request, "client_api/public_branch_withdraw.html", context)
