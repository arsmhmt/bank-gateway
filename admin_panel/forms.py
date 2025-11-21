from django import forms
from django.contrib.auth import get_user_model
from core.models import ClientSite, BankAccount

User = get_user_model()

class AdminForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password']

class ClientSiteForm(forms.ModelForm):
    class Meta:
        model = ClientSite
        fields = [
            "name",
            "contact_email",
            "contact_telegram",
            "deposit_commission_rate",
            "withdraw_commission_rate",
        ]

class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['provider', 'bank_name', 'account_holder', 'iban', 'account_limit', 'is_active']