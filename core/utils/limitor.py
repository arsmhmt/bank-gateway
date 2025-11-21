
from core.models import DepositRequest
from django.db.models import Sum

def bank_under_limit(bank):
    current_total = DepositRequest.objects.filter(
        bank_account=bank,
        status__in=['pending', 'approved']
    ).aggregate(total=Sum('amount'))['total'] or 0
    return current_total < bank.limit

def provider_under_limit(provider):
    current_total = DepositRequest.objects.filter(
        provider=provider,
        status__in=['pending', 'approved']
    ).aggregate(total=Sum('amount'))['total'] or 0
    return current_total < provider.limitor
