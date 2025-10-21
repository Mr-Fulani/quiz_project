from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from .models import Donation
from .utils import export_donations_csv, send_donation_thank_you_email


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'amount_formatted', 'currency', 'payment_type_display', 
        'crypto_currency', 'source', 'status_colored', 'payment_method', 
        'created_at', 'days_ago'
    ]
    list_filter = [
        'status', 'payment_type', 'currency', 'crypto_currency', 
        'payment_method', 'source', 'created_at', 'coingate_status'
    ]
    search_fields = [
        'name', 'email', 'stripe_payment_intent_id', 
        'coingate_order_id', 'crypto_transaction_hash', 'crypto_payment_address'
    ]
    readonly_fields = [
        'stripe_payment_intent_id', 'coingate_order_id', 'coingate_status',
        'crypto_payment_address', 'crypto_transaction_hash', 'crypto_amount',
        'created_at', 'updated_at', 'coingate_order_link'
    ]
    ordering = ['-created_at']
    actions = ['mark_as_completed', 'mark_as_failed', 'export_to_csv', 'send_thank_you_emails']
    
    fieldsets = (
        ('Общая информация', {
            'fields': ('name', 'email', 'amount', 'currency', 'source', 'user')
        }),
        ('Тип платежа', {
            'fields': ('payment_type', 'payment_method', 'status')
        }),
        ('Fiat платеж (Stripe)', {
            'fields': ('stripe_payment_intent_id',),
            'classes': ('collapse',)
        }),
        ('Крипто-платеж (CoinGate)', {
            'fields': (
                'crypto_currency', 'crypto_amount', 'crypto_payment_address',
                'coingate_order_id', 'coingate_order_link', 'coingate_status',
                'crypto_transaction_hash'
            ),
            'classes': ('collapse',)
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        # Суперпользователь может удалять любые донаты
        if request.user.is_superuser:
            return True
        # Обычные пользователи не могут удалять завершенные донаты
        if obj and obj.status == 'completed':
            return False
        return super().has_delete_permission(request, obj)
    
    def amount_formatted(self, obj):
        """Форматированная сумма доната"""
        if obj.payment_type == 'crypto' and obj.crypto_amount:
            return f"{obj.crypto_amount} {obj.crypto_currency} (≈${obj.amount})"
        return f"${obj.amount} {obj.currency.upper()}"
    amount_formatted.short_description = 'Сумма'
    amount_formatted.admin_order_field = 'amount'
    
    def payment_type_display(self, obj):
        """Отображение типа платежа с иконкой"""
        if obj.payment_type == 'crypto':
            return format_html('<span style="color: #f7931a;">🪙 Crypto</span>')
        return format_html('<span style="color: #635bff;">💳 Card</span>')
    payment_type_display.short_description = 'Тип'
    payment_type_display.admin_order_field = 'payment_type'
    
    def coingate_order_link(self, obj):
        """Ссылка на заказ в CoinGate"""
        if obj.coingate_order_id and obj.payment_type == 'crypto':
            from django.conf import settings
            env = settings.COINGATE_ENVIRONMENT
            if env == 'sandbox':
                url = f'https://sandbox.coingate.com/orders/{obj.coingate_order_id}'
            else:
                url = f'https://coingate.com/orders/{obj.coingate_order_id}'
            return format_html(
                '<a href="{}" target="_blank">Открыть в CoinGate ↗</a>',
                url
            )
        return '-'
    coingate_order_link.short_description = 'Заказ CoinGate'
    
    def status_colored(self, obj):
        """Цветной статус"""
        colors = {
            'pending': '#ffc107',      # желтый
            'completed': '#28a745',    # зеленый
            'failed': '#dc3545',       # красный
            'cancelled': '#6c757d'     # серый
        }
        color = colors.get(obj.status, '#000000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = 'Статус'
    status_colored.admin_order_field = 'status'
    
    def days_ago(self, obj):
        """Сколько дней назад был создан донат"""
        delta = timezone.now() - obj.created_at
        return f'{delta.days} дней назад'
    days_ago.short_description = 'Дней назад'
    days_ago.admin_order_field = 'created_at'
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('user')
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем статистику на страницу списка"""
        response = super().changelist_view(request, extra_context=extra_context)
        
        # Получаем общую статистику
        total_donations = Donation.objects.count()
        completed_donations = Donation.objects.filter(status='completed').count()
        
        # Статистика за последние 30 дней
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_donations = Donation.objects.filter(
            created_at__gte=thirty_days_ago
        ).count()
        
        # Статистика по источникам
        source_stats = {}
        for source_code, source_name in Donation.SOURCE_CHOICES:
            source_donations = Donation.objects.filter(source=source_code)
            source_completed = source_donations.filter(status='completed')
            source_recent = source_donations.filter(created_at__gte=thirty_days_ago)
            
            source_stats[source_code] = {
                'name': source_name,
                'total_donations': source_donations.count(),
                'completed_donations': source_completed.count(),
                'total_amount_usd': source_completed.filter(currency='usd').aggregate(total=Sum('amount'))['total'] or 0,
                'recent_donations': source_recent.count(),
            }
        
        # Статистика по валютам
        currency_stats = {}
        for currency_code, currency_name in Donation.CURRENCY_CHOICES:
            # Общая статистика по валюте
            currency_donations = Donation.objects.filter(currency=currency_code)
            currency_completed = currency_donations.filter(status='completed')
            
            # Статистика за 30 дней по валюте
            currency_recent = currency_donations.filter(created_at__gte=thirty_days_ago)
            currency_recent_completed = currency_recent.filter(status='completed')
            
            currency_stats[currency_code] = {
                'name': currency_name,
                'total_donations': currency_donations.count(),
                'completed_donations': currency_completed.count(),
                'pending_donations': currency_donations.filter(status='pending').count(),
                'failed_donations': currency_donations.filter(status='failed').count(),
                'total_amount': currency_completed.aggregate(total=Sum('amount'))['total'] or 0,
                'recent_donations': currency_recent.count(),
                'recent_completed': currency_recent_completed.count(),
                'recent_amount': currency_recent_completed.aggregate(total=Sum('amount'))['total'] or 0,
            }
        
        # Статистика по типам платежей
        payment_type_stats = {}
        for payment_type_code, payment_type_name in Donation.PAYMENT_TYPE_CHOICES:
            type_donations = Donation.objects.filter(payment_type=payment_type_code)
            type_completed = type_donations.filter(status='completed')
            type_recent = type_donations.filter(created_at__gte=thirty_days_ago)
            
            payment_type_stats[payment_type_code] = {
                'name': payment_type_name,
                'total_donations': type_donations.count(),
                'completed_donations': type_completed.count(),
                'total_amount_usd': type_completed.aggregate(total=Sum('amount'))['total'] or 0,
                'recent_donations': type_recent.count(),
            }
        
        # Статистика по криптовалютам
        crypto_stats = {}
        crypto_donations = Donation.objects.filter(payment_type='crypto')
        if crypto_donations.exists():
            for currency in crypto_donations.values_list('crypto_currency', flat=True).distinct():
                if currency:
                    currency_donations = crypto_donations.filter(crypto_currency=currency)
                    currency_completed = currency_donations.filter(status='completed')
                    
                    crypto_stats[currency] = {
                        'total_donations': currency_donations.count(),
                        'completed_donations': currency_completed.count(),
                        'total_amount_usd': currency_completed.aggregate(total=Sum('amount'))['total'] or 0,
                    }
        
        if hasattr(response, 'context_data'):
            response.context_data['donation_stats'] = {
                'total_donations': total_donations,
                'completed_donations': completed_donations,
                'pending_donations': Donation.objects.filter(status='pending').count(),
                'failed_donations': Donation.objects.filter(status='failed').count(),
                'recent_donations': recent_donations,
                'currency_stats': currency_stats,
                'source_stats': source_stats,
                'payment_type_stats': payment_type_stats,
                'crypto_stats': crypto_stats,
            }
        
        return response
    
    # Массовые действия
    def mark_as_completed(self, request, queryset):
        """Массово отметить донаты как завершенные"""
        updated = queryset.update(status='completed')
        self.message_user(
            request,
            f'Успешно отмечено как завершенные: {updated} донатов.'
        )
    mark_as_completed.short_description = 'Отметить выбранные донаты как завершенные'
    
    def mark_as_failed(self, request, queryset):
        """Массово отметить донаты как неудачные"""
        updated = queryset.update(status='failed')
        self.message_user(
            request,
            f'Успешно отмечено как неудачные: {updated} донатов.'
        )
    mark_as_failed.short_description = 'Отметить выбранные донаты как неудачные'
    
    def export_to_csv(self, request, queryset):
        """Экспорт выбранных донатов в CSV"""
        return export_donations_csv(request, queryset)
    export_to_csv.short_description = 'Экспортировать выбранные донаты в CSV'
    
    def send_thank_you_emails(self, request, queryset):
        """Отправить благодарственные письма"""
        completed_donations = queryset.filter(status='completed')
        sent_count = 0
        
        for donation in completed_donations:
            if send_donation_thank_you_email(donation):
                sent_count += 1
        
        self.message_user(
            request,
            f'Отправлено {sent_count} благодарственных писем из {completed_donations.count()} завершенных донатов.'
        )
    send_thank_you_emails.short_description = 'Отправить благодарственные письма завершенным донатам' 