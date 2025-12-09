from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import AbstractUser
from django.conf import settings


class GatewayType(models.TextChoices):
    BANK = "BANK", "Bank Transfer"
    CARD = "CARD", "Credit Card"
    CRYPTO = "CRYPTO", "Crypto"


class User(AbstractUser):
    ROLE_OWNER = "OWNER"
    ROLE_ADMIN = "ADMIN"
    ROLE_BRANCH = "BRANCH"
    ROLE_PROVIDER = "PROVIDER"

    ROLE_CHOICES = [
        (ROLE_OWNER, "Sistem"),       
        (ROLE_ADMIN, "Yönetici"),     
        (ROLE_BRANCH, "Bayi / Site"), 
        (ROLE_PROVIDER, "Teminci"),   
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_BRANCH,
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Override AbstractUser fields to make them nullable for backward compatibility
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    # Limitor and active flag for provider (Teminci)
    limitor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Teminci için maksimum toplam yatırım limiti (boş = limitsiz)",
    )
    is_provider_active_for_deposits = models.BooleanField(
        default=True,
        help_text="Pasif ise bu teminci yeni yatırımlar için gösterilmez."
    )

    def is_owner(self): return self.role == self.ROLE_OWNER
    def is_admin(self): return self.role in {self.ROLE_OWNER, self.ROLE_ADMIN}
    def is_branch(self): return self.role == self.ROLE_BRANCH
    def is_provider(self): return self.role == self.ROLE_PROVIDER

class Client(models.Model):
    name = models.CharField(max_length=100)
    contact_info = models.TextField(blank=True, null=True)
    deposit_commission = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    withdraw_commission = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    api_key = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class BankAccount(models.Model):
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'PROVIDER'})
    bank_name = models.CharField(max_length=100)
    account_holder = models.CharField(max_length=100)
    iban = models.CharField(max_length=34)
    account_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Bu hesabın alabileceği maksimum toplam yatırım (0 veya boş = limitsiz)",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bank_name} - {self.iban}"

    @property
    def limitor(self):
        """Template/backward-compatible alias for account_limit."""

        return self.account_limit

    @property
    def account_owner(self):
        """Backward compatible alias for account_holder used in older templates."""

        return self.account_holder

    @property
    def limit_amount(self):
        """Backward compatible alias for account_limit used in legacy views/templates."""

        return self.account_limit


class DepositRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Beklemede"),
        ("approved", "Onaylandı"),
        ("rejected", "Reddedildi"),
    ]

    user_name = models.CharField(max_length=100)
    external_user_id = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="TRY")
    currency = models.CharField(max_length=10, default="TRY")
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name="deposits",
        null=True,
        blank=True
    )
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, null=True, blank=True)
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deposit_requests")
    payment_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    submitted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Deposit #{self.id} - {self.amount} {self.currency}"

class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Bekliyor'),
        ('approved', 'Onaylandı'),
        ('rejected', 'Reddedildi'),
    )

    user_name = models.CharField(max_length=100)
    iban = models.CharField(max_length=34)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name="withdrawals",
        null=True,
        blank=True
    )
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawal_requests")
    payment_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Withdraw #{self.id} - {self.amount} {self.currency}"
    
# core/models.py

class ClientSite(models.Model):
    name = models.CharField(max_length=255)
    contact_email = models.EmailField(blank=True, null=True)
    contact_telegram = models.CharField(max_length=100, blank=True, null=True)
    deposit_commission_rate = models.FloatField(default=0.0)
    withdraw_commission_rate = models.FloatField(default=0.0)
    system_commission_rate = models.FloatField(default=0.0)
    branch = models.OneToOneField(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="client_site",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.name

class APIKey(models.Model):
    client_site = models.OneToOneField(ClientSite, on_delete=models.CASCADE, related_name="api_key")
    key = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return f"API Key for {self.client_site.name}"

class Commission(models.Model):
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'PROVIDER'})
    transaction_type = models.CharField(max_length=20, choices=[('deposit', 'Deposit'), ('withdraw', 'Withdraw')])
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # earned commission
    related_txn_id = models.PositiveIntegerField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider} - {self.transaction_type} - {self.amount}"


class ProviderSettlementPayment(models.Model):
    provider = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"role": User.ROLE_PROVIDER},
        related_name="settlement_payments",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_provider_settlements",
    )

    class Meta:
        verbose_name = "Teslimat Ödemesi"
        verbose_name_plural = "Teslimat Ödemeleri"

    def __str__(self):
        return f"{self.provider} – {self.amount} TL"

class ProviderCommission(models.Model):
    provider = models.ForeignKey('provider_panel.Provider', on_delete=models.CASCADE, related_name='commissions')
    transaction_type = models.CharField(max_length=20, choices=[('deposit', 'Deposit'), ('withdraw', 'Withdraw')])
    transaction_id = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider} - {self.amount} ({self.transaction_type})"


class PaymentTransaction(models.Model):
    DIRECTION_IN = "IN"
    DIRECTION_OUT = "OUT"
    DIRECTION_CHOICES = [
        (DIRECTION_IN, "Deposit"),
        (DIRECTION_OUT, "Withdraw"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_FAILED = "failed"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_FAILED, "Failed"),
        (STATUS_EXPIRED, "Expired"),
    ]

    branch = models.ForeignKey("branches.Branch", on_delete=models.CASCADE, related_name="payment_transactions")
    gateway = models.CharField(max_length=10, choices=GatewayType.choices)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="TRY")
    user_name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    ref_code = models.CharField(max_length=64, unique=True)
    card_payment = models.ForeignKey(
        "card.CardPayment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    crypto_payment = models.ForeignKey(
        "crypto.CryptoPayment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_gateway_display()} {self.direction} {self.amount} {self.currency} ({self.ref_code})"

