from django.contrib import admin

from .models import PublicRequestLog


@admin.register(PublicRequestLog)
class PublicRequestLogAdmin(admin.ModelAdmin):
    list_display = ("request_type", "branch", "ip_address", "was_limited", "limit_scope", "created_at")
    list_filter = ("request_type", "was_limited", "limit_scope", "created_at")
    search_fields = ("ip_address", "user_agent", "fingerprint", "branch__name")
    readonly_fields = (
        "branch",
        "request_type",
        "ip_address",
        "user_agent",
        "fingerprint",
        "path",
        "was_limited",
        "limit_scope",
        "metadata",
        "created_at",
    )
    ordering = ("-created_at",)
