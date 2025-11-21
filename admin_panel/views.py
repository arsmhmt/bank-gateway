from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout, update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.utils.timezone import now
from django.db import models
from django.db.models import Q, Sum
from django import forms
import secrets
from .forms import AdminForm, BankAccountForm, ClientSiteForm
from core.models import (
    ProviderCommission, DepositRequest, WithdrawalRequest,
    ClientSite, APIKey, User, BankAccount, Commission
)
from provider_panel.models import Provider
from admin_panel.decorators import superadmin_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

# --------------------
# HELPERS
# --------------------
def is_superadmin(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'superadmin'


# --------------------
# FORMS
# --------------------
# ADMIN MANAGEMENT VIEWS
# --------------------
UserModel = get_user_model()

@login_required
@user_passes_test(is_superadmin)
def view_admins(request):
    admins = UserModel.objects.filter(role='admin')
    return render(request, "admin_panel/view_admins.html", {"admins": admins})

@login_required
@user_passes_test(is_superadmin)
def add_admin(request):
    if request.method == "POST":
        form = AdminForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_panel:manage_admins")
    else:
        form = AdminForm()
    return render(request, "admin_panel/add_admin.html", {"form": form})

@login_required
@user_passes_test(is_superadmin)
def edit_admin(request, admin_id):
    admin = get_object_or_404(UserModel, id=admin_id)
    form = AdminForm(request.POST or None, instance=admin)
    if form.is_valid():
        form.save()
        return redirect("admin_panel:manage_admins")
    return render(request, "admin_panel/edit_admin.html", {"form": form})

@login_required
@user_passes_test(is_superadmin)
def delete_admin(request, admin_id):
    admin = get_object_or_404(UserModel, id=admin_id)
    if request.method == "POST":
        admin.delete()
        return redirect("admin_panel:manage_admins")
    return render(request, "admin_panel/admin_delete_confirm.html", {"admin": admin})

@login_required
@user_passes_test(is_superadmin)
def admin_logs(request):
    logs = []  # Replace with real logs model
    return render(request, "admin_panel/audit_logs.html", {"logs": logs})

# --------------------
# BANK ACCOUNT VIEWS
# --------------------
@login_required
@user_passes_test(is_superadmin)
def add_bank_account(request):
    if request.method == "POST":
        form = BankAccountForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Banka hesabı başarıyla eklendi.")
            return redirect("admin_panel:list_bank_accounts")
    else:
        form = BankAccountForm()
    return render(request, "admin_panel/add_bank_account.html", {"form": form})

@login_required
@user_passes_test(is_superadmin)
def list_bank_accounts(request):
    accounts = BankAccount.objects.all().order_by('-created_at')
    return render(request, 'admin_panel/bank_list.html', {'accounts': accounts})


# --- MISSING BANK ACCOUNT VIEWS ---
@login_required
@user_passes_test(is_superadmin)
def edit_bank_account(request, account_id):
    account = get_object_or_404(BankAccount, id=account_id)
    form = BankAccountForm(request.POST or None, instance=account)
    if form.is_valid():
        form.save()
        messages.success(request, "Banka hesabı güncellendi.")
        return redirect("admin_panel:list_bank_accounts")
    return render(request, "admin_panel/bank_form.html", {"form": form})

@login_required
@user_passes_test(is_superadmin)
def delete_bank_account(request, account_id):
    account = get_object_or_404(BankAccount, id=account_id)
    if request.method == "POST":
        account.delete()
        messages.success(request, "Banka hesabı silindi.")
        return redirect("admin_panel:list_bank_accounts")
    return render(request, "admin_panel/bank_delete_confirm.html", {"account": account})

from core.decorators import superadmin_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

def is_superadmin(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'superadmin'

@login_required
@user_passes_test(is_superadmin)
@csrf_protect
def provider_commissions(request):
    if request.method == 'POST':
        commission_id = request.POST.get('commission_id')
        commission = get_object_or_404(ProviderCommission, id=commission_id)
        commission.status = 'paid'
        commission.paid_at = now()
        commission.save()
        messages.success(request, f"✅ {commission.provider.email} için komisyon ödendi olarak işaretlendi.")
        return redirect('provider_commissions')

    commissions = ProviderCommission.objects.select_related('provider').order_by('-created_at')
    return render(request, 'admin_panel/provider_commissions.html', {
        'commissions': commissions
    })

@login_required
@user_passes_test(is_superadmin)
def mark_commission_paid(request, commission_id):
    commission = get_object_or_404(ProviderCommission, id=commission_id)
    commission.is_paid = True
    commission.save()
    messages.success(request, "Komisyon başarıyla ödendi olarak işaretlendi.")
    return redirect("admin_panel:provider_commissions")

def admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user and user.role == "superadmin":
            auth_login(request, user)
            return redirect("admin_panel:admin_dashboard")
        messages.error(request, "Geçersiz giriş bilgileri.")
    return render(request, "admin_panel/login.html")

def api_keys_view(request):
    clients = ClientSite.objects.all()
    return render(request, "admin_panel/api_keys.html", {"clients": clients})

def generate_api_key(request, client_id):
    client = get_object_or_404(ClientSite, id=client_id)
    key = secrets.token_hex(32)
    APIKey.objects.update_or_create(client=client, defaults={"key": key})
    messages.success(request, f"Yeni API anahtarı oluşturuldu: {key}")
    return redirect("admin_panel:api_keys_view")

@login_required
@user_passes_test(is_superadmin)
def dashboard(request):
    total_deposits = DepositRequest.objects.filter(status="approved").aggregate(total=Sum("amount"))["total"] or 0
    total_withdrawals = 0  # To be implemented
    total_commission = 0  # To be calculated based on commission fields
    site_count = ClientSite.objects.count()

    recent_deposits = DepositRequest.objects.order_by("-created_at")[:10]

    context = {
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "total_commission": total_commission,
        "site_count": site_count,
        "recent_deposits": recent_deposits,
    }
    return render(request, "admin_panel/dashboard.html", context)

@login_required
@user_passes_test(is_superadmin)
def pending_deposits(request):
    deposits = DepositRequest.objects.filter(status="pending").order_by("-created_at")

    # Filters
    payment_id = request.GET.get("payment_id")
    name = request.GET.get("name")
    site = request.GET.get("site")

    if payment_id:
        deposits = deposits.filter(payment_id__icontains=payment_id)
    if name:
        deposits = deposits.filter(Q(name__icontains=name) | Q(surname__icontains=name))
    if site:
        deposits = deposits.filter(client_site__name__icontains=site)

    context = {
        "deposits": deposits,
    }
    return render(request, "admin_panel/pending_deposits.html", context)

@login_required
@user_passes_test(is_superadmin)
def pending_withdrawals(request):
    withdrawals = WithdrawalRequest.objects.filter(status="pending").order_by("-created_at")

    # Filters
    payment_id = request.GET.get("payment_id")
    name = request.GET.get("name")
    site = request.GET.get("site")

    if payment_id:
        withdrawals = withdrawals.filter(payment_id__icontains=payment_id)
    if name:
        withdrawals = withdrawals.filter(Q(name__icontains=name) | Q(surname__icontains=name))
    if site:
        withdrawals = withdrawals.filter(client_site__name__icontains=site)

    context = {
        "withdrawals": withdrawals,
    }
    return render(request, "admin_panel/pending_withdrawals.html", context)

@login_required
@user_passes_test(is_superadmin)
def add_client_site(request):
    if request.method == "POST":
        name = request.POST.get("name")
        domain = request.POST.get("domain")
        contact_person = request.POST.get("contact_person")
        contact_email = request.POST.get("contact_email")
        deposit_commission = request.POST.get("deposit_commission")
        withdraw_commission = request.POST.get("withdraw_commission")

        ClientSite.objects.create(
            name=name,
            domain=domain,
            contact_person=contact_person,
            contact_email=contact_email,
            deposit_commission=deposit_commission,
            withdraw_commission=withdraw_commission,
        )
        return redirect("list_client_sites")

    return render(request, "admin_panel/add_client_site.html")

@login_required
@user_passes_test(is_superadmin)
def list_client_sites(request):
    sites = ClientSite.objects.all()
    return render(request, "admin_panel/list_client_sites.html", {"sites": sites})

@login_required
@user_passes_test(is_superadmin)
def add_provider(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        deposit_commission = request.POST.get("deposit_commission")
        withdraw_commission = request.POST.get("withdraw_commission")

        user = User.objects.create_user(
            username=email,
            email=email,
            password="teminci123",  # you can auto-generate or send later
            role="provider"
        )
        user.save()

        Provider.objects.create(
            user=user,
            name=name,
            phone=phone,
            deposit_commission=deposit_commission,
            withdraw_commission=withdraw_commission
        )

        return redirect("list_providers")

    return render(request, "admin_panel/add_provider.html")

@login_required
@user_passes_test(is_superadmin)
def list_providers(request):
    providers = Provider.objects.select_related("user").all()
    return render(request, "admin_panel/list_providers.html", {"providers": providers})

@superadmin_required
def provider_list(request):
    providers = User.objects.filter(role='provider')

    summary = []
    for provider in providers:
        total_deposits = DepositRequest.objects.filter(provider=provider, status='approved').count()
        total_withdrawals = WithdrawalRequest.objects.filter(provider=provider, status='approved').count()
        total_commission = ProviderCommission.objects.filter(provider=provider, status='paid').aggregate(
            total=models.Sum('amount')
        )['total'] or 0

        summary.append({
            'provider': provider,
            'deposits': total_deposits,
            'withdrawals': total_withdrawals,
            'commission': total_commission,
        })

    return render(request, 'admin_panel/provider_list.html', {
        'summary': summary
    })

@login_required
@user_passes_test(is_superadmin)
def edit_provider(request, provider_id):
    provider = get_object_or_404(Provider, id=provider_id)

    if request.method == 'POST':
        name = request.POST.get("name")
        phone = request.POST.get("phone")
        deposit_commission = request.POST.get("deposit_commission")
        withdraw_commission = request.POST.get("withdraw_commission")

        provider.name = name
        provider.phone = phone
        provider.deposit_commission = deposit_commission
        provider.withdraw_commission = withdraw_commission
        provider.save()

        messages.success(request, "Teminci başarıyla güncellendi.")
        return redirect("admin_panel:provider_list")

    return render(request, "admin_panel/edit_provider.html", {"provider": provider})

@login_required
@user_passes_test(is_superadmin)
def delete_provider(request, provider_id):
    provider = get_object_or_404(Provider, id=provider_id)

    if request.method == 'POST':
        provider.user.delete()  # also deletes related Provider via on_delete=CASCADE
        messages.success(request, "Teminci başarıyla silindi.")
        return redirect("admin_panel:provider_list")

    return render(request, "admin_panel/provider_delete_confirm.html", {"provider": provider})


@login_required
@superadmin_required
def admin_dashboard(request):
    today = timezone.now().date()
    deposits_today = DepositRequest.objects.filter(created_at__date=today).count()
    withdrawals_today = WithdrawalRequest.objects.filter(created_at__date=today).count()

    deposits_month = DepositRequest.objects.filter(
        created_at__month=today.month, created_at__year=today.year
    ).count()

    total_deposits = DepositRequest.objects.count()
    total_withdrawals = WithdrawalRequest.objects.count()

    recent_deposits = DepositRequest.objects.order_by("-created_at")[:5]
    recent_withdrawals = WithdrawalRequest.objects.order_by("-created_at")[:5]

    return render(request, "admin_panel/dashboard.html", {
        "deposits_today": deposits_today,
        "withdrawals_today": withdrawals_today,
        "deposits_month": deposits_month,
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "recent_deposits": recent_deposits,
        "recent_withdrawals": recent_withdrawals,
    })

@login_required
@superadmin_required
def pending_deposits(request):
    deposits = DepositRequest.objects.filter(status='pending').order_by('-created_at')
    return render(request, 'admin_panel/pending_deposits.html', {'deposits': deposits})

@login_required
@superadmin_required
def approve_deposit(request, deposit_id):
    deposit = get_object_or_404(DepositRequest, id=deposit_id)
    deposit.status = 'approved'
    deposit.save()
    messages.success(request, "Yatırım onaylandı.")
    return redirect('pending_deposits')


@login_required
@superadmin_required
def reject_deposit(request, deposit_id):
    deposit = get_object_or_404(DepositRequest, id=deposit_id)
    deposit.status = 'rejected'
    deposit.save()
    messages.warning(request, "Yatırım reddedildi.")
    return redirect('pending_deposits')

@login_required
@superadmin_required
def admin_profile(request):
    return render(request, "admin_panel/profile.html")

@login_required
@superadmin_required
def change_admin_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keeps the user logged in
            messages.success(request, 'Şifreniz başarıyla güncellendi.')
            return redirect('admin_profile')
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, 'admin_panel/change_password.html', {'form': form})
def provider_report(request):
    # Dummy context for demonstration; replace with actual logic
    provider_data = [
        # Example: {'provider': {'first_name': 'Ali', 'last_name': 'Veli'}, 'deposits': 1000, 'withdrawals': 500, 'earned': 200, 'paid': 100, 'balance': 100}
    ]
    context = {
        'provider_data': provider_data,
    }
    return render(request, 'admin_panel/provider_report.html', context)
def financial_reports(request):
    # Dummy context for demonstration; replace with actual logic
    context = {
        'filters': {},
        'sites': [],
        'providers': [],
        'site_data': [],
        'provider_data': [],
        'site_comm_total': 0,
        'provider_comm_total': 0,
        'net_profit': 0,
    }
    return render(request, 'admin_panel/financial_reports.html', context)

@login_required
@superadmin_required
def site_finance_report(request):
    return render(request, "admin_panel/site_finance_report.html")

@login_required
@superadmin_required
def commission_report(request):
    return render(request, "admin_panel/commission_report.html")

@login_required
@superadmin_required
def add_admin(request):
    return render(request, "admin_panel/add_admin.html")

@login_required
@superadmin_required
def manage_admins(request):
    return render(request, "admin_panel/manage_admins.html")

@login_required
@superadmin_required
def admin_logs(request):
    return render(request, "admin_panel/admin_logs.html")

@login_required
def admin_logout(request):
    logout(request)
    return redirect("admin_panel:login")

@login_required
@user_passes_test(is_superadmin)
def edit_client_site(request, site_id):
    site = get_object_or_404(ClientSite, pk=site_id)
    if request.method == "POST":
        form = ClientSiteForm(request.POST, instance=site)
        if form.is_valid():
            form.save()
            messages.success(request, "Client site updated successfully.")
            return redirect("admin_panel:list_client_sites")
    else:
        form = ClientSiteForm(instance=site)
    return render(request, "admin_panel/edit_client_site.html", {"form": form, "site": site})

@login_required
@user_passes_test(is_superadmin)
def delete_client_site(request, site_id):
    site = get_object_or_404(ClientSite, pk=site_id)
    if request.method == "POST":
        site.delete()
        messages.success(request, "Client site deleted successfully.")
        return redirect("admin_panel:list_client_sites")
    return render(request, "admin_panel/site_delete_confirm.html", {"site": site})
