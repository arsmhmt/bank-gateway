from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout, update_session_auth_hash, get_user_model
from django.contrib.admin.models import LogEntry
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.utils.timezone import now
from django.db import models, transaction
from decimal import Decimal
from django.db.models import Q, Sum, Count, Max
from django import forms
from django.conf import settings
from datetime import timedelta, date
from collections import defaultdict
import secrets
from .forms import (
    AdminForm,
    AdminPasswordResetForm,
    BankAccountForm,
    ClientSiteForm,
    DepositLinkForm,
    CryptoWalletConfigForm,
    CardPspConfigForm,
    CryptoWalletForm,
)
from core.models import (
    ProviderCommission,
    DepositRequest,
    WithdrawalRequest,
    ClientSite,
    APIKey,
    User,
    BankAccount,
    Commission,
    Client,
    PaymentTransaction,
    GatewayType,
)
from core.services.payment_transactions import (
    create_payment_transaction_for_deposit,
    create_payment_transaction_for_withdraw,
)
from core.utils.limitor import (
    sync_bank_active_state,
    sync_provider_bank_states,
)
from core.utils.gateways import ensure_branch_gateway_configs, build_gateway_public_urls
from branches.models import Branch, SiteGatewayConfig, CardPspConfig
from provider_panel.models import Provider
from crypto.constants import SUPPORTED_COINS, SUPPORTED_NETWORKS
from crypto.models import CryptoWalletConfig, WalletMode, CryptoPayment
from admin_panel.decorators import superadmin_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

# --------------------
# HELPERS
# --------------------
def is_superadmin(user):
    """Check if user is OWNER or ADMIN (backward compatibility)"""
    return user.is_authenticated and getattr(user, 'role', None) in ('OWNER', 'ADMIN')


def get_date_range_from_request(request):
    """Return normalized date range info based on common admin filters.

    Supported ranges:
    - today  -> only today (default)
    - week   -> from Monday of current week until today
    - month  -> from first day of current month until today
    - custom -> uses start_date / end_date (YYYY-MM-DD)
    """

    today = timezone.localdate()
    range_key = (request.GET.get("date_range") or "today").lower()

    start_date = None
    end_date = None

    if range_key == "today":
        start_date = end_date = today
    elif range_key == "week":
        # Monday of current week -> today
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif range_key == "month":
        # First day of current month -> today
        start_date = today.replace(day=1)
        end_date = today
    elif range_key == "custom":
        start_str = request.GET.get("start_date") or ""
        end_str = request.GET.get("end_date") or ""

        try:
            if start_str:
                start_date = date.fromisoformat(start_str)
            if end_str:
                end_date = date.fromisoformat(end_str)
        except ValueError:
            start_date = end_date = today
            range_key = "today"

        # If one bound is missing, fall back to today
        if not (start_date and end_date):
            start_date = end_date = today
            range_key = "today"
    else:
        # Fallback
        range_key = "today"
        start_date = end_date = today

    return {
        "date_range": range_key,
        "start_date": start_date,
        "end_date": end_date,
    }


def ensure_decimal(value):
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or "0"))


def get_commission_rates_for_site(branch=None, client=None):
    """
    Resolve the effective deposit/withdraw/system commission rates for a branch/client combo.
    Branch configuration takes precedence; we only fall back to legacy Client rates if needed.
    """

    deposit_rate = ensure_decimal(getattr(branch, "deposit_commission_rate", None))
    withdraw_rate = ensure_decimal(getattr(branch, "withdraw_commission_rate", None))
    system_rate = ensure_decimal(getattr(branch, "system_commission_rate", None))

    # Legacy fallback to Client model if branch context is missing
    if branch is None and client is not None:
        deposit_rate = ensure_decimal(getattr(client, "deposit_commission", deposit_rate))
        withdraw_rate = ensure_decimal(getattr(client, "withdraw_commission", withdraw_rate))

    return deposit_rate, withdraw_rate, system_rate


def get_provider_commission_rates(provider_user):
    """
    Fetch deposit/withdraw commission percentages for the given provider user.
    Returns (deposit_rate, withdraw_rate) as Decimals.
    """

    ZERO = Decimal("0")

    if provider_user is None:
        return ZERO, ZERO

    profile = getattr(provider_user, "provider_profile", None)
    if profile is None:
        return ZERO, ZERO

    deposit_rate = ensure_decimal(getattr(profile, "deposit_commission", ZERO))
    withdraw_rate = ensure_decimal(getattr(profile, "withdraw_commission", ZERO))
    return deposit_rate, withdraw_rate


def get_site_entry(site_stats, branch, client):
    """
    Ensure a stats bucket exists for the given branch/client combo and return it.
    """

    ZERO = Decimal("0")

    if branch:
        key = f"branch:{branch.id}"
        site_name = branch.name or (client.name if client else f"Bayi #{branch.id}")
    elif client:
        key = f"client:{client.id}"
        site_name = client.name
    else:
        key = "unassigned"
        site_name = "Tanımsız Site"

    return site_stats.setdefault(
        key,
        {
            "site_name": site_name,
            "deposit_amount": ZERO,
            "deposit_count": 0,
            "withdraw_amount": ZERO,
            "withdraw_count": 0,
            "deposit_commission_rate": ZERO,
            "withdraw_commission_rate": ZERO,
            "system_commission_rate": ZERO,
            "deposit_commission_total": ZERO,
            "withdraw_commission_total": ZERO,
            "teminci_commission_total": ZERO,
            "system_commission_total": ZERO,
            "liderpay_commission_total": ZERO,
        },
    )


def build_gateway_overview():
    today = timezone.localdate()
    overview = {}
    card_psp_active = CardPspConfig.objects.filter(is_active=True).count()
    card_psp_status = "PSP tanımlı değil"
    if card_psp_active:
        card_psp_status = f"{card_psp_active} PSP aktif"

    for gateway_value, gateway_label in GatewayType.choices:
        enabled_branches = SiteGatewayConfig.objects.filter(
            gateway=gateway_value, is_enabled=True
        ).count()

        base_qs = PaymentTransaction.objects.filter(
            gateway=gateway_value,
            created_at__date=today,
        )
        today_in = base_qs.filter(
            direction=PaymentTransaction.DIRECTION_IN
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        today_out = base_qs.filter(
            direction=PaymentTransaction.DIRECTION_OUT
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        pending_count = PaymentTransaction.objects.filter(
            gateway=gateway_value, status=PaymentTransaction.STATUS_PENDING
        ).count()

        extra = {}
        if gateway_value == GatewayType.CRYPTO:
            is_listener_active = bool(
                getattr(settings, "CRYPTO_TRON_EXPLORER_API_URL", "")
            )
            extra["listener_status"] = (
                "TRC20 listener: ACTIVE" if is_listener_active else "TRC20 listener: DISABLED"
            )
        if gateway_value == GatewayType.CARD:
            extra["psp_status"] = card_psp_status

        overview[gateway_value] = {
            "label": gateway_label,
            "enabled_branches": enabled_branches,
            "today_in": ensure_decimal(today_in),
            "today_out": ensure_decimal(today_out),
            "pending_count": pending_count,
            **extra,
        }

    return overview


def compute_commission_breakdown(amount, commission_rate, provider_rate, system_rate):
    """
    Given a transaction amount and applicable commission percentages, split the commission
    between provider/system/Lider Pay (remaining). All inputs/outputs are Decimals.
    """

    ZERO = Decimal("0")
    HUNDRED = Decimal("100")

    if amount is None:
        amount = ZERO

    amount = ensure_decimal(amount)
    commission_rate = ensure_decimal(commission_rate)
    provider_rate = ensure_decimal(provider_rate)
    system_rate = ensure_decimal(system_rate)

    total_commission = (amount * commission_rate) / HUNDRED
    if total_commission <= ZERO:
        return ZERO, ZERO, ZERO, ZERO

    provider_commission = (amount * provider_rate) / HUNDRED if provider_rate else ZERO
    provider_commission = min(provider_commission, total_commission)

    remaining = total_commission - provider_commission
    system_commission = (amount * system_rate) / HUNDRED if system_rate else ZERO
    system_commission = min(system_commission, remaining)

    liderpay_commission = total_commission - provider_commission - system_commission
    return total_commission, provider_commission, system_commission, liderpay_commission


def build_site_commission_stats(deposits_qs, withdrawals_qs):
    """
    Aggregate deposit/withdraw totals and commission splits per site (branch/client).
    Returns (site_stats_dict, totals_dict).
    """

    ZERO = Decimal("0")
    HUNDRED = Decimal("100")

    site_stats = {}

    deposit_iter = deposits_qs.select_related("branch", "client", "provider__provider_profile")
    for deposit in deposit_iter:
        branch = getattr(deposit, "branch", None)
        client = getattr(deposit, "client", None)
        entry = get_site_entry(site_stats, branch, client)

        deposit_rate, _, system_rate = get_commission_rates_for_site(branch, client)
        provider_deposit_rate, _ = get_provider_commission_rates(getattr(deposit, "provider", None))

        entry["deposit_commission_rate"] = deposit_rate
        entry["system_commission_rate"] = system_rate
        entry["deposit_amount"] += ensure_decimal(getattr(deposit, "amount", ZERO))
        entry["deposit_count"] += 1

        (
            deposit_commission_total,
            provider_commission,
            system_commission,
            liderpay_commission,
        ) = compute_commission_breakdown(
            deposit.amount,
            deposit_rate,
            provider_deposit_rate,
            system_rate,
        )

        entry["deposit_commission_total"] += deposit_commission_total
        entry["teminci_commission_total"] += provider_commission
        entry["system_commission_total"] += system_commission
        entry["liderpay_commission_total"] += liderpay_commission

    withdraw_iter = withdrawals_qs.select_related("branch", "client", "provider__provider_profile")
    for withdrawal in withdraw_iter:
        branch = getattr(withdrawal, "branch", None)
        client = getattr(withdrawal, "client", None)
        entry = get_site_entry(site_stats, branch, client)

        _, withdraw_rate, system_rate = get_commission_rates_for_site(branch, client)
        _, provider_withdraw_rate = get_provider_commission_rates(getattr(withdrawal, "provider", None))

        entry["withdraw_commission_rate"] = withdraw_rate
        entry["system_commission_rate"] = system_rate  # ensure latest system rate is visible
        entry["withdraw_amount"] += ensure_decimal(getattr(withdrawal, "amount", ZERO))
        entry["withdraw_count"] += 1

        (
            withdraw_commission_total,
            provider_commission,
            system_commission,
            liderpay_commission,
        ) = compute_commission_breakdown(
            withdrawal.amount,
            withdraw_rate,
            provider_withdraw_rate,
            system_rate,
        )

        entry["withdraw_commission_total"] += withdraw_commission_total
        entry["teminci_commission_total"] += provider_commission
        entry["system_commission_total"] += system_commission
        entry["liderpay_commission_total"] += liderpay_commission

    totals = {
        "total_site_commission": ZERO,
        "total_teminci_commission": ZERO,
        "total_system_commission": ZERO,
        "total_liderpay_commission": ZERO,
    }

    for entry in site_stats.values():
        entry["site_commission_total"] = entry["deposit_commission_total"] + entry["withdraw_commission_total"]
        totals["total_site_commission"] += entry["site_commission_total"]
        totals["total_teminci_commission"] += entry["teminci_commission_total"]
        totals["total_system_commission"] += entry["system_commission_total"]
        totals["total_liderpay_commission"] += entry["liderpay_commission_total"]

    return site_stats, totals


# --------------------
# FORMS
# --------------------
# ADMIN MANAGEMENT VIEWS
# --------------------
UserModel = get_user_model()

@login_required
@user_passes_test(is_superadmin)
def view_admins(request):
    admins = (
        UserModel.objects
        .filter(role__in=[UserModel.ROLE_ADMIN, UserModel.ROLE_OWNER])
        .order_by('-date_joined')
    )
    stats = admins.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
    )
    return render(request, "admin_panel/manage_admins.html", {
        "admins": admins,
        "admin_stats": stats,
        "self_id": request.user.id,
    })

@login_required
@user_passes_test(is_superadmin)
def add_admin(request):
    if request.method == "POST":
        form = AdminForm(request.POST)
        if form.is_valid():
            admin_user = form.save()
            messages.success(
                request,
                f"Yeni yönetim kullanıcısı oluşturuldu: {admin_user.username}",
            )
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
        messages.success(request, "Admin bilgileri güncellendi.")
        return redirect("admin_panel:manage_admins")
    return render(request, "admin_panel/edit_admin.html", {"form": form, "admin_obj": admin})

@login_required
@user_passes_test(is_superadmin)
def delete_admin(request, admin_id):
    admin = get_object_or_404(UserModel, id=admin_id)
    if admin == request.user:
        messages.error(request, "Kendi hesabınızı silemezsiniz.")
        return redirect("admin_panel:manage_admins")
    if request.method == "POST":
        admin.delete()
        messages.success(request, "Admin hesabı silindi.")
        return redirect("admin_panel:manage_admins")
    return render(request, "admin_panel/admin_delete_confirm.html", {"admin": admin})


@login_required
@user_passes_test(is_superadmin)
def toggle_admin_status(request, admin_id):
    admin = get_object_or_404(UserModel, id=admin_id)
    if request.method != "POST":
        return redirect("admin_panel:manage_admins")
    if admin == request.user:
        messages.error(request, "Kendi hesabınızı pasifleştiremezsiniz.")
        return redirect("admin_panel:manage_admins")

    admin.is_active = not admin.is_active
    admin.save(update_fields=["is_active"])
    state = "aktifleştirildi" if admin.is_active else "pasif hale getirildi"
    messages.success(request, f"{admin.get_full_name() or admin.email} {state}.")
    return redirect("admin_panel:manage_admins")


@login_required
@user_passes_test(is_superadmin)
def reset_admin_password(request, admin_id):
    admin = get_object_or_404(UserModel, id=admin_id)
    form = AdminPasswordResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        new_password = form.cleaned_data["new_password"]
        admin.set_password(new_password)
        admin.save(update_fields=["password"])
        messages.success(request, "Şifre başarıyla güncellendi.")
        return redirect("admin_panel:manage_admins")
    return render(request, "admin_panel/reset_admin_password.html", {
        "form": form,
        "admin_obj": admin,
    })

# --------------------
# BANK ACCOUNT VIEWS
# --------------------
@login_required
@user_passes_test(is_superadmin)
def add_bank_account(request):
    if request.method == "POST":
        form = BankAccountForm(request.POST)
        if form.is_valid():
            bank = form.save()
            sync_bank_active_state(bank)
            if bank.provider:
                sync_provider_bank_states(bank.provider)
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


@login_required
@user_passes_test(is_superadmin)
def edit_bank_account(request, account_id):
    account = get_object_or_404(BankAccount, id=account_id)
    form = BankAccountForm(request.POST or None, instance=account)
    if form.is_valid():
        bank = form.save()
        sync_bank_active_state(bank)
        if bank.provider:
            sync_provider_bank_states(bank.provider)
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


@login_required
@user_passes_test(is_superadmin)
def create_deposit_link(request):
    payment_base_url = getattr(settings, "PAYMENT_BASE_URL", "")

    if request.method == "POST":
        form = DepositLinkForm(request.POST)
        if form.is_valid():
            branch = form.cleaned_data["branch"]
            provider = form.cleaned_data["provider"]
            bank_account = form.cleaned_data["bank_account"]
            external_user_id = form.cleaned_data["external_user_id"]
            amount = form.cleaned_data["amount"]
            expires_in_minutes = form.cleaned_data["expires_in_minutes"]

            token = secrets.token_hex(16)
            expires_at = timezone.now() + timedelta(minutes=expires_in_minutes)

            deposit = DepositRequest.objects.create(
                user_name=external_user_id,
                external_user_id=external_user_id,
                amount=amount,
                original_amount=amount,
                client=None,
                branch=branch,
                bank_account=bank_account,
                provider=provider,
                payment_token=token,
                status="pending",
                expires_at=expires_at,
            )
            create_payment_transaction_for_deposit(deposit)

            path_part = f"/pay/{branch.site_code}/{token}/"
            if payment_base_url:
                base = payment_base_url.rstrip("/")
                link = f"{base}{path_part}"
            else:
                link = path_part
            messages.success(request, "Yatırım linki başarıyla oluşturuldu.")
            return render(
                request,
                "admin_panel/create_deposit_link.html",
                {"form": form, "deposit": deposit, "payment_link": link},
            )
    else:
        form = DepositLinkForm()

    return render(request, "admin_panel/create_deposit_link.html", {"form": form})

@login_required
@user_passes_test(is_superadmin)
@csrf_protect
def provider_commissions(request):
    if request.method == 'POST':
        commission_id = request.POST.get('commission_id')
        commission = get_object_or_404(ProviderCommission, id=commission_id)
        commission.is_paid = True
        commission.save()
        messages.success(request, f"✅ {commission.provider} için komisyon ödendi olarak işaretlendi.")
        return redirect('admin_panel:provider_commissions')

    date_info = get_date_range_from_request(request)
    start_date = date_info["start_date"]
    end_date = date_info["end_date"]

    commissions = ProviderCommission.objects.select_related('provider').order_by('-created_at')
    if start_date and end_date:
        commissions = commissions.filter(created_at__date__range=(start_date, end_date))

    return render(request, 'admin_panel/provider_commissions.html', {
        'commissions': commissions,
        'date_range': date_info["date_range"],
        'start_date': start_date,
        'end_date': end_date,
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
        if user and getattr(user, "role", None) in ("OWNER", "ADMIN", "superadmin"):
            auth_login(request, user)
            return redirect("admin_panel:admin_dashboard")
        messages.error(request, "Geçersiz giriş bilgileri.")
    return render(request, "admin_panel/login.html")

@login_required
@user_passes_test(is_superadmin)
def api_keys_view(request):
    clients = ClientSite.objects.all().select_related("api_key")
    return render(request, "admin_panel/api_keys.html", {"clients": clients})


@login_required
@user_passes_test(is_superadmin)
def generate_api_key(request, client_id):
    client = get_object_or_404(ClientSite, id=client_id)
    key = secrets.token_hex(32)
def pending_deposits(request):
    date_info = get_date_range_from_request(request)
    start_date = date_info["start_date"]
    end_date = date_info["end_date"]

    deposits = (
        DepositRequest.objects
        .filter(status="pending")
        .select_related("branch", "bank_account", "provider")
        .order_by("-created_at")
    )

    if start_date and end_date:
        deposits = deposits.filter(created_at__date__range=(start_date, end_date))

    # Filters (aligned with pending_withdrawals)
    user_name = request.GET.get("user_name")
    iban = request.GET.get("iban")
    site = request.GET.get("site")

    if user_name:
        deposits = deposits.filter(user_name__icontains=user_name)
    if iban:
        deposits = deposits.filter(bank_account__iban__icontains=iban)
    if site:
        deposits = deposits.filter(branch__name__icontains=site)

    context = {
        "deposits": deposits,
        "date_range": date_info["date_range"],
        "start_date": start_date,
        "end_date": end_date,
    }
    return render(request, "admin_panel/pending_deposits.html", context)

@login_required
@user_passes_test(is_superadmin)
def pending_withdrawals(request):
    date_info = get_date_range_from_request(request)
    start_date = date_info["start_date"]
    end_date = date_info["end_date"]

    withdrawals = (
        WithdrawalRequest.objects
        .filter(status="pending")
        .select_related("branch", "provider", "client")
        .order_by("-created_at")
    )

    if start_date and end_date:
        withdrawals = withdrawals.filter(created_at__date__range=(start_date, end_date))

    # Filters
    user_name = request.GET.get("user_name")
    iban = request.GET.get("iban")
    site = request.GET.get("site")

    if user_name:
        withdrawals = withdrawals.filter(user_name__icontains=user_name)
    if iban:
        withdrawals = withdrawals.filter(iban__icontains=iban)
    if site:
        withdrawals = withdrawals.filter(branch__name__icontains=site)

    providers = User.objects.filter(role=User.ROLE_PROVIDER).order_by("email")

    context = {
        "withdrawals": withdrawals,
        "providers": providers,
        "date_range": date_info["date_range"],
        "start_date": start_date,
        "end_date": end_date,
    }
    return render(request, "admin_panel/pending_withdrawals.html", context)


@login_required
@user_passes_test(is_superadmin)
@transaction.atomic
def assign_withdrawal_provider(request, withdrawal_id):
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id, status="pending")

    if request.method == "POST":
        provider_id = request.POST.get("provider_id")
        if not provider_id:
            messages.error(request, "Lütfen bir teminci seçin.")
        else:
            provider_user = get_object_or_404(User, id=provider_id, role=User.ROLE_PROVIDER)
            withdrawal.provider = provider_user
            withdrawal.save(update_fields=["provider"])
            messages.success(request, f"Çekim #{withdrawal.id} için teminci atandı.")

    return redirect("admin_panel:admin_pending_withdrawals")

@login_required
@user_passes_test(is_superadmin)
def add_client_site(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        domain = (request.POST.get("domain") or "").strip()
        contact_person = (request.POST.get("contact_person") or "").strip()
        contact_email = (request.POST.get("contact_email") or "").strip()
        deposit_commission = request.POST.get("deposit_commission") or "0"
        withdraw_commission = request.POST.get("withdraw_commission") or "0"

        branch_username = (request.POST.get("branch_username") or "").strip()
        branch_email = (request.POST.get("branch_email") or "").strip()
        branch_password = request.POST.get("branch_password") or ""
        callback_url = (request.POST.get("callback_url") or "").strip()

        if not branch_username or not branch_email or not branch_password:
            messages.error(request, "Site panel kullanıcısı için kullanıcı adı, email ve şifre zorunludur.")
            return render(request, "admin_panel/add_client_site.html")

        try:
            with transaction.atomic():
                # 1) Create BRANCH user for site panel login
                branch_user = User.objects.create_user(
                    username=branch_username,
                    email=branch_email,
                    password=branch_password,
                    role=User.ROLE_BRANCH,
                )

                # 2) Create Branch record (site/branch entity)
                branch = Branch.objects.create(
                    name=name,
                    domain=domain,
                    user=branch_user,
                    callback_url=callback_url,
                )

                # 3) Create financial settings record (ClientSite)
                ClientSite.objects.create(
                    name=name,
                    contact_email=contact_email,
                    deposit_commission_rate=float(deposit_commission or 0),
                    withdraw_commission_rate=float(withdraw_commission or 0),
                    branch=branch,
                )

                # 4) Create SiteGatewayConfig rows according to submitted checkboxes
                bank_enabled = bool(request.POST.get("gateway_bank"))
                crypto_enabled = bool(request.POST.get("gateway_crypto"))
                card_enabled = bool(request.POST.get("gateway_card"))

                SiteGatewayConfig.objects.update_or_create(
                    branch=branch,
                    gateway=GatewayType.BANK,
                    defaults={"is_enabled": bank_enabled},
                )
                SiteGatewayConfig.objects.update_or_create(
                    branch=branch,
                    gateway=GatewayType.CRYPTO,
                    defaults={"is_enabled": crypto_enabled},
                )
                SiteGatewayConfig.objects.update_or_create(
                    branch=branch,
                    gateway=GatewayType.CARD,
                    defaults={"is_enabled": card_enabled},
                )

            messages.success(
                request,
                "Site, panel kullanıcısı ve ayarlar başarıyla oluşturuldu.",
            )
            return redirect("admin_panel:siteler_list")
        except Exception as exc:
            messages.error(request, f"Site oluşturulurken bir hata oluştu: {exc}")

    return render(request, "admin_panel/add_client_site.html")

@login_required
@user_passes_test(is_superadmin)
def list_client_sites(request):
    sites = (
        ClientSite.objects
        .all()
        .select_related("branch", "branch__user")
        .prefetch_related("branch__gateway_configs")
        .order_by("name")
    )

    site_rows = []
    for site in sites:
        branch = getattr(site, "branch", None)
        gateway_configs = []
        if branch:
            ensure_branch_gateway_configs(branch)
            gateway_configs = branch.gateway_configs.order_by("gateway")
        site_rows.append(
            {
                "site": site,
                "branch": branch,
                "gateway_configs": gateway_configs,
                "public_urls": build_gateway_public_urls(branch) if branch else {},
            }
        )

    context = {"site_rows": site_rows}
    return render(request, "admin_panel/list_client_sites.html", context)


@login_required
@user_passes_test(is_superadmin)
def site_detail(request, branch_id):
    branch = get_object_or_404(Branch, pk=branch_id)
    ensure_branch_gateway_configs(branch)

    existing_configs = {
        cfg.gateway: cfg
        for cfg in SiteGatewayConfig.objects.filter(branch=branch)
    }

    if request.method == "POST":
        desired_states = {
            GatewayType.BANK: "gateway_bank" in request.POST,
            GatewayType.CRYPTO: "gateway_crypto" in request.POST,
            GatewayType.CARD: "gateway_card" in request.POST,
        }

        for gateway_code, is_enabled in desired_states.items():
            cfg = existing_configs.get(gateway_code)
            if cfg is None:
                cfg = SiteGatewayConfig(branch=branch, gateway=gateway_code)
                existing_configs[gateway_code] = cfg
            if cfg.is_enabled != is_enabled:
                cfg.is_enabled = is_enabled
                cfg.save(update_fields=["is_enabled"])

        messages.success(request, "Site gateway anahtarları güncellendi.")
        return redirect("admin_panel:site_detay", branch_id=branch.id)

    context = {
        "site": branch,
        "client_site": getattr(branch, "client_site", None),
        "gateway_bank_enabled": bool(
            existing_configs.get(GatewayType.BANK)
            and existing_configs[GatewayType.BANK].is_enabled
        ),
        "gateway_crypto_enabled": bool(
            existing_configs.get(GatewayType.CRYPTO)
            and existing_configs[GatewayType.CRYPTO].is_enabled
        ),
        "gateway_card_enabled": bool(
            existing_configs.get(GatewayType.CARD)
            and existing_configs[GatewayType.CARD].is_enabled
        ),
    }
    return render(request, "admin_panel/site_detay.html", context)


@login_required
@user_passes_test(is_superadmin)
def banka_genel_bakis(request):
    today = timezone.localdate()

    pending_deposits = DepositRequest.objects.filter(status="pending").count()
    pending_withdrawals = WithdrawalRequest.objects.filter(status="pending").count()
    active_accounts = BankAccount.objects.filter(is_active=True).count()
    # Provider model doesn't have `is_active`; use related user flag and provider block flag
    active_providers = Provider.objects.filter(
        user__is_provider_active_for_deposits=True,
        is_blocked=False,
    ).count()

    today_in = (
        PaymentTransaction.objects.filter(
            gateway=GatewayType.BANK,
            direction=PaymentTransaction.DIRECTION_IN,
            created_at__date=today,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )
    today_out = (
        PaymentTransaction.objects.filter(
            gateway=GatewayType.BANK,
            direction=PaymentTransaction.DIRECTION_OUT,
            created_at__date=today,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    recent_transactions = (
        PaymentTransaction.objects.filter(gateway=GatewayType.BANK)
        .select_related("branch")
        .order_by("-created_at")[:10]
    )

    context = {
        "pending_deposits": pending_deposits,
        "pending_withdrawals": pending_withdrawals,
        "active_accounts": active_accounts,
        "active_providers": active_providers,
        "today_in": today_in,
        "today_out": today_out,
        "recent_transactions": recent_transactions,
    }
    return render(request, "admin_panel/banka_genel_bakis.html", context)


@login_required
@user_passes_test(is_superadmin)
def kripto_genel_bakis(request):
    today = timezone.localdate()

    active_crypto_sites = SiteGatewayConfig.objects.filter(
        gateway=GatewayType.CRYPTO,
        is_enabled=True,
    ).count()
    active_wallets = CryptoWalletConfig.objects.filter(is_active=True).count()
    today_volume = (
        PaymentTransaction.objects.filter(
            gateway=GatewayType.CRYPTO,
            created_at__date=today,
            direction=PaymentTransaction.DIRECTION_IN,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    recent_tx = (
        PaymentTransaction.objects.filter(gateway=GatewayType.CRYPTO)
        .select_related("branch")
        .order_by("-created_at")[:20]
    )

    crypto_cfgs = SiteGatewayConfig.objects.filter(
        gateway=GatewayType.CRYPTO
    ).select_related("branch")
    site_rows = [
        {"site": cfg.branch, "enabled": cfg.is_enabled} for cfg in crypto_cfgs
    ]

    listener_active = bool(
        getattr(settings, "CRYPTO_TRON_EXPLORER_API_URL", None)
        and getattr(settings, "CRYPTO_TRON_EXPLORER_API_KEY", None)
    )

    context = {
        "active_crypto_sites": active_crypto_sites,
        "active_wallets": active_wallets,
        "today_volume": today_volume,
        "recent_tx": recent_tx,
        "site_rows": site_rows,
        "listener_active": listener_active,
    }
    return render(request, "admin_panel/kripto_genel_bakis.html", context)


@login_required
@user_passes_test(is_superadmin)
def kripto_koin_list(request):
    coins = CryptoWalletConfig.objects.select_related("branch").order_by(
        "-is_active", "coin", "network"
    )
    context = {"coins": coins}
    return render(request, "admin_panel/kripto_koin_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def kripto_koin_create(request):
    if request.method == "POST":
        form = CryptoWalletForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Yeni kripto koin adresi eklendi.")
            return redirect("admin_panel:kripto_koin_list")
    else:
        form = CryptoWalletForm()

    context = {"form": form}
    return render(request, "admin_panel/kripto_koin_form.html", context)


@login_required
@user_passes_test(is_superadmin)
def kripto_koin_edit(request, pk):
    coin_cfg = get_object_or_404(CryptoWalletConfig, pk=pk)
    if request.method == "POST":
        form = CryptoWalletForm(request.POST, instance=coin_cfg)
        if form.is_valid():
            form.save()
            messages.success(request, "Kripto koin adresi güncellendi.")
            return redirect("admin_panel:kripto_koin_list")
    else:
        form = CryptoWalletForm(instance=coin_cfg)

    context = {
        "form": form,
        "coin_cfg": coin_cfg,
    }
    return render(request, "admin_panel/kripto_koin_form.html", context)


@login_required
@user_passes_test(is_superadmin)
def kripto_koin_delete(request, pk):
    coin_cfg = get_object_or_404(CryptoWalletConfig, pk=pk)
    if request.method == "POST":
        coin_cfg.delete()
        messages.success(request, "Kripto koin kaydı silindi.")
        return redirect("admin_panel:kripto_koin_list")

    context = {"coin_cfg": coin_cfg}
    return render(request, "admin_panel/kripto_koin_delete_confirm.html", context)


@login_required
@user_passes_test(is_superadmin)
def kredi_karti_genel_bakis(request):
    today = timezone.localdate()

    active_card_sites = SiteGatewayConfig.objects.filter(
        gateway=GatewayType.CARD,
        is_enabled=True,
    ).count()
    today_volume = (
        PaymentTransaction.objects.filter(
            gateway=GatewayType.CARD,
            created_at__date=today,
            direction=PaymentTransaction.DIRECTION_IN,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    recent_tx = (
        PaymentTransaction.objects.filter(gateway=GatewayType.CARD)
        .select_related("branch")
        .order_by("-created_at")[:20]
    )

    card_cfgs = SiteGatewayConfig.objects.filter(
        gateway=GatewayType.CARD
    ).select_related("branch")
    site_rows = [
        {"site": cfg.branch, "enabled": cfg.is_enabled} for cfg in card_cfgs
    ]

    context = {
        "active_card_sites": active_card_sites,
        "today_volume": today_volume,
        "recent_tx": recent_tx,
        "site_rows": site_rows,
    }
    return render(request, "admin_panel/kredi_karti_genel_bakis.html", context)


@login_required
@user_passes_test(is_superadmin)
def kredi_karti_site_detay(request, branch_id):
    branch = get_object_or_404(Branch, pk=branch_id)
    card_psp = getattr(branch, "card_psp_config", None)
    card_enabled = SiteGatewayConfig.objects.filter(
        branch=branch, gateway=GatewayType.CARD, is_enabled=True
    ).exists()

    transactions = (
        PaymentTransaction.objects
        .filter(branch=branch, gateway=GatewayType.CARD)
        .order_by("-created_at")[:25]
    )
    gateway_links = build_gateway_public_urls(branch).get(GatewayType.CARD)

    context = {
        "site": branch,
        "card_psp": card_psp,
        "card_enabled": card_enabled,
        "transactions": transactions,
        "gateway_links": gateway_links,
    }
    return render(request, "admin_panel/kredi_karti_site_detay.html", context)


@login_required
@user_passes_test(is_superadmin)
def kripto_site_detay(request, branch_id):
    branch = get_object_or_404(Branch, pk=branch_id)
    crypto_enabled = SiteGatewayConfig.objects.filter(
        branch=branch, gateway=GatewayType.CRYPTO, is_enabled=True
    ).exists()

    wallets = CryptoWalletConfig.objects.filter(branch=branch).order_by("coin", "network")

    transactions = (
        PaymentTransaction.objects
        .filter(branch=branch, gateway=GatewayType.CRYPTO)
        .order_by("-created_at")[:25]
    )

    gateway_links = build_gateway_public_urls(branch).get(GatewayType.CRYPTO)

    context = {
        "site": branch,
        "crypto_enabled": crypto_enabled,
        "wallets": wallets,
        "transactions": transactions,
        "gateway_links": gateway_links,
    }
    return render(request, "admin_panel/kripto_site_detay.html", context)


@login_required
@user_passes_test(is_superadmin)
def site_gateway_list(request, site_id):
    site = get_object_or_404(ClientSite, id=site_id)
    branch = getattr(site, "branch", None)
    if branch is None:
        messages.error(request, "Bu site için bağlı bir branch bulunamadı.")
        return redirect("admin_panel:siteler_list")

    ensure_branch_gateway_configs(branch)
    gateway_configs = branch.gateway_configs.order_by("gateway")
    public_urls = build_gateway_public_urls(branch)

    context = {
        "site": site,
        "branch": branch,
        "gateway_configs": gateway_configs,
        "public_urls": public_urls,
    }
    return render(request, "admin_panel/site_gateway_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def site_gateway_edit(request, site_id, gateway):
    site = get_object_or_404(ClientSite, id=site_id)
    branch = getattr(site, "branch", None)
    if branch is None:
        messages.error(request, "Bu site için bağlı bir branch bulunamadı.")
        return redirect("admin_panel:list_client_sites")

    gateway_code = gateway.upper()
    ensure_branch_gateway_configs(branch)
    gateway_config = get_object_or_404(SiteGatewayConfig, branch=branch, gateway=gateway_code)

    if request.method == "POST":
        gateway_config.is_enabled = request.POST.get("is_enabled") == "on"
        gateway_config.save(update_fields=["is_enabled"])
        messages.success(
            request,
            f"{gateway_config.get_gateway_display()} gateway ayarı güncellendi.",
        )
        return redirect("admin_panel:site_gateway_list", site_id=site.id)

    context = {
        "site": site,
        "branch": branch,
        "gateway_config": gateway_config,
    }
    return render(request, "admin_panel/site_gateway_edit.html", context)


@login_required
@user_passes_test(is_superadmin)
def transactions_list(request):
    gateway = (request.GET.get("gateway") or "").upper()
    branch_id = request.GET.get("branch") or ""
    status = (request.GET.get("status") or "").lower()
    coin = (request.GET.get("coin") or "").upper()
    network = (request.GET.get("network") or "").upper()

    transactions = (
        PaymentTransaction.objects
        .select_related("branch", "crypto_payment")
        .order_by("-created_at")
    )

    if gateway:
        transactions = transactions.filter(gateway=gateway)
    if branch_id:
        transactions = transactions.filter(branch_id=branch_id)
    if status:
        transactions = transactions.filter(status=status)
    if coin:
        transactions = transactions.filter(
            gateway=GatewayType.CRYPTO,
            crypto_payment__coin=coin,
        )
    if network:
        transactions = transactions.filter(
            gateway=GatewayType.CRYPTO,
            crypto_payment__network=network,
        )

    context = {
        "transactions": transactions[:200],
        "branches": Branch.objects.order_by("name"),
        "gateway_choices": GatewayType.choices,
        "status_choices": PaymentTransaction.STATUS_CHOICES,
        "coin_choices": SUPPORTED_COINS,
        "network_choices": SUPPORTED_NETWORKS,
        "filters": {
            "gateway": gateway,
            "branch": branch_id,
            "status": status,
            "coin": coin,
            "network": network,
        },
    }
    return render(request, "admin_panel/transactions_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def crypto_wallet_create(request):
    form = CryptoWalletConfigForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        wallet = form.save()
        messages.success(request, f"{wallet.branch.name} için {wallet.coin}/{wallet.network} cüzdanı oluşturuldu.")
        return redirect("admin_panel:crypto_wallets")

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "admin_panel/crypto_wallet_form.html", context)


@login_required
@user_passes_test(is_superadmin)
def crypto_wallet_list(request):
    branch_filter = request.GET.get("branch")
    mode_filter = request.GET.get("mode")
    coin_filter = request.GET.get("coin")
    network_filter = request.GET.get("network")
    active_filter = request.GET.get("active")

    wallets = CryptoWalletConfig.objects.select_related("branch").order_by("branch__name", "coin", "network")
    if branch_filter:
        wallets = wallets.filter(branch_id=branch_filter)
    if mode_filter:
        wallets = wallets.filter(mode=mode_filter)
    if coin_filter:
        wallets = wallets.filter(coin=coin_filter)
    if network_filter:
        wallets = wallets.filter(network=network_filter)
    if active_filter in {"0", "1"}:
        wallets = wallets.filter(is_active=(active_filter == "1"))

    context = {
        "wallets": wallets,
        "branches": Branch.objects.order_by("name"),
        "wallet_modes": WalletMode.choices,
        "coin_choices": SUPPORTED_COINS,
        "network_choices": SUPPORTED_NETWORKS,
        "filters": {
            "branch": branch_filter or "",
            "mode": mode_filter or "",
            "coin": coin_filter or "",
            "network": network_filter or "",
            "active": active_filter or "",
        },
    }
    return render(request, "admin_panel/crypto_wallet_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def crypto_wallet_edit(request, pk):
    wallet = get_object_or_404(CryptoWalletConfig, pk=pk)
    form = CryptoWalletConfigForm(request.POST or None, instance=wallet)
    if request.method == "POST" and form.is_valid():
        wallet = form.save()
        messages.success(request, f"{wallet.branch.name} için {wallet.coin}/{wallet.network} cüzdanı güncellendi.")
        return redirect("admin_panel:crypto_wallets")

    context = {
        "form": form,
        "wallet": wallet,
        "is_edit": True,
    }
    return render(request, "admin_panel/crypto_wallet_form.html", context)


@login_required
@user_passes_test(is_superadmin)
def add_provider(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        deposit_commission = request.POST.get("deposit_commission")
        withdraw_commission = request.POST.get("withdraw_commission")
        limitor = request.POST.get("limitor")
        limitor = limitor.strip() if limitor else ""

        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        if not username or not email or not password:
            messages.error(request, "Teminci için kullanıcı adı, email ve şifre zorunludur.")
            return render(request, "admin_panel/add_provider.html")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Bu kullanıcı adı zaten kullanılıyor. Lütfen farklı bir kullanıcı adı deneyin.")
            return render(request, "admin_panel/add_provider.html")

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    role=User.ROLE_PROVIDER,
                )

                Provider.objects.create(
                    user=user,
                    name=name,
                    phone=phone,
                    deposit_commission=deposit_commission,
                    withdraw_commission=withdraw_commission,
                    limitor=limitor or None,
                )

            messages.success(request, "Teminci başarıyla oluşturuldu.")
            return redirect("admin_panel:provider_list")
        except Exception as exc:
            messages.error(request, f"Teminci oluşturulurken bir hata oluştu: {exc}")

    return render(request, "admin_panel/add_provider.html")

@login_required
@user_passes_test(is_superadmin)
def list_providers(request):
    providers = Provider.objects.select_related("user").all()
    return render(request, "admin_panel/list_providers.html", {"providers": providers})

@superadmin_required
def provider_list(request):
    providers = User.objects.filter(role__in=[User.ROLE_PROVIDER, "provider"]).select_related('provider_profile')

    summary = []
    for provider_user in providers:
        provider_profile = getattr(provider_user, 'provider_profile', None)

        total_deposits = DepositRequest.objects.filter(provider=provider_user, status='approved').count()
        total_withdrawals = WithdrawalRequest.objects.filter(provider=provider_user, status='approved').count()

        if provider_profile is not None:
            total_commission = ProviderCommission.objects.filter(
                provider=provider_profile,
                is_paid=True,
            ).aggregate(total=models.Sum('amount'))['total'] or 0
        else:
            total_commission = 0

        summary.append({
            'provider': provider_user,
            'deposits': total_deposits,
            'withdrawals': total_withdrawals,
            'commission': total_commission,
        })

    return render(request, 'admin_panel/provider_list.html', {
        'summary': summary
    })


@login_required
@user_passes_test(is_superadmin)
def provider_detail(request, provider_id):
    # Show provider financials including Teslimat (settlement) balance
    try:
        provider = Provider.objects.get(id=provider_id)
        user = provider.user
    except Provider.DoesNotExist:
        user = get_object_or_404(User, id=provider_id)
        provider = getattr(user, 'provider_profile', None)

    # Use shared helper to compute teslimat components
    from core.utils.settlements import compute_provider_settlement

    settlement = compute_provider_settlement(user)

    total_deposits = settlement.get('total_deposits') or Decimal('0')
    total_withdrawals = settlement.get('total_withdrawals') or Decimal('0')
    total_commission = settlement.get('total_commission') or Decimal('0')
    total_settlements = settlement.get('total_settlements') or Decimal('0')
    teslimat_balance = settlement.get('balance') or Decimal('0')

    context = {
        'provider': user,
        'provider_profile': provider,
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
        'total_commission': total_commission,
        'total_settlements': total_settlements,
        'teslimat_balance': teslimat_balance,
    }
    return render(request, 'admin_panel/provider_detail.html', context)


@login_required
@user_passes_test(is_superadmin)
def toggle_provider_active(request, provider_id):
    # Toggle is_provider_active_for_deposits on User
    try:
        provider = Provider.objects.get(id=provider_id)
        user = provider.user
    except Provider.DoesNotExist:
        user = get_object_or_404(User, id=provider_id)

    if request.method == 'POST':
        user.is_provider_active_for_deposits = not bool(user.is_provider_active_for_deposits)
        user.save(update_fields=['is_provider_active_for_deposits'])
        messages.success(request, 'Teminci durum güncellendi.')
    return redirect('admin_panel:provider_list')


@login_required
@user_passes_test(is_superadmin)
def add_settlement_payment(request, provider_id):
    # Create a ProviderSettlementPayment recorded by admin
    try:
        provider = Provider.objects.get(id=provider_id)
        user = provider.user
    except Provider.DoesNotExist:
        user = get_object_or_404(User, id=provider_id)
        provider = getattr(user, 'provider_profile', None)

    if request.method == 'POST':
        amount = request.POST.get('amount')
        note = request.POST.get('note') or ''
        try:
            amt = Decimal(str(amount))
        except Exception:
            messages.error(request, 'Geçersiz tutar.')
            return redirect('admin_panel:provider_detail', provider_id=provider_id)

        # Create settlement record
        from core.models import ProviderSettlementPayment

        ProviderSettlementPayment.objects.create(
            provider=user,
            amount=amt,
            note=note,
            created_by=request.user,
        )
        messages.success(request, 'Teslimat ödemesi kaydedildi.')
    return redirect('admin_panel:provider_detail', provider_id=provider_id)

@login_required
@user_passes_test(is_superadmin)
def edit_provider(request, provider_id):
    # Allow linking either by Provider PK or by Teminci User PK
    try:
        provider = Provider.objects.get(id=provider_id)
    except Provider.DoesNotExist:
        provider = get_object_or_404(Provider, user_id=provider_id)

    if request.method == 'POST':
        name = request.POST.get("name")
        phone = request.POST.get("phone")
        deposit_commission = request.POST.get("deposit_commission")
        withdraw_commission = request.POST.get("withdraw_commission")
        limitor = request.POST.get("limitor")
        limitor = limitor.strip() if limitor else ""
        new_password = (request.POST.get("new_password") or "").strip()

        provider.name = name
        provider.phone = phone
        provider.deposit_commission = deposit_commission
        provider.withdraw_commission = withdraw_commission
        provider.limitor = limitor or None
        provider.save()
        if new_password:
            if provider.user:
                provider.user.set_password(new_password)
                provider.user.save(update_fields=["password"])
        sync_provider_bank_states(provider)

        if new_password:
            messages.success(request, "Teminci ve şifresi başarıyla güncellendi.")
        else:
            messages.success(request, "Teminci başarıyla güncellendi.")
        return redirect("admin_panel:provider_list")

    return render(request, "admin_panel/edit_provider.html", {"provider": provider})

@login_required
@user_passes_test(is_superadmin)
def delete_provider(request, provider_id):
    try:
        provider = Provider.objects.get(id=provider_id)
    except Provider.DoesNotExist:
        provider = get_object_or_404(Provider, user_id=provider_id)

    if request.method == 'POST':
        provider.user.delete()  # also deletes related Provider via on_delete=CASCADE
        messages.success(request, "Teminci başarıyla silindi.")
        return redirect("admin_panel:provider_list")

    return render(request, "admin_panel/provider_delete_confirm.html", {"provider": provider})


@login_required
@superadmin_required
def admin_dashboard(request):
    ZERO = Decimal("0")
    HUNDRED = Decimal("100")

    date_info = get_date_range_from_request(request)
    start_date = date_info["start_date"]
    end_date = date_info["end_date"]

    site_id = (request.GET.get("site_id") or "").strip()
    provider_id = (request.GET.get("provider_id") or "").strip()

    approved_deposits = DepositRequest.objects.filter(status="approved")
    approved_withdrawals = WithdrawalRequest.objects.filter(status="approved")

    if start_date and end_date:
        approved_deposits = approved_deposits.filter(created_at__date__range=(start_date, end_date))
        approved_withdrawals = approved_withdrawals.filter(created_at__date__range=(start_date, end_date))

    if site_id:
        approved_deposits = approved_deposits.filter(client_id=site_id)
        approved_withdrawals = approved_withdrawals.filter(client_id=site_id)

    if provider_id:
        approved_deposits = approved_deposits.filter(provider_id=provider_id)
        approved_withdrawals = approved_withdrawals.filter(provider_id=provider_id)

    deposit_aggregates = approved_deposits.aggregate(
        total_amount=Sum("amount"), total_count=Count("id")
    )
    withdraw_aggregates = approved_withdrawals.aggregate(
        total_amount=Sum("amount"), total_count=Count("id")
    )

    total_deposit_amount = ensure_decimal(deposit_aggregates["total_amount"]) or ZERO
    total_deposit_count = deposit_aggregates["total_count"] or 0

    total_withdraw_amount = ensure_decimal(withdraw_aggregates["total_amount"]) or ZERO
    total_withdraw_count = withdraw_aggregates["total_count"] or 0

    site_stats, totals = build_site_commission_stats(approved_deposits, approved_withdrawals)
    site_summaries = sorted(
        site_stats.values(),
        key=lambda row: row["site_commission_total"],
        reverse=True,
    )

    total_site_commission = totals["total_site_commission"]
    total_teminci_commission = totals["total_teminci_commission"]
    total_system_commission = totals["total_system_commission"]
    total_liderpay_commission = totals["total_liderpay_commission"]

    total_transaction_volume = total_deposit_amount + total_withdraw_amount
    gateway_overview = build_gateway_overview()

    recent_deposits = approved_deposits.order_by("-created_at")[:5]
    recent_withdrawals = approved_withdrawals.order_by("-created_at")[:5]

    context = {
        "total_transaction_volume": total_transaction_volume,
        "total_deposit_amount": total_deposit_amount,
        "total_deposit_count": total_deposit_count,
        "total_withdraw_amount": total_withdraw_amount,
        "total_withdraw_count": total_withdraw_count,
        "total_site_commission": total_site_commission,
        "total_teminci_commission": total_teminci_commission,
        "total_system_commission": total_system_commission,
        "total_liderpay_commission": total_liderpay_commission,
        "site_summaries": site_summaries,
        "site_count": Client.objects.count(),
        "recent_deposits": recent_deposits,
        "recent_withdrawals": recent_withdrawals,
        "date_range": date_info["date_range"],
        "start_date": start_date,
        "end_date": end_date,
        "gateway_overview": gateway_overview,
    }

    return render(request, "admin_panel/dashboard.html", context)


@login_required
@superadmin_required
def gateway_matrix(request):
    branches = Branch.objects.select_related("user").prefetch_related("gateway_configs").order_by("name")

    # Ensure every branch has configs for all gateways
    for branch in branches:
        ensure_branch_gateway_configs(branch)

    if request.method == "POST":
        branch_id = request.POST.get("branch_id")
        gateway_code = (request.POST.get("gateway") or "").upper()
        if branch_id and gateway_code in dict(GatewayType.choices):
            config = SiteGatewayConfig.objects.filter(branch_id=branch_id, gateway=gateway_code).first()
            if config:
                config.is_enabled = not config.is_enabled
                config.save(update_fields=["is_enabled"])
                messages.success(
                    request,
                    f"{config.branch.name} için {config.get_gateway_display()} gateway durumu {'AKTİF' if config.is_enabled else 'PASİF'} yapıldı.",
                )
        return redirect("admin_panel:gateways_matrix")

    configs = SiteGatewayConfig.objects.select_related("branch")
    config_lookup = defaultdict(dict)
    for cfg in configs:
        config_lookup[cfg.branch_id][cfg.gateway] = cfg

    branch_rows = []
    for branch in branches:
        gateway_entries = []
        branch_configs = config_lookup.get(branch.id, {})
        for gateway_code, gateway_label in GatewayType.choices:
            gateway_entries.append(
                {
                    "code": gateway_code,
                    "label": gateway_label,
                    "config": branch_configs.get(gateway_code),
                }
            )
        branch_rows.append({"branch": branch, "gateways": gateway_entries})

    context = {
        "branch_rows": branch_rows,
        "gateways": GatewayType.choices,
    }
    return render(request, "admin_panel/gateways_matrix.html", context)


@login_required
@superadmin_required
def gateway_branch_detail(request, branch_id):
    branch = get_object_or_404(Branch, pk=branch_id)
    ensure_branch_gateway_configs(branch)

    gateway_configs = {
        cfg.gateway: cfg for cfg in branch.gateway_configs.all()
    }
    card_psp_instance = getattr(branch, "card_psp_config", None)
    card_psp_form = CardPspConfigForm(instance=card_psp_instance)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "toggle_gateway":
            gateway_code = (request.POST.get("gateway") or "").upper()
            desired_state = request.POST.get("is_enabled") == "1"
            config = gateway_configs.get(gateway_code)
            if config:
                config.is_enabled = desired_state
                config.save(update_fields=["is_enabled"])
                messages.success(
                    request,
                    f"{branch.name} için {config.get_gateway_display()} gateway durumu {'AKTİF' if desired_state else 'PASİF'} olarak ayarlandı.",
                )
            return redirect("admin_panel:gateway_branch_detail", branch_id=branch.id)
        elif action == "update_card_psp":
            card_psp_form = CardPspConfigForm(request.POST, instance=card_psp_instance)
            if card_psp_form.is_valid():
                card_psp = card_psp_form.save(commit=False)
                card_psp.branch = branch
                card_psp.save()
                messages.success(request, "Kart PSP ayarları güncellendi.")
                return redirect("admin_panel:gateway_branch_detail", branch_id=branch.id)
            else:
                messages.error(request, "Kart PSP ayarları güncellenemedi. Lütfen formu kontrol edin.")
        else:
            messages.error(request, "Geçersiz işlem.")
    else:
        card_psp_form = CardPspConfigForm(instance=card_psp_instance)

    crypto_wallets = branch.crypto_wallets.order_by("coin", "network")

    gateway_cards = []
    for code, label in GatewayType.choices:
        gateway_cards.append(
            {
                "code": code,
                "label": label,
                "config": gateway_configs.get(code),
            }
        )

    context = {
        "branch": branch,
        "gateway_cards": gateway_cards,
        "crypto_wallets": crypto_wallets,
        "card_psp_form": card_psp_form,
        "card_psp_config": card_psp_instance,
    }
    return render(request, "admin_panel/gateway_branch_detail.html", context)


@login_required
@superadmin_required
def crypto_overview(request):
    listener_active = bool(getattr(settings, "CRYPTO_TRON_EXPLORER_API_URL", ""))
    listener_status = (
        "TRC20 listener: ACTIVE" if listener_active else "TRC20 listener: DISABLED"
    )

    wallets = (
        CryptoWalletConfig.objects.select_related("branch")
        .order_by("branch__name", "coin", "network")
    )

    last_deposits = (
        CryptoPayment.objects.filter(direction=CryptoPayment.DIRECTION_IN)
        .values("branch_id", "coin", "network")
        .annotate(last_created=Max("created_at"))
    )
    last_deposit_map = {
        (entry["branch_id"], entry["coin"], entry["network"]): entry["last_created"]
        for entry in last_deposits
    }

    for wallet in wallets:
        wallet.last_deposit_at = last_deposit_map.get(
            (wallet.branch_id, wallet.coin, wallet.network)
        )

    context = {
        "listener_status": listener_status,
        "wallets": wallets,
    }
    return render(request, "admin_panel/crypto_overview.html", context)


@login_required
@superadmin_required
def pending_deposits_legacy(request):
    deposits = DepositRequest.objects.filter(status='pending').order_by('-created_at')
    return render(request, 'admin_panel/pending_deposits.html', {'deposits': deposits})

@login_required
@superadmin_required
def approve_deposit(request, deposit_id):
    deposit = get_object_or_404(DepositRequest, id=deposit_id)
    deposit.status = 'approved'
    deposit.save()
    sync_bank_active_state(deposit.bank_account)
    sync_provider_bank_states(deposit.provider)
    messages.success(request, "Yatırım onaylandı.")
    return redirect('pending_deposits')


@login_required
@user_passes_test(is_superadmin)
def toggle_bank_account_active(request, account_id):
    from core.models import BankAccount

    account = get_object_or_404(BankAccount, pk=account_id)
    if request.method == 'POST':
        account.is_active = not bool(account.is_active)
        account.save(update_fields=['is_active'])
        messages.success(request, 'Banka hesabı durum güncellendi.')
    return redirect('admin_panel:list_bank_accounts')


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


@login_required
@superadmin_required
def provider_report(request):
    date_info = get_date_range_from_request(request)
    start_date = date_info["start_date"]
    end_date = date_info["end_date"]

    approved_deposits = DepositRequest.objects.filter(status="approved")
    approved_withdrawals = WithdrawalRequest.objects.filter(status="approved")

    if start_date and end_date:
        approved_deposits = approved_deposits.filter(created_at__date__range=(start_date, end_date))
        approved_withdrawals = approved_withdrawals.filter(created_at__date__range=(start_date, end_date))

    provider_data = []

    for provider in Provider.objects.select_related("user"):
        user = provider.user

        deposit_total = approved_deposits.filter(provider=user).aggregate(total=Sum("amount"))['total'] or Decimal("0")
        withdraw_total = approved_withdrawals.filter(provider=user).aggregate(total=Sum("amount"))['total'] or Decimal("0")

        commissions_qs = ProviderCommission.objects.filter(provider=provider)
        if start_date and end_date:
            commissions_qs = commissions_qs.filter(created_at__date__range=(start_date, end_date))

        earned = commissions_qs.aggregate(total=Sum("amount"))['total'] or Decimal("0")
        paid = commissions_qs.filter(is_paid=True).aggregate(total=Sum("amount"))['total'] or Decimal("0")
        balance = earned - paid

        provider_data.append({
            'provider': user,
            'deposits': deposit_total,
            'withdrawals': withdraw_total,
            'earned': earned,
            'paid': paid,
            'balance': balance,
        })

    context = {
        'provider_data': provider_data,
        'date_range': date_info["date_range"],
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'admin_panel/provider_report.html', context)


@login_required
@superadmin_required
def financial_reports(request):
    date_info = get_date_range_from_request(request)
    start_date = date_info["start_date"]
    end_date = date_info["end_date"]

    site_id = (request.GET.get("site_id") or "").strip()
    provider_id = (request.GET.get("provider_id") or "").strip()

    # Base approved transactions in selected date window
    approved_deposits = DepositRequest.objects.filter(status="approved")
    approved_withdrawals = WithdrawalRequest.objects.filter(status="approved")

    if start_date and end_date:
        approved_deposits = approved_deposits.filter(created_at__date__range=(start_date, end_date))
        approved_withdrawals = approved_withdrawals.filter(created_at__date__range=(start_date, end_date))

    if site_id:
        approved_deposits = approved_deposits.filter(client_id=site_id)
        approved_withdrawals = approved_withdrawals.filter(client_id=site_id)

    if provider_id:
        approved_deposits = approved_deposits.filter(provider_id=provider_id)
        approved_withdrawals = approved_withdrawals.filter(provider_id=provider_id)

    site_stats, totals = build_site_commission_stats(approved_deposits, approved_withdrawals)
    site_data = []
    site_summaries = []

    for entry in site_stats.values():
        site_data.append({
            "site_name": entry["site_name"],
            "deposits": entry["deposit_amount"],
            "withdrawals": entry["withdraw_amount"],
            "total_earned": entry["site_commission_total"],
        })

        site_summaries.append(entry)

    site_data.sort(key=lambda row: row["total_earned"], reverse=True)
    site_summaries.sort(key=lambda row: row["site_commission_total"], reverse=True)

    # --- Provider-based aggregation (Teminci) ---
    provider_data = []
    provider_comm_total = ZERO

    provider_qs = Provider.objects.select_related("user")
    if provider_id:
        provider_qs = provider_qs.filter(user_id=provider_id)

    for provider in provider_qs:
        user = provider.user

        deposit_total = approved_deposits.filter(provider=user).aggregate(total=Sum("amount"))['total'] or ZERO
        withdraw_total = approved_withdrawals.filter(provider=user).aggregate(total=Sum("amount"))['total'] or ZERO

        commissions_qs = ProviderCommission.objects.filter(provider=provider)
        if start_date and end_date:
            commissions_qs = commissions_qs.filter(created_at__date__range=(start_date, end_date))

        earned = commissions_qs.aggregate(total=Sum("amount"))['total'] or ZERO
        paid = commissions_qs.filter(is_paid=True).aggregate(total=Sum("amount"))['total'] or ZERO
        balance = earned - paid

        provider_comm_total += earned

        provider_data.append({
            'provider': user,
            'deposits': deposit_total,
            'withdrawals': withdraw_total,
            'earned': earned,
            'paid': paid,
            'balance': balance,
        })

    net_profit = total_liderpay_commission + total_system_commission

    sites = Client.objects.all().order_by("name")
    providers = Provider.objects.select_related("user").order_by("user__email")

    context = {
        'date_range': date_info["date_range"],
        'start_date': start_date,
        'end_date': end_date,
        'site_data': site_data,
        'provider_data': provider_data,
        'site_comm_total': totals["total_site_commission"],
        'total_site_commission': totals["total_site_commission"],
        'total_teminci_commission': totals["total_teminci_commission"],
        'total_system_commission': totals["total_system_commission"],
        'total_liderpay_commission': totals["total_liderpay_commission"],
        'provider_comm_total': provider_comm_total,
        'net_profit': net_profit,
        'site_summaries': site_summaries,
        'sites': sites,
        'providers': providers,
        'selected_site_id': site_id,
        'selected_provider_id': provider_id,
    }
    return render(request, 'admin_panel/financial_reports.html', context)

@login_required
@superadmin_required
def site_finance_report(request):
    return render(request, "admin_panel/site_finance_report.html")

@login_required
@superadmin_required
def commission_report(request):
    date_info = get_date_range_from_request(request)
    start_date = date_info["start_date"]
    end_date = date_info["end_date"]

    site_id = (request.GET.get("site_id") or "").strip()
    provider_id = (request.GET.get("provider_id") or "").strip()

    approved_deposits = DepositRequest.objects.filter(status="approved")
    approved_withdrawals = WithdrawalRequest.objects.filter(status="approved")

    if start_date and end_date:
        approved_deposits = approved_deposits.filter(created_at__date__range=(start_date, end_date))
        approved_withdrawals = approved_withdrawals.filter(created_at__date__range=(start_date, end_date))

    if site_id:
        approved_deposits = approved_deposits.filter(client_id=site_id)
        approved_withdrawals = approved_withdrawals.filter(client_id=site_id)

    if provider_id:
        approved_deposits = approved_deposits.filter(provider_id=provider_id)
        approved_withdrawals = approved_withdrawals.filter(provider_id=provider_id)

    site_stats, totals = build_site_commission_stats(approved_deposits, approved_withdrawals)
    site_summaries = sorted(
        site_stats.values(),
        key=lambda row: row["site_commission_total"],
        reverse=True,
    )

    sites = Client.objects.all().order_by("name")
    providers = Provider.objects.select_related("user").order_by("user__email")

    context = {
        "site_summaries": site_summaries,
        "total_site_commission": totals["total_site_commission"],
        "total_teminci_commission": totals["total_teminci_commission"],
        "total_system_commission": totals["total_system_commission"],
        "total_liderpay_commission": totals["total_liderpay_commission"],
        "date_range": date_info["date_range"],
        "start_date": start_date,
        "end_date": end_date,
        "sites": sites,
        "providers": providers,
        "selected_site_id": site_id,
        "selected_provider_id": provider_id,
    }

    return render(request, "admin_panel/commission_report.html", context)

@login_required
@superadmin_required
def add_admin(request):
    return render(request, "admin_panel/add_admin.html")

@login_required
@superadmin_required
def manage_admins(request):
    admins = (
        UserModel.objects
        .filter(role__in=[UserModel.ROLE_ADMIN, UserModel.ROLE_OWNER])
        .order_by('-last_login', '-date_joined')
    )
    return render(request, "admin_panel/manage_admins.html", {
        "admins": admins,
    })

@login_required
@superadmin_required
def admin_logs(request):
    logs = (
        LogEntry.objects
        .select_related("user", "content_type")
        .order_by("-action_time")[:200]
    )
    return render(request, "admin_panel/admin_logs.html", {
        "logs": logs,
    })

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
            return redirect("admin_panel:siteler_list")
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
