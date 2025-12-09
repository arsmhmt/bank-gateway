from django.db import models


class PublicRequestLog(models.Model):
    REQUEST_DEPOSIT = "deposit"
    REQUEST_WITHDRAW = "withdraw"
    REQUEST_TYPE_CHOICES = [
        (REQUEST_DEPOSIT, "Deposit"),
        (REQUEST_WITHDRAW, "Withdraw"),
    ]

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="public_request_logs",
        null=True,
        blank=True,
    )
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    fingerprint = models.CharField(max_length=96, blank=True)
    path = models.CharField(max_length=255, blank=True)
    was_limited = models.BooleanField(default=False)
    limit_scope = models.CharField(max_length=32, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("branch", "request_type", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.request_type} request @ {self.ip_address or 'unknown'} ({self.created_at:%Y-%m-%d %H:%M:%S})"

