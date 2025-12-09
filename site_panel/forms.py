from django import forms
from django.contrib.auth import get_user_model

from core.models import BankAccount
from branches.models import Branch

User = get_user_model()


class SiteDepositLinkForm(forms.Form):
    bank_account = forms.ModelChoiceField(
        label="Banka Hesabı (Opsiyonel)",
        required=False,
        queryset=BankAccount.objects.none(),
        help_text="Boş bırakırsanız kullanıcı ödeme ekranında banka seçecek.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    external_user_id = forms.CharField(
        label="Kullanıcı ID / Username",
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "site kullanıcısı"}),
    )
    amount = forms.DecimalField(
        label="Tutar",
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    expires_in_minutes = forms.IntegerField(
        label="Link Süresi (dakika)",
        initial=30,
        min_value=1,
        max_value=1440,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
        help_text="Varsayılan 30 dk. Süre dolunca link otomatik olarak geçersiz olur.",
    )

    def __init__(self, *args, bank_account_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if bank_account_qs is not None:
            self.fields["bank_account"].queryset = bank_account_qs
        self.fields["bank_account"].empty_label = "Bankayı otomatik seç"


class NotificationSettingsForm(forms.ModelForm):
    notification_poll_interval = forms.IntegerField(
        label="Kontrol Sıklığı (saniye)",
        min_value=5,
        max_value=60,
        help_text="Bildirimlerin kaç saniyede bir yenileneceğini belirleyin (5-60).",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 5, "max": 60}),
    )

    notification_sound_enabled = forms.BooleanField(
        label="Sesli uyarı",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Branch
        fields = ["notification_sound_enabled", "notification_poll_interval"]
