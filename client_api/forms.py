from decimal import Decimal

from django import forms


class BranchBoundAmountMixin:
    amount_min_default = Decimal("0.00")
    amount_max_default = None
    amount_field_name = "amount"

    def __init__(self, *args, branch=None, **kwargs):
        self.branch = branch
        super().__init__(*args, **kwargs)
        self._apply_branch_amount_bounds()

    def _apply_branch_amount_bounds(self):
        field = self.fields.get(self.amount_field_name)
        if not field:
            return

        min_amount = self.amount_min_default
        max_amount = self.amount_max_default

        if self.branch:
            min_attr = getattr(self.branch, getattr(self, "branch_min_field", ""), None)
            max_attr = getattr(self.branch, getattr(self, "branch_max_field", ""), None)
            if min_attr is not None:
                min_amount = min_attr
            if max_attr:
                max_amount = max_attr

        field.min_value = min_amount
        field.max_value = max_amount


class PublicDepositForm(BranchBoundAmountMixin, forms.Form):
    branch_min_field = "deposit_min_amount"
    branch_max_field = "deposit_max_amount"

    player_name = forms.CharField(
        label="Ad Soyad",
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Oyuncu adı"}),
    )
    player_id = forms.CharField(
        label="Kullanıcı ID",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Skin kullanıcı adı / ID"}),
    )
    amount = forms.DecimalField(
        label="Yatırım Tutarı",
        min_value=Decimal("0.00"),
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )


class PublicWithdrawForm(BranchBoundAmountMixin, forms.Form):
    branch_min_field = "withdraw_min_amount"
    branch_max_field = "withdraw_max_amount"

    player_name = forms.CharField(
        label="Ad Soyad",
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Oyuncu adı"}),
    )
    player_id = forms.CharField(
        label="Kullanıcı ID",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Skin kullanıcı adı / ID"}),
    )
    iban = forms.CharField(
        label="IBAN",
        max_length=34,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "TRXX XXXX XXXX XXXX"}),
    )
    amount = forms.DecimalField(
        label="Çekim Tutarı",
        min_value=Decimal("0.00"),
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
