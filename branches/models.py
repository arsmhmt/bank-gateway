from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.crypto import get_random_string
from django.core.validators import MinValueValidator, MaxValueValidator

from core.models import User, GatewayType


def generate_api_key():
    return get_random_string(40)


def generate_site_code() -> str:
    """Generate a short public identifier for a Branch/Site.

    This ID is safe to expose in payment URLs and APIs.
    """

    return get_random_string(10).upper()


def generate_public_code() -> str:
    """Generate slug-safe permanent code for public deposit/withdraw endpoints."""

    return get_random_string(6).lower()


class Branch(models.Model):
    """
    Betting site / branch that uses the bank gateway.
    """
    name = models.CharField(max_length=150)
    domain = models.CharField(max_length=255, blank=True)

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="branch_profile",
        help_text="Login user for this branch/site panel",
    )

    api_key = models.CharField(
        max_length=64,
        unique=True,
        default=generate_api_key,
    )

    # Public unique identifier per site used in payment URLs, e.g. /pay/<site_code>/<token>/
    site_code = models.CharField(
        max_length=16,
        unique=True,
        default=generate_site_code,
        help_text="Public unique ID for this site/branch (used in payment URLs).",
    )
    public_code = models.SlugField(
        max_length=32,
        unique=True,
        default=generate_public_code,
        help_text="Permanent code for /p/<code>/deposit|withdraw links.",
    )
    callback_url = models.URLField(
        help_text="Where we POST transaction status (approved/rejected) for this branch"
    )
    deposit_min_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Public deposit form minimum tutarı. Varsayılan 10₺.",
    )
    deposit_max_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Site başına maksimum public yatırım tutarı. Boş bırakılırsa limitsiz.",
    )
    withdraw_min_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("50.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Public çekim formu minimum tutarı. Varsayılan 50₺.",
    )
    withdraw_max_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Site başına maksimum public çekim tutarı. Boş bırakılırsa limitsiz.",
    )
    deposit_commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Siteye uygulanan yatırım komisyon oranı (%).",
    )
    withdraw_commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Siteye uygulanan çekim komisyon oranı (%).",
    )
    system_commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
        help_text="Lider Pay sistem payı (varsayılan 0).",
    )

    notification_sound_enabled = models.BooleanField(default=True)
    notification_poll_interval = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(5), MaxValueValidator(60)],
        help_text="Polling interval in seconds for site panel notifications",
    )
    last_notification_ack = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name

    def _public_base_url(self) -> str:
        base = getattr(settings, "PAYMENT_BASE_URL", "https://lider-pay.com") or "https://lider-pay.com"
        return base.rstrip("/")

    def get_deposit_url(self) -> str:
        return f"{self._public_base_url()}/p/{self.public_code}/deposit/"

    def get_withdraw_url(self) -> str:
        return f"{self._public_base_url()}/p/{self.public_code}/withdraw/"


class SiteGatewayConfig(models.Model):
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="gateway_configs",
    )
    gateway = models.CharField(max_length=10, choices=GatewayType.choices)
    is_enabled = models.BooleanField(default=False)

    class Meta:
        unique_together = ("branch", "gateway")
        verbose_name = "Site Gateway Configuration"
        verbose_name_plural = "Site Gateway Configurations"

    def __str__(self) -> str:
        return f"{self.branch.name} - {self.gateway}"


class CardPspConfig(models.Model):
    MODE_TEST = "TEST"
    MODE_LIVE = "LIVE"
    MODE_CHOICES = [
        (MODE_TEST, "Test"),
        (MODE_LIVE, "Live"),
    ]

    branch = models.OneToOneField(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="card_psp_config",
    )
    provider_name = models.CharField(max_length=50)
    merchant_id = models.CharField(max_length=100)
    terminal_id = models.CharField(max_length=100, blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_TEST)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.branch.name} · {self.provider_name} ({self.mode})"
