from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Donation


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ['name', 'amount', 'currency', 'status', 'payment_method', 'created_at']
    list_filter = ['status', 'currency', 'payment_method', 'created_at']
    search_fields = ['name', 'email', 'stripe_payment_intent_id']
    readonly_fields = ['stripe_payment_intent_id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        (_('Donation Information'), {
            'fields': ('name', 'email', 'amount', 'currency')
        }),
        (_('Payment Details'), {
            'fields': ('payment_method', 'status', 'stripe_payment_intent_id')
        }),
        (_('User Information'), {
            'fields': ('user',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        # Ограничиваем удаление завершенных донатов
        if obj and obj.status == 'completed':
            return False
        return super().has_delete_permission(request, obj) 