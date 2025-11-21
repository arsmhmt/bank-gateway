
from django.shortcuts import render, redirect
from core.models import WithdrawalRequest

def withdraw_request_form(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        iban = request.POST.get('iban')
        amount = request.POST.get('amount')
        bank = request.POST.get('bank')

        WithdrawalRequest.objects.create(
            client=None,
            provider=None,
            name_surname=name,
            iban=iban,
            amount=amount,
            status="Beklemede"
        )
        return render(request, 'client_api/withdraw_submitted.html', {"amount": amount})
    return render(request, 'client_api/withdraw_form.html')
