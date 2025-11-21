
from django import forms
from core.models import BankAccount, User

class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ["bank_name", "account_holder", "iban", "account_limit"]
        widgets = {
            "bank_name": forms.TextInput(attrs={"class": "form-control"}),
            "account_holder": forms.TextInput(attrs={"class": "form-control"}),
            "iban": forms.TextInput(attrs={"class": "form-control"}),
            "account_limit": forms.NumberInput(attrs={"class": "form-control"}),
        }

class ProviderProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'email']
