from decimal import Decimal

from django.db.models import Sum

from core.models import DepositRequest, WithdrawalRequest, ProviderCommission


ZERO = Decimal("0")


def compute_provider_settlement(provider):
    """Compute Teslimat components for a provider user.

    Returns a dict with keys: total_deposits, total_withdrawals, total_commission,
    total_settlements, balance. All values are Decimal.
    """
    # provider may be either User or provider_profile; normalize to User
    provider_user = provider
    if hasattr(provider, "user"):
        provider_user = provider.user

    total_deposits = (
        DepositRequest.objects.filter(provider=provider_user, status="approved").aggregate(total=Sum("amount"))["total"]
        or ZERO
    )

    total_withdrawals = (
        WithdrawalRequest.objects.filter(provider=provider_user, status="approved").aggregate(total=Sum("amount"))["total"]
        or ZERO
    )

    total_commission = (
        ProviderCommission.objects.filter(provider__user=provider_user).aggregate(total=Sum("amount"))["total"]
        or ProviderCommission.objects.filter(provider=provider_user).aggregate(total=Sum("amount"))["total"]
        or ZERO
    )

    # settlements recorded on user.settlement_payments
    total_settlements = (
        provider_user.settlement_payments.aggregate(total=Sum("amount"))["total"]
        or ZERO
    )

    balance = Decimal(total_deposits) - Decimal(total_withdrawals) - Decimal(total_commission) - Decimal(total_settlements)

    return {
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "total_commission": total_commission,
        "total_settlements": total_settlements,
        "balance": balance,
    }
