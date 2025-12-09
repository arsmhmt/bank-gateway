
from decimal import Decimal

from django.db.models import Sum

from core.models import DepositRequest, BankAccount


ZERO = Decimal("0")


def _sum_deposits_for_bank(bank_account) -> Decimal:
    """Return total of pending + approved deposits for a bank account."""

    total = (
        DepositRequest.objects
        .filter(bank_account=bank_account, status__in=["pending", "approved"])
        .aggregate(total=Sum("amount"))["total"]
        or ZERO
    )
    return total


def _normalise_provider(provider):
    """Return a tuple of (provider_user, provider_model) for limit helpers."""

    provider_model = None
    provider_user = provider

    if hasattr(provider, "user"):
        provider_model = provider
        provider_user = provider.user
    else:
        provider_model = getattr(provider, "provider_profile", None)

    return provider_user, provider_model


def _sum_deposits_for_provider(provider) -> Decimal:
    """Return total of pending + approved deposits for a provider."""

    provider_user, _ = _normalise_provider(provider)

    if provider_user is None:
        return ZERO

    total = (
        DepositRequest.objects
        .filter(provider=provider_user, status__in=["pending", "approved"])
        .aggregate(total=Sum("amount"))["total"]
        or ZERO
    )
    return total


def bank_under_limit(bank_account) -> bool:
    """
    Whether the bank account can still accept deposits.

    Unlimited when account_limit is None/0 or non-positive. Otherwise compare totals.
    """

    limit = getattr(bank_account, "account_limit", None)
    if not limit or limit <= ZERO:
        return True

    used = _sum_deposits_for_bank(bank_account)
    return used < limit


def provider_under_limit(provider) -> bool:
    """
    Whether the provider remains under their aggregate deposit limit.
    """

    _, provider_model = _normalise_provider(provider)

    if provider_model is not None:
        limit = getattr(provider_model, "limitor", None)
    else:
        limit = getattr(provider, "limitor", None)

    if not limit or limit <= ZERO:
        return True

    used = _sum_deposits_for_provider(provider)
    return used < limit


def sync_bank_active_state(bank_account):
    """Toggle bank account active flag based on its limit usage."""

    if bank_account is None:
        return

    can_accept = bank_under_limit(bank_account)
    desired_active = bool(can_accept)

    if bank_account.is_active != desired_active:
        bank_account.is_active = desired_active
        bank_account.save(update_fields=["is_active"])


def sync_provider_bank_states(provider):
    """Ensure provider's bank accounts reflect provider-level limit."""

    provider_user, _ = _normalise_provider(provider)

    if provider_user is None:
        return

    respect_limit = provider_under_limit(provider)
    qs = BankAccount.objects.filter(provider=provider_user)

    if respect_limit:
        qs.filter(is_active=False).update(is_active=True)
    else:
        qs.filter(is_active=True).update(is_active=False)
