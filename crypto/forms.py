from decimal import Decimal

from django import forms

from client_api.forms import BranchBoundAmountMixin
from crypto.constants import SUPPORTED_COINS, SUPPORTED_NETWORKS


class CryptoDepositForm(BranchBoundAmountMixin, forms.Form):
    branch_min_field = "deposit_min_amount"
    branch_max_field = "deposit_max_amount"

    player_id = forms.CharField(
        label="Oyuncu ID",
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Skin kullanıcı ID"}),
    )
    coin = forms.ChoiceField(
        label="Coin",
        choices=SUPPORTED_COINS,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    network = forms.ChoiceField(
        label="Ağ",
        choices=SUPPORTED_NETWORKS,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    amount = forms.DecimalField(
        label="Tutar",
        min_value=Decimal("5.00"),
        max_digits=12,
        decimal_places=6,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.000001"}),
    )
