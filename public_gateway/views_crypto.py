from __future__ import annotations

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from decimal import Decimal, InvalidOperation
from typing import Optional

from crypto.forms import CryptoDepositForm
from crypto.models import CryptoPayment, CryptoWalletConfig, WalletMode
from crypto.services import get_crypto_rate
from core.constants import DEFAULT_CURRENCY
from core.models import GatewayType
from core.services.payment_transactions import create_payment_transaction_for_crypto

from .utils import (
    build_deposit_tabs,
    ensure_gateway_enabled,
    extract_prefill_params,
    get_branch_or_404,
    get_gateway_label,
)


def deposit_form(request: HttpRequest, code: str) -> HttpResponse:
    branch = get_branch_or_404(code)
    disabled_response = ensure_gateway_enabled(request, branch, GatewayType.CRYPTO)
    if disabled_response:
        return disabled_response

    prefill_initial, prefill_display = extract_prefill_params(request)

    # Only consider wallets that are active and enabled for deposits
    wallet_qs = (
        CryptoWalletConfig.objects.filter(branch=branch, is_active=True, is_deposit_enabled=True)
        .order_by("coin", "network")
    )
    if not wallet_qs.exists():
        return render(
            request,
            "public/errors/crypto_wallet_missing.html",
            {
                "branch": branch,
                "gateway_tabs": build_deposit_tabs(branch, GatewayType.CRYPTO),
                "gateway_label": get_gateway_label(GatewayType.CRYPTO),
            },
            status=503,
        )

    wallet_map = {
        (wallet.coin.upper(), wallet.network.upper()): wallet for wallet in wallet_qs
    }
    coin_order = sorted({wallet.coin.upper() for wallet in wallet_qs})
    networks_by_coin = {}
    for wallet in wallet_qs:
        networks_by_coin.setdefault(wallet.coin.upper(), [])
        if wallet.network.upper() not in networks_by_coin[wallet.coin.upper()]:
            networks_by_coin[wallet.coin.upper()].append(wallet.network.upper())

    def _normalize_symbol(value: str | None) -> str:
        return (value or "").strip().upper()

    selected_coin = _normalize_symbol(request.GET.get("coin")) or coin_order[0]
    if selected_coin not in coin_order:
        selected_coin = coin_order[0]

    selected_networks = networks_by_coin.get(selected_coin) or networks_by_coin[coin_order[0]]
    selected_network = _normalize_symbol(request.GET.get("network")) or selected_networks[0]
    if selected_network not in selected_networks:
        selected_network = selected_networks[0]

    initial = prefill_initial.copy()
    initial.setdefault("coin", selected_coin)
    initial.setdefault("network", selected_network)

    form = CryptoDepositForm(request.POST or None, branch=branch, initial=initial)
    form.fields["coin"].choices = [(coin, coin) for coin in coin_order]

    current_coin = _normalize_symbol(
        form.data.get("coin") if request.method == "POST" else form.initial.get("coin")
    ) or selected_coin
    if current_coin not in coin_order:
        current_coin = coin_order[0]
    current_networks = networks_by_coin.get(current_coin) or []
    if not current_networks:
        current_networks = selected_networks
    form.fields["network"].choices = [(network, network) for network in current_networks]

    selected_wallet = wallet_map.get((current_coin, current_networks[0]))
    wallet_meta = {
        "mode": selected_wallet.mode if selected_wallet else "",
        "mode_label": selected_wallet.get_mode_display() if selected_wallet else "",
        "memo_tag": selected_wallet.memo_tag if selected_wallet else "",
        "ledger_hint": (selected_wallet.ledger_xpub[:24] + "…")
        if selected_wallet and selected_wallet.ledger_xpub
        else "",
    }

    crypto_payment = None
    deposit_address = None
    memo_tag = None

    if selected_wallet and selected_wallet.mode == WalletMode.MANUAL and selected_wallet.address:
        deposit_address = selected_wallet.address
        memo_tag = selected_wallet.memo_tag

    if request.method == "POST":
        if form.is_valid():
            cleaned_coin = form.cleaned_data["coin"].upper()
            cleaned_network = form.cleaned_data["network"].upper()
            wallet = wallet_map.get((cleaned_coin, cleaned_network))
            if wallet is None:
                form.add_error(None, "Bu coin/ağ kombinasyonu için aktif cüzdan bulunamadı.")
            else:
                try:
                    if wallet.mode == WalletMode.MANUAL:
                        if not wallet.address:
                            form.add_error(None, "Bu manuel cüzdan için tanımlı adres bulunmuyor.")
                            raise ValueError
                        deposit_address = wallet.address
                        memo_tag = wallet.memo_tag
                    else:
                        if not wallet.ledger_xpub:
                            form.add_error(None, "Ledger modunda xpub zorunludur.")
                            raise ValueError
                        with transaction.atomic():
                            wallet_locked = (
                                CryptoWalletConfig.objects.select_for_update()
                                .get(pk=wallet.pk)
                            )
                            derived_address = f"{wallet_locked.ledger_xpub[:32]}-{wallet_locked.derivation_index}"
                            wallet_locked.derivation_index += 1
                            wallet_locked.save(update_fields=["derivation_index", "updated_at"])
                        deposit_address = derived_address
                        memo_tag = None

                    if deposit_address:
                        crypto_payment = CryptoPayment.objects.create(
                            branch=branch,
                            coin=cleaned_coin,
                            network=cleaned_network,
                            amount=form.cleaned_data["amount"],
                            currency=DEFAULT_CURRENCY,
                            direction=CryptoPayment.DIRECTION_IN,
                            address=deposit_address,
                            status=CryptoPayment.STATUS_PENDING,
                        )
                        create_payment_transaction_for_crypto(crypto_payment)
                        wallet_meta = {
                            "mode": wallet.mode,
                            "mode_label": wallet.get_mode_display(),
                            "memo_tag": memo_tag,
                            "ledger_hint": (wallet.ledger_xpub[:24] + "…") if wallet.ledger_xpub else "",
                        }
                        form = CryptoDepositForm(branch=branch)
                except ValueError:
                    crypto_payment = None

    fiat_currency = DEFAULT_CURRENCY
    rate = get_crypto_rate(current_coin, fiat_currency)

    amount_candidate: Optional[Decimal] = None
    if crypto_payment:
        amount_candidate = crypto_payment.amount
        deposit_address = crypto_payment.address
    else:
        raw_amount = form.data.get("amount") if request.method == "POST" else form.initial.get("amount")
        try:
            if raw_amount:
                amount_candidate = Decimal(raw_amount)
        except (ValueError, TypeError, InvalidOperation):
            amount_candidate = None

    fiat_value = None
    if rate is not None and amount_candidate:
        try:
            fiat_value = amount_candidate * rate
        except Exception:
            fiat_value = None

    context = {
        "branch": branch,
        "form": form,
        "crypto_payment": crypto_payment,
        "prefill": prefill_display,
        "gateway_tabs": build_deposit_tabs(branch, GatewayType.CRYPTO),
        "gateway_label": get_gateway_label(GatewayType.CRYPTO),
        "wallet_meta": wallet_meta,
        "selected_coin": current_coin,
        "selected_network": form.data.get("network") if request.method == "POST" else form.initial.get("network"),
        "deposit_address": deposit_address,
        "coin": current_coin,
        "network": form.data.get("network") if request.method == "POST" else form.initial.get("network"),
        "crypto_mode": wallet_meta.get("mode"),
        "fiat_currency": fiat_currency,
        "rate": rate,
        "fiat_value": fiat_value,
        "memo_tag": wallet_meta.get("memo_tag"),
    }
    return render(request, "public/crypto_deposit.html", context)


def withdraw_form(request: HttpRequest, code: str) -> HttpResponse:
    branch = get_branch_or_404(code)
    disabled_response = ensure_gateway_enabled(request, branch, GatewayType.CRYPTO)
    if disabled_response:
        return disabled_response

    _, prefill_display = extract_prefill_params(request)
    context = {
        "branch": branch,
        "gateway": GatewayType.CRYPTO,
        "gateway_label": get_gateway_label(GatewayType.CRYPTO),
        "prefill": prefill_display,
    }
    return render(request, "public/gateway_placeholder.html", context)
