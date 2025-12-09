from django.contrib import admin
from .models import ProviderSettlementPayment


@admin.register(ProviderSettlementPayment)
class ProviderSettlementPaymentAdmin(admin.ModelAdmin):
    list_display = ("provider", "amount", "created_at", "created_by")
    search_fields = ("provider__email", "note")
    readonly_fields = ("created_at",)
from django.contrib import admin
from provider_panel.models import Provider

@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'deposit_commission', 'withdraw_commission', 'is_blocked', 'created_at')
    search_fields = ('name', 'phone')
    list_filter = ('is_blocked',)
# admin placeholder
