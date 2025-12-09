
import secrets
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse

from core.models import WithdrawalRequest, DepositRequest, BankAccount, User
from core.utils.limitor import (
    bank_under_limit,
    provider_under_limit,
    sync_bank_active_state,
    sync_provider_bank_states,
)
from core.services.payment_transactions import (
    create_payment_transaction_for_deposit,
    create_payment_transaction_for_withdraw,
)
from branches.models import Branch
from .forms import PublicDepositForm, PublicWithdrawForm
from .security import check_public_rate_limits, log_public_request


def _extract_prefill_data(request):
    if request.method != "GET":
        return {}, {}

    initial = {}
    display = {}

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


def withdraw_request_form(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        iban = request.POST.get('iban')
        amount = request.POST.get('amount')
        bank = request.POST.get('bank')

        WithdrawalRequest.objects.create(
            client=None,
            provider=None,
            user_name=name,
            iban=iban,
            amount=amount,
            status="pending",
        )
        return render(request, 'client_api/withdraw_submitted.html', {"amount": amount})
    return render(request, 'client_api/withdraw_form.html')


def public_payment(request, site_code, token):
    """Public payment page used by external users via tokenized links.

    URL shape: /pay/<site_code>/<token>/
    - site_code: Branch.site_code (public unique id per site)
    - token: DepositRequest.payment_token (unique per request)
    """

    branch = get_object_or_404(Branch, site_code=site_code, is_active=True)
    deposit = get_object_or_404(DepositRequest, payment_token=token, branch=branch)

    now = timezone.now()
    is_expired = bool(deposit.expires_at and deposit.expires_at < now)
    is_pending = deposit.status == "pending"

    # Determine available bank accounts: either fixed one or provider's active ones
    if deposit.bank_account:
        bank_queryset = BankAccount.objects.filter(pk=deposit.bank_account_id)
    else:
        bank_queryset = BankAccount.objects.filter(provider=deposit.provider, is_active=True)

    if request.method == "POST" and is_pending and not is_expired:
        # Optional: capture sender full name from separate fields
        sender_first = (request.POST.get("sender_first_name") or "").strip()
        sender_last = (request.POST.get("sender_last_name") or "").strip()
        if sender_first or sender_last:
            sender_name = " ".join(part for part in [sender_first, sender_last] if part)
            deposit.user_name = sender_name

        # If bank was not pre-selected, allow the user to choose
        if not deposit.bank_account:
            bank_id = request.POST.get("bank_id")
            if bank_id:
                selected_bank = bank_queryset.filter(pk=bank_id).first()
                if selected_bank:
                    deposit.bank_account = selected_bank

        if deposit.submitted_at is None:
            deposit.submitted_at = now

        deposit.save(update_fields=[
            "user_name",
            "bank_account",
            "submitted_at",
        ])

        # Recompute flags for the updated deposit and show the same page with a status message
        is_expired = bool(deposit.expires_at and deposit.expires_at < now)
        is_pending = deposit.status == "pending"

    sender_first_prefill = ""
    sender_last_prefill = ""
    if deposit.user_name:
        name_parts = deposit.user_name.strip().split(" ", 1)
        sender_first_prefill = name_parts[0]
        if len(name_parts) > 1:
            sender_last_prefill = name_parts[1]

    context = {
        "branch": branch,
        "deposit": deposit,
        "banks": bank_queryset,
        "is_expired": is_expired,
        "is_pending": is_pending,
        "sender_first_name": sender_first_prefill,
        "sender_last_name": sender_last_prefill,
    }
    return render(request, "client_api/public_payment_page.html", context)


def public_payment_status(request, site_code, token):
    branch = get_object_or_404(Branch, site_code=site_code, is_active=True)
    deposit = get_object_or_404(DepositRequest, payment_token=token, branch=branch)

    is_pending = deposit.status == "pending"
    data = {
        "status": deposit.status,
        "status_display": deposit.get_status_display(),
        "is_pending": is_pending,
        "submitted": bool(deposit.submitted_at),
        "updated_at": deposit.processed_at.isoformat() if deposit.processed_at else None,
    }

    return JsonResponse(data)


def _eligible_bank_queryset():
    return (
        BankAccount.objects.filter(
            is_active=True,
            provider__is_active=True,
            provider__role=User.ROLE_PROVIDER,
        )
        .select_related("provider")
        .order_by("bank_name", "iban")
    )


def _select_available_bank():
    for bank in _eligible_bank_queryset():
        provider = bank.provider
        if provider is None:
            continue
        if not provider_under_limit(provider):
            continue
        if not bank_under_limit(bank):
            continue
        return bank
    return None


def public_branch_deposit(request, public_code):
    branch = get_object_or_404(Branch, public_code=public_code, is_active=True)
    prefill_initial, prefill_display = _extract_prefill_data(request)

    form_kwargs = {"branch": branch}
    if request.method != "POST" and prefill_initial:
        form_kwargs["initial"] = prefill_initial

    form = PublicDepositForm(request.POST or None, **form_kwargs)
    created_deposit = None
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
                form = PublicDepositForm(branch=branch)  # reset form after success
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
    }
    return render(request, "client_api/public_branch_deposit.html", context)


def public_branch_withdraw(request, public_code):
    branch = get_object_or_404(Branch, public_code=public_code, is_active=True)
    prefill_initial, prefill_display = _extract_prefill_data(request)

    form_kwargs = {"branch": branch}
    if request.method != "POST" and prefill_initial:
        form_kwargs["initial"] = prefill_initial

    form = PublicWithdrawForm(request.POST or None, **form_kwargs)
    created_withdrawal = None

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
