from decimal import Decimal

from django import forms

from client_api.forms import BranchBoundAmountMixin


class CardDepositForm(BranchBoundAmountMixin, forms.Form):
    branch_min_field = "deposit_min_amount"
    branch_max_field = "deposit_max_amount"

    player_name = forms.CharField(
        label="Ad Soyad",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Oyuncu adı"}),
    )
    player_id = forms.CharField(
        label="Kullanıcı ID",
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Skin kullanıcı adı / ID (opsiyonel)"}
        ),
    )
    amount = forms.DecimalField(
        label="Yatırım Tutarı",
        min_value=Decimal("1.00"),
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    card_holder = forms.CharField(
        label="Kart Üzerindeki İsim",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Kart üzerindeki isim"}),
    )
    card_brand = forms.ChoiceField(
        label="Kart Tipi",
        choices=[
            ("visa", "Visa"),
            ("mastercard", "Mastercard"),
            ("amex", "American Express"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
