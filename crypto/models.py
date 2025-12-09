from decimal import Decimal

from django.db import models

from crypto.constants import (
    DEFAULT_RATE_SOURCES,
    SUPPORTED_COINS,
    SUPPORTED_NETWORKS,
)


class CryptoAssetConfig(models.Model):
    coin = models.CharField(max_length=10, choices=SUPPORTED_COINS)
    network = models.CharField(max_length=20, choices=SUPPORTED_NETWORKS)
    wallet_address = models.CharField(max_length=255)
    tag_or_memo = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    rate_source = models.CharField(
        max_length=50,
        choices=DEFAULT_RATE_SOURCES,
        default="coingecko",
    )
    manual_rate = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    rate_markup_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    min_confirmations = models.PositiveIntegerField(default=1)
    last_rate = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    last_rate_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("coin", "network")
        ordering = ["coin", "network"]

    def __str__(self):
        return f"{self.coin} · {self.network}"

    @property
    def markup_multiplier(self) -> Decimal:
        if self.rate_markup_percent:
            return Decimal("1") + (self.rate_markup_percent / Decimal("100"))
        return Decimal("1")


class WalletMode(models.TextChoices):
    MANUAL = "MANUAL", "Manual External Wallet"
    LEDGER = "LEDGER", "Ledger Cold Wallet"


class CryptoWalletConfig(models.Model):
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="crypto_wallets",
    )
    mode = models.CharField(max_length=10, choices=WalletMode.choices, default=WalletMode.MANUAL)
    coin = models.CharField(max_length=20)
    network = models.CharField(max_length=20)

    # Manual wallet fields
    address = models.CharField(max_length=180, blank=True)
    memo_tag = models.CharField(max_length=120, blank=True)

    # Ledger wallet fields
    ledger_xpub = models.CharField(max_length=255, blank=True)
    derivation_index = models.PositiveIntegerField(default=0)

    label = models.CharField(
        max_length=64,
        blank=True,
        help_text="Opsiyonel açıklama: Örn. Ana Ledger Cüzdanı",
    )
    is_active = models.BooleanField(default=True)
    is_deposit_enabled = models.BooleanField(
        default=True,
        help_text="Yeni yatırımlar için bu adres kullanılabilir mi?",
    )
    min_deposit_amount = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Opsiyonel minimum yatırım (boş bırakılırsa sınır yok).",
    )
    explorer_url_override = models.URLField(
        blank=True,
        help_text="Opsiyonel özel blockchain explorer bağlantısı.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("branch", "coin", "network")
        ordering = ["branch", "coin", "network"]

    def __str__(self):
        return f"{self.branch} · {self.coin}/{self.network} [{self.mode}]"


class CryptoPayment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_FAILED, "Failed"),
    ]

    DIRECTION_IN = "IN"
    DIRECTION_OUT = "OUT"
    DIRECTION_CHOICES = [
        (DIRECTION_IN, "Deposit"),
        (DIRECTION_OUT, "Withdrawal"),
    ]

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="crypto_payments",
    )
    coin = models.CharField(max_length=20)
    network = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=16, decimal_places=8)
    currency = models.CharField(max_length=10, default="TRY")
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default=DIRECTION_IN)
    user_name = models.CharField(max_length=150, blank=True)
    address = models.CharField(max_length=180)
    tx_hash = models.CharField(max_length=120, blank=True, null=True)
    payment_token = models.CharField(max_length=64, blank=True, null=True, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"CryptoPayment #{self.id} · {self.direction} · {self.coin} {self.amount}"
