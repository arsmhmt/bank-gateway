from django import forms
from django.contrib.auth import get_user_model
from branches.models import Branch, CardPspConfig
from core.models import ClientSite, BankAccount
from crypto.constants import SUPPORTED_COINS, SUPPORTED_NETWORKS
from crypto.models import CryptoWalletConfig, WalletMode

User = get_user_model()


class StyledFormMixin:
    """Apply consistent Bootstrap-friendly classes to all widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get("class", "")

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = f"{existing} form-check-input".strip()
            elif isinstance(widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
                widget.attrs["class"] = f"{existing} form-check".strip()
            else:
                widget.attrs["class"] = f"{existing} form-control".strip()

            if not widget.attrs.get("placeholder") and field.label:
                widget.attrs["placeholder"] = field.label


class AdminForm(StyledFormMixin, forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False, label="Şifre")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "password"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        is_new = not getattr(self.instance, "pk", None)

        # Username is always required for admin login
        self.fields["username"].required = True
        self.fields["username"].label = "Kullanıcı Adı"

        # Password required only when creating a new admin
        self.fields["password"].required = is_new
        if is_new:
            self.fields["password"].widget.attrs["placeholder"] = "Şifre"
        else:
            self.fields["password"].widget.attrs["placeholder"] = "Yeni şifre (opsiyonel)"

    def save(self, commit=True):
        is_new = not getattr(self.instance, "pk", None)
        user = super().save(commit=False)

        # Ensure username and email come from cleaned form data
        username = self.cleaned_data.get("username") or user.username
        email = self.cleaned_data.get("email") or user.email

        if username:
            user.username = username
        if email:
            user.email = email

        # New users created through this form must be ADMIN by default
        if is_new:
            user.role = getattr(User, "ROLE_ADMIN", "ADMIN")

        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)

        if commit:
            user.save()
        return user


class AdminPasswordResetForm(StyledFormMixin, forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput, label="Yeni Şifre")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Yeni Şifre (Tekrar)")

    def clean(self):
        data = super().clean()
        password = data.get("new_password")
        confirm = data.get("confirm_password")
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "Şifreler eşleşmiyor.")
        return data


NETWORK_CHOICES = [
    ("TRC20", "TRC20 (Tron)"),
    ("ERC20", "ERC20 (Ethereum)"),
    ("BEP20", "BEP20 (BSC)"),
]


class CryptoWalletForm(StyledFormMixin, forms.ModelForm):
    network = forms.ChoiceField(choices=NETWORK_CHOICES, label="Ağ")

    class Meta:
        model = CryptoWalletConfig
        fields = [
            "branch",
            "coin",
            "network",
            "address",
            "label",
            "is_active",
            "is_deposit_enabled",
            "min_deposit_amount",
        ]
        labels = {
            "branch": "Site",
            "coin": "Koin",
            "network": "Ağ",
            "address": "Adres",
            "label": "Etiket",
            "is_active": "Aktif",
            "is_deposit_enabled": "Yatırım için aktif",
            "min_deposit_amount": "Minimum yatırım tutarı",
        }

class ClientSiteForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ClientSite
        fields = [
            "name",
            "contact_email",
            "contact_telegram",
            "deposit_commission_rate",
            "withdraw_commission_rate",
        ]

class BankAccountForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['provider', 'bank_name', 'account_holder', 'iban', 'account_limit', 'is_active']

class DepositLinkForm(StyledFormMixin, forms.Form):
    branch = forms.ModelChoiceField(queryset=Branch.objects.all(), label="Site / Bayi")
    provider = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=[getattr(User, "ROLE_PROVIDER", "PROVIDER"), "PROVIDER", "provider"]),
        label="Teminci",
    )
    bank_account = forms.ModelChoiceField(
        queryset=BankAccount.objects.filter(is_active=True),
        label="Banka Hesabı",
        required=False,
        help_text="Boş bırakırsanız kullanıcı ödeme ekranında banka seçecek.",
    )
    external_user_id = forms.CharField(max_length=100, label="Kullanıcı ID / Username")
    amount = forms.DecimalField(max_digits=10, decimal_places=2, label="Tutar")
    expires_in_minutes = forms.IntegerField(
        initial=30,
        min_value=1,
        max_value=1440,
        label="Link Süresi (dakika)",
    )


class CryptoWalletConfigForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CryptoWalletConfig
        fields = [
            "branch",
            "mode",
            "coin",
            "network",
            "address",
            "memo_tag",
            "ledger_xpub",
            "derivation_index",
            "is_active",
        ]

    coin = forms.ChoiceField(choices=SUPPORTED_COINS, label="Coin")
    network = forms.ChoiceField(choices=SUPPORTED_NETWORKS, label="Ağ")
    derivation_index = forms.IntegerField(min_value=0, label="Ledger Address Index", required=False, disabled=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            self.fields["branch"].disabled = True
            self.fields["coin"].disabled = True
            self.fields["network"].disabled = True
            self.fields["derivation_index"].initial = instance.derivation_index
        else:
            self.fields["derivation_index"].initial = 0

    def clean(self):
        data = super().clean()
        mode = data.get("mode")
        address = (data.get("address") or "").strip()
        ledger_xpub = (data.get("ledger_xpub") or "").strip()

        if mode == WalletMode.MANUAL:
            if not address:
                self.add_error("address", "Manuel cüzdan modu için adres zorunludur.")
            data["ledger_xpub"] = ""
        elif mode == WalletMode.LEDGER:
            if not ledger_xpub:
                self.add_error("ledger_xpub", "Ledger modu için xpub zorunludur.")
            data["address"] = ""
            data["memo_tag"] = ""
        return data


class CardPspConfigForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CardPspConfig
        fields = [
            "provider_name",
            "merchant_id",
            "terminal_id",
            "api_key",
            "mode",
            "is_active",
        ]
        labels = {
            "provider_name": "PSP Sağlayıcı",
            "merchant_id": "Merchant ID",
            "terminal_id": "Terminal ID",
            "api_key": "API Key / Secret",
            "mode": "Mod",
            "is_active": "Aktif mi?",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["api_key"].widget = forms.Textarea(attrs={"rows": 3, "class": "form-control"})
        self.fields["terminal_id"].required = False
        self.fields["api_key"].required = False