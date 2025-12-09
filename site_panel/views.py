import json
import secrets

from django.conf import settings
from django.shortcuts import render, redirect
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, get_user_model
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.urls import reverse
from datetime import timedelta
from decimal import Decimal

from core.decorators import branch_required
from branches.models import Branch
from core.models import (
    DepositRequest,
    WithdrawalRequest,
    ClientSite,
    BankAccount,
    GatewayType,
    PaymentTransaction,
)
from core.services.payment_transactions import create_payment_transaction_for_deposit
from core.utils.gateways import get_branch_gateway_flags, build_gateway_public_urls
from site_panel.forms import SiteDepositLinkForm, NotificationSettingsForm
from crypto.models import CryptoWalletConfig, WalletMode


User = get_user_model()


def _decimal(value):
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or "0"))

def _inject_gateway_flags(context, branch):
    context.setdefault("branch", branch)
    flags = get_branch_gateway_flags(branch)
    context["gateway_flags"] = flags
    context["gateway_bank_enabled"] = flags.get(GatewayType.BANK, False)
    context["gateway_card_enabled"] = flags.get(GatewayType.CARD, False)
    context["gateway_crypto_enabled"] = flags.get(GatewayType.CRYPTO, False)
    context["gateway_public_urls"] = build_gateway_public_urls(branch)
    return context


def _build_card_psp_context(branch):
    card_gateway_config = branch.gateway_configs.filter(gateway=GatewayType.CARD).first()
    card_psp = getattr(branch, "card_psp_config", None)

    supported_raw = getattr(card_psp, "supported_currencies", None) if card_psp else None
    if supported_raw:
        if isinstance(supported_raw, (list, tuple)):
            supported_currencies = [curr.strip().upper() for curr in supported_raw if curr]
        else:
            supported_currencies = [curr.strip().upper() for curr in str(supported_raw).split(",") if curr.strip()]
    else:
        supported_currencies = ["TRY"]

    return {
        "branch": branch,
        "card_gateway_config": card_gateway_config,
        "card_psp": card_psp,
        "card_enabled": bool(card_gateway_config and card_gateway_config.is_enabled),
        "supported_currencies": supported_currencies,
    }


@branch_required
def dashboard(request):
    branch = request.user.branch_profile  # from Branch.user OneToOne
    today = timezone.now().date()

    range_key = (request.GET.get("range") or "today").lower()
    custom_start_str = (request.GET.get("start_date") or "").strip()
    custom_end_str = (request.GET.get("end_date") or "").strip()

    start_date = end_date = None
    range_label = ""

    if range_key == "today":
        start_date = end_date = today
        range_label = "Bugün"
    elif range_key == "yesterday":
        day = today - timedelta(days=1)
        start_date = end_date = day
        range_label = "Dün"
    elif range_key == "last7":
        start_date = today - timedelta(days=7)
        end_date = today
        range_label = "Son 7 Gün"
    elif range_key == "this_month":
        start_date = today.replace(day=1)
        end_date = today
        range_label = "Bu Ay"
    elif range_key == "last_month":
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        start_date = last_month_end.replace(day=1)
        end_date = last_month_end
        range_label = "Geçen Ay"
    elif range_key == "custom":
        start_date = parse_date(custom_start_str) if custom_start_str else None
        end_date = parse_date(custom_end_str) if custom_end_str else None
        range_label = "Özel Aralık"
    else:
        range_key = "all"
        range_label = "Tüm Zamanlar"

    deposits_qs = DepositRequest.objects.filter(branch=branch, status="approved")
    withdrawals_qs = WithdrawalRequest.objects.filter(branch=branch, status="approved")

    if start_date:
        deposits_qs = deposits_qs.filter(created_at__date__gte=start_date)
        withdrawals_qs = withdrawals_qs.filter(created_at__date__gte=start_date)
    if end_date:
        deposits_qs = deposits_qs.filter(created_at__date__lte=end_date)
        withdrawals_qs = withdrawals_qs.filter(created_at__date__lte=end_date)

    total_deposits_amount = deposits_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_deposits_count = deposits_qs.count()
    total_withdrawals_amount = withdrawals_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_withdrawals_count = withdrawals_qs.count()

    ZERO = Decimal("0")
    HUNDRED = Decimal("100")

    deposit_rate = Decimal(str(getattr(branch, "deposit_commission_rate", 0) or 0))
    withdraw_rate = Decimal(str(getattr(branch, "withdraw_commission_rate", 0) or 0))

    deposit_commission_total = (total_deposits_amount * deposit_rate) / HUNDRED
    withdraw_commission_total = (total_withdrawals_amount * withdraw_rate) / HUNDRED
    commission_total = deposit_commission_total + withdraw_commission_total
    balance_amount = total_deposits_amount - total_withdrawals_amount - commission_total

    pending_deposits = DepositRequest.objects.filter(branch=branch, status="pending").order_by("-created_at")[:10]
    pending_withdrawals = WithdrawalRequest.objects.filter(branch=branch, status="pending").order_by("-created_at")[:10]

    stats = {
        "range_key": range_key,
        "range_label": range_label,
        "filter_start": custom_start_str,
        "filter_end": custom_end_str,
        "total_deposits_amount": total_deposits_amount,
        "total_deposits_count": total_deposits_count,
        "total_withdrawals_amount": total_withdrawals_amount,
        "total_withdrawals_count": total_withdrawals_count,
        "commission_total": commission_total,
        "balance_amount": balance_amount,
        "deposit_rate": deposit_rate,
        "withdraw_rate": withdraw_rate,
    }

    range_options = [
        ("today", "Bugün"),
        ("yesterday", "Dün"),
        ("last7", "Son 7 Gün"),
        ("this_month", "Bu Ay"),
        ("last_month", "Geçen Ay"),
        ("custom", "Özel Aralık"),
        ("all", "Tüm Zamanlar"),
    ]

    context = {
        "branch": branch,
        "stats": stats,
        "range_options": range_options,
        "pending_deposits": pending_deposits,
        "pending_withdrawals": pending_withdrawals,
        "form": SiteDepositLinkForm(
            bank_account_qs=BankAccount.objects.filter(is_active=True)
        ),
        "notification_form": NotificationSettingsForm(instance=branch),
    }
    context = _inject_gateway_flags(context, branch)

    gateway_flags = context.get("gateway_flags", {})
    gateway_configs = {
        cfg.gateway: cfg for cfg in branch.gateway_configs.all()
    }
    today_transactions = PaymentTransaction.objects.filter(
        branch=branch,
        created_at__date=today,
    )

    preferred_crypto_wallet = (
        branch.crypto_wallets.filter(is_active=True, coin="USDT", network="TRC20").first()
        or branch.crypto_wallets.filter(is_active=True).order_by("coin", "network").first()
    )
    last_crypto_tx = (
        PaymentTransaction.objects.filter(
            branch=branch,
            gateway=GatewayType.CRYPTO,
            direction=PaymentTransaction.DIRECTION_IN,
        )
        .order_by("-created_at")
        .first()
    )

    quick_links = {
        GatewayType.BANK: [
            {"label": "Bank Yatırımlar", "url": reverse("site_panel:deposits")},
            {"label": "Bank Çekimler", "url": reverse("site_panel:withdrawals")},
        ],
        GatewayType.CARD: [
            {"label": "Kart Ayarları", "url": reverse("site_panel:kart_ayarlari")},
        ],
        GatewayType.CRYPTO: [
            {"label": "Kripto Cüzdanları", "url": reverse("site_panel:kripto_cuzdanlar")},
        ],
    }
    detail_routes = {
        GatewayType.BANK: "site_panel:banka_havale",
        GatewayType.CARD: "site_panel:kart_ayarlari",
        GatewayType.CRYPTO: "site_panel:kripto_cuzdanlar",
    }

    gateway_status = {}
    icons = {
        GatewayType.BANK: "🏦",
        GatewayType.CARD: "💳",
        GatewayType.CRYPTO: "🪙",
    }

    for code, label in GatewayType.choices:
        config = gateway_configs.get(code)
        enabled = bool(config and config.is_enabled)

        code_transactions = today_transactions.filter(gateway=code)
        in_stats = code_transactions.filter(direction=PaymentTransaction.DIRECTION_IN).aggregate(
            count=Count("id"), total=Sum("amount")
        )
        out_stats = code_transactions.filter(direction=PaymentTransaction.DIRECTION_OUT).aggregate(
            count=Count("id"), total=Sum("amount")
        )

        detail_name = detail_routes.get(code)
        detail_url = reverse(detail_name) if detail_name else ""
        entry = {
            "code": code,
            "label": label,
            "enabled": enabled,
            "icon": icons.get(code, "⚙️"),
            "today_in_count": in_stats["count"] or 0,
            "today_in_total": _decimal(in_stats["total"]),
            "today_out_count": out_stats["count"] or 0,
            "today_out_total": _decimal(out_stats["total"]),
            "links": quick_links.get(code, []),
            "detail_url": detail_url,
        }
        entry["today_in"] = entry["today_in_total"]

        if code == GatewayType.CRYPTO:
            entry.update(
                {
                    "mode": preferred_crypto_wallet.get_mode_display() if preferred_crypto_wallet else None,
                    "coin": preferred_crypto_wallet.coin if preferred_crypto_wallet else None,
                    "network": preferred_crypto_wallet.network if preferred_crypto_wallet else None,
                    "last_deposit_at": last_crypto_tx.created_at if last_crypto_tx else None,
                }
            )

        if code == GatewayType.CARD:
            entry["mode"] = getattr(getattr(branch, "card_psp_config", None), "mode", "TEST")

        gateway_status[code] = entry

    today_stats = {
        "bank_in": gateway_status.get(GatewayType.BANK, {}).get("today_in_total", Decimal("0")),
        "crypto_in": gateway_status.get(GatewayType.CRYPTO, {}).get("today_in_total", Decimal("0")),
        "card_in": gateway_status.get(GatewayType.CARD, {}).get("today_in_total", Decimal("0")),
    }

    raw_public_urls = context.get("gateway_public_urls", {})
    payment_base = getattr(settings, "PAYMENT_BASE_URL", "").rstrip("/")
    public_urls = {}
    for code, label in GatewayType.choices:
        if not gateway_flags.get(code):
            continue
        raw = raw_public_urls.get(code)
        if not raw:
            continue
        deposit_path = raw.get("deposit")
        if not deposit_path:
            continue
        if payment_base:
            deposit_url = f"{payment_base}{deposit_path}"
        else:
            deposit_url = request.build_absolute_uri(deposit_path)
        public_urls[f"{code}_DEPOSIT"] = deposit_url

    pending_transactions = list(
        PaymentTransaction.objects.filter(
            branch=branch,
            status=PaymentTransaction.STATUS_PENDING,
        )
        .order_by("-created_at")[:10]
    )

    context.update(
        {
            "gateway_status": gateway_status,
            "today_stats": today_stats,
            "public_urls": public_urls,
            "pending_transactions": pending_transactions,
        }
    )

    return render(request, "site_panel/dashboard.html", context)


@branch_required
def deposit_list(request):
    branch = request.user.branch_profile
    qs = DepositRequest.objects.filter(branch=branch)

    # Basic filters by date range and status
    start_str = (request.GET.get("start_date") or "").strip()
    end_str = (request.GET.get("end_date") or "").strip()
    status = (request.GET.get("status") or "").strip()
    search_query = (request.GET.get("q") or "").strip()

    if start_str:
        start_date = parse_date(start_str)
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)

    if end_str:
        end_date = parse_date(end_str)
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)

    if status:
        qs = qs.filter(status=status)

    if search_query:
        search_filter = Q(user_name__icontains=search_query) | Q(external_user_id__icontains=search_query)
        if search_query.isdigit():
            search_filter |= Q(id=int(search_query))
        qs = qs.filter(search_filter)

    filters = {
        "start_date": start_str,
        "end_date": end_str,
        "status": status,
        "query": search_query,
    }

    deposits = qs.order_by("-created_at")
    context = {
        "branch": branch,
        "deposits": deposits,
        "filters": filters,
        "status_choices": DepositRequest.STATUS_CHOICES,
    }
    return render(request, "site_panel/deposits.html", _inject_gateway_flags(context, branch))


@branch_required
def withdrawal_list(request):
    branch = request.user.branch_profile
    qs = WithdrawalRequest.objects.filter(branch=branch)

    # Basic filters by date range and status
    start_str = (request.GET.get("start_date") or "").strip()
    end_str = (request.GET.get("end_date") or "").strip()
    status = (request.GET.get("status") or "").strip()
    search_query = (request.GET.get("q") or "").strip()

    if start_str:
        start_date = parse_date(start_str)
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)

    if end_str:
        end_date = parse_date(end_str)
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)

    if status:
        qs = qs.filter(status=status)

    if search_query:
        search_filter = Q(user_name__icontains=search_query) | Q(iban__icontains=search_query)
        if search_query.isdigit():
            search_filter |= Q(id=int(search_query))
        qs = qs.filter(search_filter)

    filters = {
        "start_date": start_str,
        "end_date": end_str,
        "status": status,
        "query": search_query,
    }

    withdrawals = qs.order_by("-created_at")
    context = {
        "branch": branch,
        "withdrawals": withdrawals,
        "filters": filters,
        "status_choices": WithdrawalRequest.STATUS_CHOICES,
    }
    return render(request, "site_panel/withdrawals.html", _inject_gateway_flags(context, branch))


@branch_required
def bank_accounts(request):
    branch = request.user.branch_profile

    provider_ids = (
        DepositRequest.objects.filter(branch=branch)
        .values_list("provider_id", flat=True)
        .distinct()
    )

    accounts = BankAccount.objects.filter(is_active=True)
    if provider_ids:
        accounts = accounts.filter(provider_id__in=provider_ids)

    accounts = accounts.order_by("bank_name", "iban")

    context = {
        "branch": branch,
        "accounts": accounts,
    }
    return render(request, "site_panel/bank_accounts.html", _inject_gateway_flags(context, branch))


@branch_required
def reports(request):
    branch = request.user.branch_profile

    today = timezone.now().date()
    range_key = (request.GET.get("range") or "today").lower()
    custom_start_str = (request.GET.get("start_date") or "").strip()
    custom_end_str = (request.GET.get("end_date") or "").strip()

    start_date = end_date = None
    range_label = ""

    if range_key == "today":
        start_date = end_date = today
        range_label = "Bugün"
    elif range_key == "yesterday":
        day = today - timedelta(days=1)
        start_date = end_date = day
        range_label = "Dün"
    elif range_key == "last7":
        start_date = today - timedelta(days=7)
        end_date = today
        range_label = "Son 7 Gün"
    elif range_key == "this_month":
        start_date = today.replace(day=1)
        end_date = today
        range_label = "Bu Ay"
    elif range_key == "last_month":
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        start_date = last_month_end.replace(day=1)
        end_date = last_month_end
        range_label = "Geçen Ay"
    elif range_key == "custom":
        start_date = parse_date(custom_start_str) if custom_start_str else None
        end_date = parse_date(custom_end_str) if custom_end_str else None
        range_label = "Özel Aralık"
    else:
        range_key = "all"
        range_label = "Tüm Zamanlar"

    deposits_qs = DepositRequest.objects.filter(branch=branch, status="approved")
    withdrawals_qs = WithdrawalRequest.objects.filter(branch=branch, status="approved")

    if start_date:
        deposits_qs = deposits_qs.filter(created_at__date__gte=start_date)
        withdrawals_qs = withdrawals_qs.filter(created_at__date__gte=start_date)
    if end_date:
        deposits_qs = deposits_qs.filter(created_at__date__lte=end_date)
        withdrawals_qs = withdrawals_qs.filter(created_at__date__lte=end_date)

    total_deposits_amount = deposits_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_deposits_count = deposits_qs.count()
    total_withdrawals_amount = withdrawals_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_withdrawals_count = withdrawals_qs.count()

    client_site = ClientSite.objects.filter(name=branch.name).first()
    deposit_rate = Decimal(str(getattr(client_site, "deposit_commission_rate", 0) or 0))
    withdraw_rate = Decimal(str(getattr(client_site, "withdraw_commission_rate", 0) or 0))

    ZERO = Decimal("0")
    HUNDRED = Decimal("100")
    TEMINCI_SHARE = Decimal("0.03")   # 3% of volume
    SYSTEM_SHARE = Decimal("0.002")   # 0.2% of volume

    # Raw site commissions from configured percentages
    deposit_commission_total = (total_deposits_amount * deposit_rate) / HUNDRED
    withdraw_commission_total = (total_withdrawals_amount * withdraw_rate) / HUNDRED
    site_commission_total = deposit_commission_total + withdraw_commission_total

    # Deposit-side split
    deposit_teminci_commission = ZERO
    deposit_system_commission = ZERO
    deposit_liderpay_commission = deposit_commission_total

    if total_deposits_amount > ZERO and deposit_rate > ZERO:
        theoretical_deposit_teminci = total_deposits_amount * TEMINCI_SHARE
        theoretical_deposit_system = total_deposits_amount * SYSTEM_SHARE
        theoretical_needed = theoretical_deposit_teminci + theoretical_deposit_system

        if deposit_commission_total >= theoretical_needed:
            deposit_teminci_commission = theoretical_deposit_teminci
            deposit_system_commission = theoretical_deposit_system
            deposit_liderpay_commission = deposit_commission_total - theoretical_needed

    # Withdraw-side split (only Sistem + Lider Pay)
    withdraw_teminci_commission = ZERO
    withdraw_system_commission = ZERO
    withdraw_liderpay_commission = withdraw_commission_total

    if total_withdrawals_amount > ZERO and withdraw_rate > ZERO:
        theoretical_withdraw_system = total_withdrawals_amount * SYSTEM_SHARE
        if withdraw_commission_total >= theoretical_withdraw_system:
            withdraw_system_commission = theoretical_withdraw_system
            withdraw_liderpay_commission = withdraw_commission_total - theoretical_withdraw_system

    teminci_commission_total = deposit_teminci_commission + withdraw_teminci_commission
    system_commission_total = deposit_system_commission + withdraw_system_commission
    liderpay_commission_total = deposit_liderpay_commission + withdraw_liderpay_commission

    commission_total = site_commission_total
    balance_amount = total_deposits_amount - total_withdrawals_amount - commission_total

    deposits_by_day = (
        deposits_qs
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total_amount=Sum("amount"), count=Count("id"))
        .order_by("-day")
    )

    withdrawals_by_day = (
        withdrawals_qs
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total_amount=Sum("amount"), count=Count("id"))
        .order_by("-day")
    )

    stats = {
        "range_key": range_key,
        "range_label": range_label,
        "filter_start": custom_start_str,
        "filter_end": custom_end_str,
        "total_deposits_amount": total_deposits_amount,
        "total_deposits_count": total_deposits_count,
        "total_withdrawals_amount": total_withdrawals_amount,
        "total_withdrawals_count": total_withdrawals_count,
        "commission_total": commission_total,
        "balance_amount": balance_amount,
        "deposit_rate": deposit_rate,
        "withdraw_rate": withdraw_rate,
        "teminci_commission_total": teminci_commission_total,
        "system_commission_total": system_commission_total,
        "liderpay_commission_total": liderpay_commission_total,
    }

    range_options = [
        ("today", "Bugün"),
        ("yesterday", "Dün"),
        ("last7", "Son 7 Gün"),
        ("this_month", "Bu Ay"),
        ("last_month", "Geçen Ay"),
        ("custom", "Özel Aralık"),
        ("all", "Tüm Zamanlar"),
    ]

    context = {
        "branch": branch,
        "stats": stats,
        "range_options": range_options,
        "deposits_by_day": deposits_by_day,
        "withdrawals_by_day": withdrawals_by_day,
    }
    return render(request, "site_panel/reports.html", _inject_gateway_flags(context, branch))


@branch_required
def crypto_wallets(request):
    branch = request.user.branch_profile
    wallets = (
        CryptoWalletConfig.objects
        .filter(branch=branch)
        .order_by("-is_active", "coin", "network")
    )
    context = {
        "branch": branch,
        "wallets": wallets,
        "wallet_modes": dict(WalletMode.choices),
        "crypto_gateway_enabled": branch.gateway_configs.filter(
            gateway=GatewayType.CRYPTO, is_enabled=True
        ).exists(),
        "has_active_crypto_wallet": wallets.filter(is_active=True).exists(),
    }
    context = _inject_gateway_flags(context, branch)
    context.setdefault("crypto_gateway_enabled", context.get("gateway_crypto_enabled"))
    context["has_active_crypto_wallet"] = wallets.filter(is_active=True).exists()
    return render(request, "site_panel/crypto_wallets.html", context)


@branch_required
def kart_ayarlari(request):
    branch = request.user.branch_profile
    context = _build_card_psp_context(branch)
    return render(request, "site_panel/card_settings.html", _inject_gateway_flags(context, branch))


@branch_required
def card_settings(request):
    # Backwards-compatible route; reuse yeni kart ayarları görünümü
    return kart_ayarlari(request)


@branch_required
def create_deposit_link(request):
    branch = request.user.branch_profile

    base_bank_account_qs = BankAccount.objects.filter(is_active=True).select_related("provider").order_by("bank_name", "iban")
    provider_candidates = User.objects.filter(
        role=User.ROLE_PROVIDER,
        is_active=True,
        is_provider_active_for_deposits=True,
        id__in=base_bank_account_qs.values_list("provider_id", flat=True),
    ).order_by("first_name", "username")
    payment_base_url = getattr(settings, "PAYMENT_BASE_URL", "").rstrip("/")

    payment_link = None
    created_deposit = None

    if request.method == "POST":
        form = SiteDepositLinkForm(
            request.POST,
            bank_account_qs=base_bank_account_qs,
        )

        if form.is_valid():
            bank_account = form.cleaned_data.get("bank_account")
            external_user_id = form.cleaned_data["external_user_id"].strip()
            amount = form.cleaned_data["amount"]
            expires_in_minutes = form.cleaned_data["expires_in_minutes"]

            provider = bank_account.provider if bank_account else provider_candidates.first()

            if not provider:
                form.add_error(None, "Aktif teminci bulunamadı. Lütfen banka hesabı seçin veya sistem yöneticisine haber verin.")
            else:
                token = secrets.token_hex(16)
                expires_at = timezone.now() + timedelta(minutes=expires_in_minutes)

                created_deposit = DepositRequest.objects.create(
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
                create_payment_transaction_for_deposit(created_deposit)

                path_part = f"/pay/{branch.site_code}/{token}/"
                if payment_base_url:
                    payment_link = f"{payment_base_url}{path_part}"
                else:
                    payment_link = path_part

                messages.success(request, "Yatırım linki başarıyla oluşturuldu.")
                form = SiteDepositLinkForm(bank_account_qs=base_bank_account_qs)
    else:
        form = SiteDepositLinkForm(bank_account_qs=base_bank_account_qs)

    recent_links_raw = (
        DepositRequest.objects
        .filter(branch=branch)
        .select_related("provider", "bank_account")
        .order_by("-created_at")[:8]
    )

    recent_links = []
    for entry in recent_links_raw:
        path_part = None
        if entry.payment_token:
            path_part = f"/pay/{branch.site_code}/{entry.payment_token}/"
        if path_part:
            if payment_base_url:
                full_link = f"{payment_base_url}{path_part}"
            else:
                full_link = path_part
        else:
            full_link = ""
        recent_links.append(
            {
                "deposit": entry,
                "link": full_link,
                "path": path_part or "",
            }
        )

    context = {
        "branch": branch,
        "form": form,
        "payment_link": payment_link,
        "created_deposit": created_deposit,
        "recent_links": recent_links,
        "bank_accounts": base_bank_account_qs,
    }
    return render(request, "site_panel/create_deposit_link.html", _inject_gateway_flags(context, branch))


def site_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user and getattr(user, "role", None) == "BRANCH":
            auth_login(request, user)
            return redirect("site_panel:dashboard")
        messages.error(request, "Geçersiz giriş bilgileri.")
    return render(request, "admin_panel/login.html", {
        "panel_title": "Site Paneli",
        "panel_subtitle": "Bayi/Site hesabınız ile giriş yapın.",
        "access_badge": "Site Girişi",
    })


@branch_required
def site_logout(request):
    auth_logout(request)
    messages.success(request, "Başarıyla çıkış yaptınız.")
    return redirect("site_panel:login")


@branch_required
def notifications_feed(request):
    branch = request.user.branch_profile

    deposit_queryset = (
        DepositRequest.objects
        .filter(branch=branch, status="pending", submitted_at__isnull=False)
        .order_by("-created_at")
        .values("id", "user_name", "amount", "created_at")[:5]
    )

    withdrawal_queryset = (
        WithdrawalRequest.objects
        .filter(branch=branch, status="pending")
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
        "poll_interval": branch.notification_poll_interval,
        "sound_enabled": branch.notification_sound_enabled,
        "ack_timestamp": branch.last_notification_ack.isoformat() if branch.last_notification_ack else None,
    }

    if request.GET.get("mark_seen") == "1":
        branch.last_notification_ack = timezone.now()
        branch.save(update_fields=["last_notification_ack"])
        data["ack_timestamp"] = branch.last_notification_ack.isoformat()

    return JsonResponse(data)


@branch_required
def api_yonetimi(request):
    """Site panel view that shows API integration details for BANK and CRYPTO only.

    Read-only: exposes the branch api_key and example requests for enabled gateways.
    """
    branch = request.user.branch_profile

    # Determine enabled gateways via SiteGatewayConfig
    bank_enabled = branch.gateway_configs.filter(gateway=GatewayType.BANK, is_enabled=True).exists()
    crypto_enabled = branch.gateway_configs.filter(gateway=GatewayType.CRYPTO, is_enabled=True).exists()

    # Determine base URL
    base_url = getattr(settings, "SITE_BASE_URL", "") or ""
    if not base_url:
        base_url = request.build_absolute_uri("/").rstrip("/")

    endpoints = {
        "deposit_create_url": "/api/v1/deposit/create",
        "withdraw_create_url": "/api/v1/withdraw/create",
        "txn_status_url": "/api/v1/transaction/status",
    }

    # Mask API key for display (show first 6 and last 6 characters)
    api_key_full = branch.api_key
    masked_api_key = api_key_full
    if api_key_full and len(api_key_full) > 12:
        masked_api_key = f"{api_key_full[:6]}...{api_key_full[-6:]}"

    # Example payloads
    examples = {}
    if bank_enabled:
        examples["bank_deposit"] = json.dumps(
            {
                "gateway": "BANK",
                "external_user_id": "player123",
                "amount": 100.00,
                "currency": "TRY",
            },
            indent=2,
            ensure_ascii=False,
        )
    if crypto_enabled:
        examples["crypto_deposit"] = json.dumps(
            {
                "gateway": "CRYPTO",
                "external_user_id": "player123",
                "amount": 50.0,
                "currency": "USDT",
            },
            indent=2,
            ensure_ascii=False,
        )

    examples["txn_status"] = f"?payment_token=PAYMENT_TOKEN_HERE"

    context = {
        "site_name": branch.name,
        "api_key": api_key_full,
        "masked_api_key": masked_api_key,
        "base_url": base_url,
        "enabled_gateways": {"BANK": bank_enabled, "CRYPTO": crypto_enabled},
        "endpoints": endpoints,
        "examples": examples,
    }

    context = _inject_gateway_flags(context, branch)
    return render(request, "site_panel/api_yonetimi.html", context)


@branch_required
@require_POST
def update_notification_settings(request):
    branch = request.user.branch_profile
    form = NotificationSettingsForm(request.POST, instance=branch)
    if form.is_valid():
        form.save()
        messages.success(request, "Bildirim ayarları güncellendi.")
    else:
        error_msg = "; ".join(
            [f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()]
        )
        messages.error(request, f"Bildirim ayarları güncellenemedi: {error_msg}")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if not next_url:
        next_url = reverse("site_panel:dashboard")
    return redirect(next_url)
