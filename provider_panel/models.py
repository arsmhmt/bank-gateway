# models placeholder

from django.db import models
from django.conf import settings

class Provider(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="provider_profile")
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    deposit_commission = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    withdraw_commission = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
