
#
from core.decorators import provider_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from core.models import WithdrawalRequest, User, DepositRequest, BankAccount
from provider_panel.forms import BankAccountForm
from django.utils.decorators import method_decorator
from django.contrib.auth import authenticate, login as auth_login, update_session_auth_hash, logout
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
from django.utils.dateparse import parse_date
from django.contrib.auth.forms import PasswordChangeForm

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
            messages.success(request, "Banka hesabı başarıyla eklendi.")
            return redirect("provider_bank_accounts")
    else:
        form = BankAccountForm()
    return render(request, "provider_panel/add_bank_account.html", {"form": form})

# List all bank accounts for the provider (for bank_accounts.html)
@login_required
@provider_required
def bank_accounts(request):
    accounts = BankAccount.objects.filter(provider=request.user)
    return render(request, "provider_panel/bank_accounts.html", {"accounts": accounts})

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
            messages.success(request, "Banka hesabı başarıyla eklendi.")
            return redirect("provider_bank_accounts")
    else:
        form = BankAccountForm()
    return render(request, "provider_panel/add_bank_account.html", {"form": form})

# Bank account form view (add/edit)
@login_required
@provider_required
def bank_form(request, pk=None):
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
        messages.success(request, "Banka hesabı başarıyla kaydedildi.")
        return redirect("provider_bank_accounts")
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
            messages.success(request, "Banka hesabı başarıyla eklendi.")
            return redirect("provider_bank_accounts")
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
        messages.success(request, "Banka hesabı silindi.")
        return redirect("provider_bank_accounts")
    return render(request, "provider_panel/bank_delete_confirm.html", {"account": account})

# List all active bank accounts for the provider
@login_required
@provider_required
def bank_list(request):
    accounts = BankAccount.objects.filter(provider=request.user, is_active=True)
    return render(request, "provider_panel/bank_list.html", {"accounts": accounts})

@provider_required
def finance_history(request):
    # You can add context data as needed
    return render(request, "provider_panel/finance_history.html", {})

@login_required
@provider_required
def list_bank_accounts(request):
    accounts = BankAccount.objects.filter(provider=request.user).order_by("-created_at")
    return render(request, "provider_panel/list_bank_accounts.html", {"accounts": accounts})

def provider_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user and user.role == "provider":
            auth_login(request, user)
            return redirect("provider_panel:provider_dashboard")
        messages.error(request, "Geçersiz giriş bilgileri.")
    return render(request, "provider_panel/login.html")


@login_required
def provider_dashboard(request):
    # Dashboard statistics

    from django.utils import timezone
    from datetime import timedelta
    from core import models as core_models
    from django.db import models
    today = timezone.now().date()
    month_start = today.replace(day=1)


    stats = {
        "today_deposits": core_models.DepositRequest.objects.filter(provider=request.user, created_at__date=today).aggregate(total=models.Sum('amount'))['total'] or 0,
        "month_deposits": core_models.DepositRequest.objects.filter(provider=request.user, created_at__date__gte=month_start).aggregate(total=models.Sum('amount'))['total'] or 0,
        "total_deposits": core_models.DepositRequest.objects.filter(provider=request.user).aggregate(total=models.Sum('amount'))['total'] or 0,
        "pending_deposits": core_models.DepositRequest.objects.filter(provider=request.user, status='pending').count(),
    }

    deposits = core_models.DepositRequest.objects.filter(provider=request.user).order_by('-created_at')[:10]
    withdrawals = core_models.WithdrawalRequest.objects.filter(provider=request.user).order_by('-created_at')[:10]
    bank_accounts = core_models.BankAccount.objects.filter(provider=request.user, is_active=True)

    return render(request, "provider_panel/dashboard.html", {
        "stats": stats,
        "deposits": deposits,
        "withdrawals": withdrawals,
        "bank_accounts": bank_accounts,
    })

# List all transactions for the provider (for transactions.html)
@login_required
@provider_required
def transactions(request):
    deposits = DepositRequest.objects.filter(provider=request.user)
    withdrawals = WithdrawalRequest.objects.filter(provider=request.user)
    # You can add more transaction types if needed
    return render(request, "provider_panel/transactions.html", {
        "deposits": deposits,
        "withdrawals": withdrawals
    })

@login_required
def pending_withdrawals(request):
    withdrawals = WithdrawalRequest.objects.filter(provider=request.user, status='pending')
    return render(request, "provider_panel/pending_withdrawals.html", {"withdrawals": withdrawals})



@login_required
@provider_required
def withdrawals(request):
    withdrawals = WithdrawalRequest.objects.filter(provider=request.user).order_by('-created_at')
    return render(request, "provider_panel/withdrawals.html", {"withdrawals": withdrawals})


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
            messages.success(request, "Banka hesabı başarıyla eklendi.")
            return redirect("provider_bank_accounts")
    else:
        form = BankAccountForm()
    return render(request, "provider_panel/add_bank_account.html", {"form": form})



@login_required
@provider_required
def edit_bank_account(request, pk):
    account = get_object_or_404(BankAccount, id=pk, provider=request.user)
    if request.method == "POST":
        form = BankAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, "Hesap güncellendi.")
            return redirect("provider_bank_accounts")
    else:
        form = BankAccountForm(instance=account)
    return render(request, "provider_panel/edit_bank_account.html", {"form": form})


@provider_required
def delete_bank_account(request, account_id):
    account = get_object_or_404(BankAccount, id=account_id, provider=request.user)
    account.is_active = False
    account.save()
    messages.success(request, "Banka hesabı silindi.")
    return redirect('bank_accounts')

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

    messages.success(request, f"#{deposit.id} nolu yatırım onaylandı.")
    return redirect('provider_deposits')


@login_required
@provider_required
def reject_deposit(request, deposit_id):
    deposit = get_object_or_404(DepositRequest, id=deposit_id, status='pending', provider=request.user)

    deposit.status = 'rejected'
    deposit.processed_at = timezone.now()
    deposit.save()

    messages.warning(request, f"#{deposit.id} nolu yatırım reddedildi.")
    return redirect('provider_deposits')

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
        withdrawal.status = "approved"
        withdrawal.save()
        messages.success(request, "Çekim talebi onaylandı.")
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
            messages.success(request, "Banka hesabı başarıyla eklendi.")
            return redirect("provider_bank_accounts")
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
    messages.success(request, "Hesap silindi.")
    return redirect("provider_bank_accounts")

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
            return redirect('provider_profile')
        else:
            messages.error(request, 'Lütfen formu kontrol ediniz.')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'provider_panel/profile.html', {
        'form': form
    })

@login_required
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