
#
from core.decorators import provider_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from core.models import WithdrawalRequest, User, DepositRequest, BankAccount, ProviderCommission
from decimal import Decimal
from provider_panel.models import Provider
from core.utils.limitor import (
    sync_bank_active_state,
    sync_provider_bank_states,
)
from provider_panel.forms import BankAccountForm
from django.utils.decorators import method_decorator
from django.contrib.auth import authenticate, login as auth_login, update_session_auth_hash, logout
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
from django.utils.dateparse import parse_date
from django.contrib.auth.forms import PasswordChangeForm

# ...existing code...

@login_required
@provider_required
def add_bank_account(request):
    """Create a new bank account using the localized HTML form (bank_accounts.html)."""
    if request.method == "POST":
        # Manual fields from template
        bank_name = request.POST.get("bank_name")
        account_holder = request.POST.get("account_holder")
        iban = request.POST.get("iban")
        limit = request.POST.get("limit")

        account_limit = limit or None

        bank = BankAccount.objects.create(
            provider=request.user,
            bank_name=bank_name,
            account_holder=account_holder,
            iban=iban,
            account_limit=account_limit,
        )
        sync_bank_active_state(bank)
        sync_provider_bank_states(request.user)
        messages.success(request, "Banka hesabı başarıyla eklendi.")
        return redirect("provider_panel:list_bank_accounts")

    # GET: render localized form
    return render(request, "provider_panel/bank_accounts.html")

# ...existing code...

# Add new bank account for provider
@login_required
@provider_required
def add_bank_account(request):
    if request.method == "POST":
        form = BankAccountForm(request.POST)
        if form.is_valid():
            bank = form.save(commit=False)
            bank.provider = request.user
            bank.save()
            sync_bank_active_state(bank)
            sync_provider_bank_states(request.user)
            messages.success(request, "Banka hesabı başarıyla eklendi.")
            return redirect("provider_panel:bank_list")
    else:
        form = BankAccountForm()
    return render(request, "provider_panel/add_bank_account.html", {"form": form})

@login_required
@provider_required
def bank_form(request, pk=None):
    """Edit an existing bank account using the generic bank_form.html template."""
    if pk:
        account = get_object_or_404(BankAccount, pk=pk, provider=request.user)
        form = BankAccountForm(request.POST or None, instance=account)
    else:
        form = BankAccountForm(request.POST or None)
        account = None

    if request.method == "POST" and form.is_valid():
        bank = form.save(commit=False)
        bank.provider = request.user
        bank.save()
        sync_bank_active_state(bank)
        sync_provider_bank_states(request.user)
        messages.success(request, "Banka hesabı başarıyla kaydedildi.")
        return redirect("provider_panel:list_bank_accounts")

    return render(request, "provider_panel/bank_form.html", {"form": form, "account": account})

# Add new bank account for provider
@login_required
@provider_required
def add_bank_account(request):
    if request.method == "POST":
        form = BankAccountForm(request.POST)
        if form.is_valid():
            bank = form.save(commit=False)
            bank.provider = request.user
            bank.save()
            sync_bank_active_state(bank)
            sync_provider_bank_states(request.user)
            messages.success(request, "Banka hesabı başarıyla eklendi.")
            return redirect("provider_panel:bank_list")
    else:
        form = BankAccountForm()
    return render(request, "provider_panel/add_bank_account.html", {"form": form})

# Confirm and delete a bank account
@login_required
@provider_required
def bank_delete_confirm(request, pk):
    account = get_object_or_404(BankAccount, pk=pk, provider=request.user)
    if request.method == "POST":
        account.is_active = False
        account.save()
        sync_provider_bank_states(request.user)
        messages.success(request, "Banka hesabı silindi.")
        return redirect("provider_panel:bank_list")
    return render(request, "provider_panel/bank_delete_confirm.html", {"account": account})

# List all active bank accounts for the provider
@login_required
@provider_required
def bank_list(request):
    accounts = BankAccount.objects.filter(provider=request.user, is_active=True)
    return render(request, "provider_panel/bank_list.html", {"accounts": accounts})

@login_required
@provider_required
def finance_history(request):
    """Combined deposit/withdraw history for the logged-in Teminci with basic filters."""

    start_date_str = request.GET.get("start_date") or ""
    end_date_str = request.GET.get("end_date") or ""
    bank_query = request.GET.get("bank_name") or ""

    deposits = DepositRequest.objects.filter(provider=request.user).select_related("branch", "client", "bank_account")
    withdrawals = WithdrawalRequest.objects.filter(provider=request.user).select_related("branch", "client")

    if start_date_str:
        start_date = parse_date(start_date_str)
        if start_date:
            deposits = deposits.filter(created_at__date__gte=start_date)
            withdrawals = withdrawals.filter(created_at__date__gte=start_date)

    if end_date_str:
        end_date = parse_date(end_date_str)
        if end_date:
            deposits = deposits.filter(created_at__date__lte=end_date)
            withdrawals = withdrawals.filter(created_at__date__lte=end_date)

    if bank_query:
        deposits = deposits.filter(bank_account__bank_name__icontains=bank_query)
        withdrawals = withdrawals.filter(bank_account__bank_name__icontains=bank_query)

    transactions = []

    for d in deposits:
        bank_name = d.bank_account.bank_name if d.bank_account else ""
        transactions.append({
            "created_at": d.created_at,
            "type": "deposit",
            "full_name": d.user_name,
            "amount": d.amount,
            "bank_name": bank_name,
            "status": d.get_status_display(),
        })

    for w in withdrawals:
        transactions.append({
            "created_at": w.created_at,
            "type": "withdraw",
            "full_name": w.user_name,
            "amount": w.amount,
            "bank_name": w.iban,
            "status": w.get_status_display(),
        })

    transactions.sort(key=lambda x: x["created_at"], reverse=True)

    context = {
        "transactions": transactions,
        "filters": {
            "start": start_date_str,
            "end": end_date_str,
            "bank": bank_query,
        },
    }

    return render(request, "provider_panel/finance_history.html", context)


@login_required
@provider_required
def provider_commissions(request):
    """Show this Teminci's commission totals and line items from ProviderCommission."""

    provider_profile = getattr(request.user, "provider_profile", None)

    if provider_profile is None:
        commissions = ProviderCommission.objects.none()
    else:
        commissions = ProviderCommission.objects.filter(provider=provider_profile).order_by("-created_at")

    start_date_str = request.GET.get("start_date") or ""
    end_date_str = request.GET.get("end_date") or ""
    status = request.GET.get("status") or "all"

    if start_date_str:
        start_date = parse_date(start_date_str)
        if start_date:
            commissions = commissions.filter(created_at__date__gte=start_date)

    if end_date_str:
        end_date = parse_date(end_date_str)
        if end_date:
            commissions = commissions.filter(created_at__date__lte=end_date)

    if status == "paid":
        commissions = commissions.filter(is_paid=True)
    elif status == "unpaid":
        commissions = commissions.filter(is_paid=False)

    total_earned = commissions.aggregate(total=Sum("amount"))["total"] or 0
    total_paid = commissions.filter(is_paid=True).aggregate(total=Sum("amount"))["total"] or 0
    total_unpaid = total_earned - total_paid

    context = {
        "commissions": commissions,
        "total_earned": total_earned,
        "total_paid": total_paid,
        "total_unpaid": total_unpaid,
        "filters": {
            "start": start_date_str,
            "end": end_date_str,
            "status": status,
        },
    }

    return render(request, "provider_panel/commissions.html", context)


@login_required
@provider_required
def notifications_feed(request):
    provider = request.user

    deposit_queryset = (
        DepositRequest.objects
        .filter(provider=provider, status="pending", submitted_at__isnull=False)
        .order_by("-created_at")
        .values("id", "user_name", "amount", "created_at")[:5]
    )

    withdrawal_queryset = (
        WithdrawalRequest.objects
        .filter(provider=provider, status="pending")
        .order_by("-created_at")
        .values("id", "user_name", "amount", "created_at")[:5]
    )

    def serialize(entries):
        return [
            {
                "id": entry["id"],
                "user_name": entry["user_name"],
                "amount": float(entry["amount"]),
                "created_at": entry["created_at"].isoformat() if entry["created_at"] else None,
            }
            for entry in entries
        ]

    data = {
        "deposits": serialize(deposit_queryset),
        "withdrawals": serialize(withdrawal_queryset),
        "poll_interval": 15,
        "sound_enabled": True,
    }

    return JsonResponse(data)

@login_required
@provider_required
def list_bank_accounts(request):
    """Show active bank accounts using the localized list_bank_accounts.html template."""
    accounts = BankAccount.objects.filter(provider=request.user).order_by("-created_at")
    return render(request, "provider_panel/list_bank_accounts.html", {"accounts": accounts})

def provider_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user and user.role == "PROVIDER":
            auth_login(request, user)
            return redirect("provider_panel:provider_dashboard")
        messages.error(request, "Geçersiz giriş bilgileri.")
    return render(request, "admin_panel/login.html", {
        "panel_title": "Teminci Paneli",
        "panel_subtitle": "Teminci hesabınız ile giriş yapın.",
        "access_badge": "Teminci Girişi",
    })


@login_required
def provider_dashboard(request):
    # Dashboard statistics

    from django.utils import timezone
    from datetime import timedelta
    from core import models as core_models
    from django.db import models
    today = timezone.now().date()
    month_start = today.replace(day=1)

    # Teminci profil bilgisi (cüzdan vb.)
    provider_profile = getattr(request.user, "provider_profile", None)


    stats = {
        "today_deposits": core_models.DepositRequest.objects.filter(provider=request.user, created_at__date=today).aggregate(total=models.Sum('amount'))['total'] or 0,
        "month_deposits": core_models.DepositRequest.objects.filter(provider=request.user, created_at__date__gte=month_start).aggregate(total=models.Sum('amount'))['total'] or 0,
        "total_deposits": core_models.DepositRequest.objects.filter(provider=request.user).aggregate(total=models.Sum('amount'))['total'] or 0,
        "pending_deposits": core_models.DepositRequest.objects.filter(provider=request.user, status='pending').count(),
    }

    ZERO = Decimal("0")
    HUNDRED = Decimal("100")

    deposit_volume = core_models.DepositRequest.objects.filter(provider=request.user, status="approved").aggregate(total=models.Sum("amount"))["total"] or ZERO
    withdraw_volume = core_models.WithdrawalRequest.objects.filter(provider=request.user, status="approved").aggregate(total=models.Sum("amount"))["total"] or ZERO

    if not isinstance(deposit_volume, Decimal):
        deposit_volume = Decimal(deposit_volume)
    if not isinstance(withdraw_volume, Decimal):
        withdraw_volume = Decimal(withdraw_volume)

    deposit_rate = Decimal(str(getattr(provider_profile, "deposit_commission", 0) or 0)) if provider_profile else ZERO
    withdraw_rate = Decimal(str(getattr(provider_profile, "withdraw_commission", 0) or 0)) if provider_profile else ZERO

    teminci_deposit_commission = (deposit_volume * deposit_rate) / HUNDRED if deposit_rate else ZERO
    teminci_withdraw_commission = (withdraw_volume * withdraw_rate) / HUNDRED if withdraw_rate else ZERO
    teminci_commission_total = teminci_deposit_commission + teminci_withdraw_commission

    stats["deposit_volume"] = deposit_volume
    stats["withdraw_volume"] = withdraw_volume
    stats["deposit_rate"] = deposit_rate
    stats["withdraw_rate"] = withdraw_rate
    stats["deposit_commission_total"] = teminci_deposit_commission
    stats["withdraw_commission_total"] = teminci_withdraw_commission
    stats["total_commission"] = teminci_commission_total

    deposits = core_models.DepositRequest.objects.filter(provider=request.user).order_by('-created_at')[:10]
    withdrawals = core_models.WithdrawalRequest.objects.filter(provider=request.user).order_by('-created_at')[:10]
    bank_accounts = core_models.BankAccount.objects.filter(provider=request.user, is_active=True)

    # compute teslimat (settlement) via helper
    try:
        from core.utils.settlements import compute_provider_settlement
        teslimat = compute_provider_settlement(request.user)
    except Exception:
        teslimat = {
            "total_deposits": 0,
            "total_withdrawals": 0,
            "total_commission": 0,
            "total_settlements": 0,
            "balance": 0,
        }

    return render(request, "provider_panel/dashboard.html", {
        "stats": stats,
        "deposits": deposits,
        "withdrawals": withdrawals,
        "bank_accounts": bank_accounts,
        "provider_profile": provider_profile,
        "teslimat": teslimat,
    })

# List all transactions for the provider (for transactions.html)
@login_required
@provider_required
def transactions(request):
    date_from_str = (request.GET.get("date_from") or "").strip()
    date_to_str = (request.GET.get("date_to") or "").strip()
    tx_type = (request.GET.get("tx_type") or "").strip()
    status = (request.GET.get("status") or "").strip()
    bank_query = (request.GET.get("bank") or "").strip()

    deposits = DepositRequest.objects.filter(provider=request.user)
    withdrawals = WithdrawalRequest.objects.filter(provider=request.user)

    if date_from_str:
        start_date = parse_date(date_from_str)
        if start_date:
            deposits = deposits.filter(created_at__date__gte=start_date)
            withdrawals = withdrawals.filter(created_at__date__gte=start_date)

    if date_to_str:
        end_date = parse_date(date_to_str)
        if end_date:
            deposits = deposits.filter(created_at__date__lte=end_date)
            withdrawals = withdrawals.filter(created_at__date__lte=end_date)

    if bank_query:
        deposits = deposits.filter(bank_account__bank_name__icontains=bank_query)
        withdrawals = withdrawals.filter(iban__icontains=bank_query)

    tx_items = []

    if tx_type in ["", "deposit"]:
        for d in deposits:
            if status and d.status != status:
                continue
            branch = getattr(d, "branch", None)
            site_name = getattr(branch, "name", None) or getattr(d.client, "name", None) or getattr(branch, "site_code", "-")
            site_code = getattr(branch, "site_code", None) or "-"
            tx_items.append({
                "id": d.id,
                "type": "deposit",
                "label": "Yatırım",
                "user_name": d.user_name,
                "amount": d.amount,
                "bank_name": d.bank_account.bank_name if d.bank_account else "-",
                "site_name": site_name,
                "site_code": site_code,
                "status": d.get_status_display(),
                "status_code": d.status,
                "created_at": d.created_at,
            })

    if tx_type in ["", "withdraw"]:
        for w in withdrawals:
            if status and w.status != status:
                continue
            branch = getattr(w, "branch", None)
            site_name = getattr(branch, "name", None) or getattr(w.client, "name", None) or getattr(branch, "site_code", "-")
            site_code = getattr(branch, "site_code", None) or "-"
            tx_items.append({
                "id": w.id,
                "type": "withdraw",
                "label": "Çekim",
                "user_name": w.user_name,
                "amount": w.amount,
                "bank_name": w.iban,
                "site_name": site_name,
                "site_code": site_code,
                "status": w.get_status_display(),
                "status_code": w.status,
                "created_at": w.created_at,
            })

    tx_items.sort(key=lambda item: item["created_at"], reverse=True)

    context = {
        "txs": tx_items,
        "filters": {
            "date_from": date_from_str,
            "date_to": date_to_str,
            "tx_type": tx_type,
            "status": status,
            "bank": bank_query,
        },
    }

    return render(request, "provider_panel/transactions.html", context)

@login_required
@provider_required
def pending_withdrawals(request):
    withdrawals = (
        WithdrawalRequest.objects
        .filter(provider=request.user, status='pending')
        .select_related('branch', 'client')
    )
    return render(request, "provider_panel/pending_withdrawals.html", {"withdrawals": withdrawals})



@login_required
@provider_required
def withdrawals(request):
    withdrawals = WithdrawalRequest.objects.filter(provider=request.user).order_by('-created_at')
    return render(request, "provider_panel/withdrawals.html", {"withdrawals": withdrawals})


    # (duplicate add_bank_account definitions removed; see single implementation above)



@login_required
@provider_required
def edit_bank_account(request, pk):
    account = get_object_or_404(BankAccount, id=pk, provider=request.user)
    if request.method == "POST":
        form = BankAccountForm(request.POST, instance=account)
        if form.is_valid():
            bank = form.save()
            sync_bank_active_state(bank)
            sync_provider_bank_states(request.user)
            messages.success(request, "Hesap güncellendi.")
            return redirect("provider_panel:bank_list")
    else:
        form = BankAccountForm(instance=account)
    return render(request, "provider_panel/edit_bank_account.html", {"form": form})


@provider_required
def delete_bank_account(request, account_id):
    account = get_object_or_404(BankAccount, id=account_id, provider=request.user)
    account.is_active = False
    account.save()
    sync_provider_bank_states(request.user)
    messages.success(request, "Banka hesabı silindi.")
    return redirect('provider_panel:bank_list')

@login_required
@provider_required
def deposit_requests(request):
    deposits = DepositRequest.objects.filter(status="pending").order_by("-created_at")
    return render(request, "provider_panel/deposit_requests.html", {"deposits": deposits})

@login_required
@provider_required
def approve_deposit(request, deposit_id):
    deposit = get_object_or_404(DepositRequest, id=deposit_id, status='pending', provider=request.user)

    deposit.status = 'approved'
    deposit.processed_at = timezone.now()
    deposit.save()
    sync_bank_active_state(deposit.bank_account)
    sync_provider_bank_states(request.user)

    messages.success(request, f"#{deposit.id} nolu yatırım onaylandı.")
    return redirect('provider_panel:pending_deposits')


@login_required
@provider_required
def reject_deposit(request, deposit_id):
    deposit = get_object_or_404(DepositRequest, id=deposit_id, status='pending', provider=request.user)

    deposit.status = 'rejected'
    deposit.processed_at = timezone.now()
    deposit.save()
    sync_provider_bank_states(request.user)

    messages.warning(request, f"#{deposit.id} nolu yatırım reddedildi.")
    return redirect('provider_panel:pending_deposits')

@login_required
@provider_required
def withdrawal_requests(request):
    withdrawals = WithdrawalRequest.objects.filter(provider=request.user).order_by('-created_at')

    context = {
        "withdrawals": withdrawals
    }
    return render(request, "provider_panel/withdrawals.html", context)

@login_required
@provider_required
def approve_withdrawal(request, withdrawal_id):
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id, provider=request.user)

    if withdrawal.status == "pending":
        # Onayla ve teminci cüzdanından düş (negatif bakiyeye izin verilir)
        withdrawal.status = "approved"
        withdrawal.save(update_fields=["status"])

        provider_profile = getattr(request.user, "provider_profile", None)
        if provider_profile is not None:
            current_balance = provider_profile.wallet_balance or Decimal("0")
            provider_profile.wallet_balance = current_balance - withdrawal.amount
            provider_profile.save(update_fields=["wallet_balance"])

        messages.success(request, "Çekim talebi onaylandı ve cüzdan bakiyeniz güncellendi.")
    else:
        messages.warning(request, "Bu talep zaten işlenmiş.")

    return redirect("provider_withdrawals")


@login_required
@provider_required
def reject_withdrawal(request, withdrawal_id):
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id, provider=request.user)

    if withdrawal.status == "pending":
        withdrawal.status = "rejected"
        withdrawal.save()
        messages.success(request, "Çekim talebi reddedildi.")
    else:
        messages.warning(request, "Bu talep zaten işlenmiş.")

    return redirect("provider_withdrawals")

@login_required
@provider_required
def add_bank_account(request):
    if request.method == "POST":
        form = BankAccountForm(request.POST)
        if form.is_valid():
            bank = form.save(commit=False)
            bank.provider = request.user
            bank.save()
            sync_bank_active_state(bank)
            sync_provider_bank_states(request.user)
            messages.success(request, "Banka hesabı başarıyla eklendi.")
            return redirect("provider_panel:bank_list")
    else:
        form = BankAccountForm()
    
    return render(request, "provider_panel/add_bank_account.html", {"form": form})

@login_required
@provider_required
def list_bank_accounts(request):
    accounts = BankAccount.objects.filter(provider=request.user).order_by("-created_at")
    return render(request, "provider_panel/list_bank_accounts.html", {"accounts": accounts})

@login_required
@provider_required
def delete_bank_account(request, account_id):
    account = get_object_or_404(BankAccount, id=account_id, provider=request.user)
    account.delete()
    sync_provider_bank_states(request.user)
    messages.success(request, "Hesap silindi.")
    return redirect("provider_panel:bank_list")

@login_required
@provider_required
def provider_finance_report(request):
    provider = request.user
    deposits = DepositRequest.objects.filter(provider=provider)
    withdrawals = WithdrawalRequest.objects.filter(provider=provider)

    # Filter by date range
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    bank = request.GET.get("bank")

    if start_date:
        deposits = deposits.filter(created_at__date__gte=parse_date(start_date))
        withdrawals = withdrawals.filter(created_at__date__gte=parse_date(start_date))
    if end_date:
        deposits = deposits.filter(created_at__date__lte=parse_date(end_date))
        withdrawals = withdrawals.filter(created_at__date__lte=parse_date(end_date))
    if bank:
        deposits = deposits.filter(bank_account__bank_name__icontains=bank)
        withdrawals = withdrawals.filter(bank_account__bank_name__icontains=bank)

    total_deposits = deposits.aggregate(Sum("amount"))["amount__sum"] or 0
    total_withdrawals = withdrawals.aggregate(Sum("amount"))["amount__sum"] or 0

    return render(request, "provider_panel/finance_report.html", {
        "deposits": deposits.order_by("-created_at")[:100],
        "withdrawals": withdrawals.order_by("-created_at")[:100],
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "start_date": start_date,
        "end_date": end_date,
        "bank": bank,
    })
    
@login_required
@provider_required
def provider_profile(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # keep user logged in
            messages.success(request, 'Şifreniz başarıyla güncellendi.')
            return redirect('provider_panel:provider_profile')
        else:
            messages.error(request, 'Lütfen formu kontrol ediniz.')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'provider_panel/profile.html', {
        'form': form
    })

@login_required
@provider_required
def pending_deposits(request):
    deposits = DepositRequest.objects.filter(provider=request.user, status='pending')
    return render(request, "provider_panel/pending_deposits.html", {"deposits": deposits})

@provider_required
def finance_report(request):
    start = request.GET.get("start_date")
    end = request.GET.get("end_date")
    deposits = DepositRequest.objects.filter(provider=request.user)
    withdrawals = WithdrawalRequest.objects.filter(provider=request.user)

    if start:
        deposits = deposits.filter(created_at__gte=start)
        withdrawals = withdrawals.filter(created_at__gte=start)
    if end:
        deposits = deposits.filter(created_at__lte=end)
        withdrawals = withdrawals.filter(created_at__lte=end)

    return render(request, "provider_panel/finance_report.html", {
        "deposits": deposits,
        "withdrawals": withdrawals
    })

def provider_logout(request):
    logout(request)
    messages.success(request, "Başarıyla çıkış yaptınız.")
    return redirect('provider_panel:provider_login')