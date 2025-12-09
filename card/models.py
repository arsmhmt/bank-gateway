from django.db import models


class CardPayment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_FAILED = "failed"
    STATUS_REQUIRES_ACTION = "action_required"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REQUIRES_ACTION, "Requires 3D Secure"),
    ]

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="card_payments",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="TRY")
    user_name = models.CharField(max_length=150)
    psp_tx_id = models.CharField(max_length=120, blank=True, null=True)
    psp_redirect_url = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"CardPayment #{self.id} · {self.branch.name} · {self.amount}"

# Create your models here.
