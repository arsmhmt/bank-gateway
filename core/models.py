from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, role=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        if role is not None:
            extra_fields['role'] = role
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('role', 'superadmin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    objects = UserManager()

    def __str__(self):
        return self.email

class Client(models.Model):
    name = models.CharField(max_length=100)
    contact_info = models.TextField(blank=True, null=True)
    deposit_commission = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    withdraw_commission = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    api_key = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class BankAccount(models.Model):
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'provider'})
    bank_name = models.CharField(max_length=100)
    account_holder = models.CharField(max_length=100)
    iban = models.CharField(max_length=34)
    account_limit = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bank_name} - {self.iban}"


class DepositRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Beklemede"),
        ("approved", "Onaylandı"),
        ("rejected", "Reddedildi"),
    ]

    user_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE)
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deposit_requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Deposit #{self.id} - {self.amount} TL"

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
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawal_requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Withdraw #{self.id} - {self.amount} TL"
    
# core/models.py

class ClientSite(models.Model):
    name = models.CharField(max_length=255)
    contact_email = models.EmailField(blank=True, null=True)
    contact_telegram = models.CharField(max_length=100, blank=True, null=True)
    deposit_commission_rate = models.FloatField(default=0.0)
    withdraw_commission_rate = models.FloatField(default=0.0)

    def __str__(self):
        return self.name

class APIKey(models.Model):
    client_site = models.OneToOneField(ClientSite, on_delete=models.CASCADE, related_name="api_key")
    key = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return f"API Key for {self.client_site.name}"

class Commission(models.Model):
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'provider'})
    transaction_type = models.CharField(max_length=20, choices=[('deposit', 'Deposit'), ('withdraw', 'Withdraw')])
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # earned commission
    related_txn_id = models.PositiveIntegerField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider} - {self.transaction_type} - {self.amount}"

class ProviderCommission(models.Model):
    provider = models.ForeignKey('provider_panel.Provider', on_delete=models.CASCADE, related_name='commissions')
    transaction_type = models.CharField(max_length=20, choices=[('deposit', 'Deposit'), ('withdraw', 'Withdraw')])
    transaction_id = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider} - {self.amount} ({self.transaction_type})"

