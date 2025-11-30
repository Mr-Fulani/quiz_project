import logging
import re

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.html import format_html

from .models import Webhook, DefaultLink, MainFallbackLink, SocialMediaCredentials

logger = logging.getLogger(__name__)


class WebhookForm(forms.ModelForm):
    class Meta:
        model = Webhook
        fields = '__all__'

    def clean_url(self):
        """Добавляет https:// к URL и валидирует его."""
        url = self.cleaned_data.get('url')
        logger.debug(f"Очистка URL: {url}")

        if url and not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
            logger.debug(f"Добавлен https://, новый URL: {url}")

        # Валидация URL
        validator = URLValidator()
        try:
            validator(url)
        except ValidationError as e:
            logger.error(f"Некорректный URL: {url}, ошибка: {e}")
            raise ValidationError("Неверный формат URL. Пример: https://example.com/webhook")

        # Дополнительная проверка регулярным выражением
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, url):
            logger.error(f"URL не прошел проверку регулярным выражением: {url}")
            raise ValidationError("Неверный формат URL. Пример: https://example.com/webhook")

        return url

@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ('id', 'url_link', 'service_name', 'webhook_type', 'platforms_display', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'webhook_type', 'service_name')
    search_fields = ('url', 'service_name')
    ordering = ('-created_at',)
    actions = ['activate_webhooks', 'deactivate_webhooks']
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('service_name', 'url', 'webhook_type', 'is_active')
        }),
        ('Настройки для соцсетей', {
            'fields': ('target_platforms',),
            'description': 'Выберите платформы для этого webhook. Пример: ["instagram", "tiktok", "youtube_shorts"]'
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def url_link(self, obj):
        """Отображает URL как кликабельную ссылку."""
        return format_html('<a href="{0}" target="_blank">{0}</a>', obj.url)

    url_link.short_description = 'URL'
    
    def platforms_display(self, obj):
        """Отображает список платформ для webhook социальных сетей."""
        if obj.webhook_type == 'social_media' and obj.target_platforms:
            platforms = ', '.join(obj.target_platforms)
            return format_html('<span style="color: #007bff;">{}</span>', platforms)
        return '—'
    
    platforms_display.short_description = 'Платформы'

    def activate_webhooks(self, request, queryset):
        """Массовое действие для активации вебхуков."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Успешно активировано {updated} вебхуков.")

    activate_webhooks.short_description = "Активировать выбранные вебхуки"

    def deactivate_webhooks(self, request, queryset):
        """Массовое действие для деактивации вебхуков."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Успешно деактивировано {updated} вебхуков.")

    deactivate_webhooks.short_description = "Деактивировать выбранные вебхуки"

    form = WebhookForm

    def save_model(self, request, obj, form, change):
        """Логирует сохранение вебхука."""
        logger.debug(f"Сохранение вебхука, URL: {obj.url}")
        logger.info(f"Сохранен вебхук с URL: {obj.url}")
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        """Добавляет подсказку для поля URL."""
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['url'].help_text = (
            "Введите URL вебхука (например, example.com или https://example.com/webhook). "
            "Если протокол не указан, будет автоматически добавлен https://."
        )
        return form


@admin.register(DefaultLink)
class DefaultLinkAdmin(admin.ModelAdmin):
    """
    Админка для ссылок по умолчанию в кнопке 'Узнать больше о задаче'.
    Эта таблица используется и ботом и Django.
    """
    list_display = ('language', 'topic', 'link_display', 'id')
    list_filter = ('language', 'topic')
    search_fields = ('language', 'topic', 'link')
    ordering = ('language', 'topic')
    
    fieldsets = (
        (None, {
            'fields': ('language', 'topic', 'link'),
            'description': 'Ссылка по умолчанию для кнопки "Узнать больше" в Telegram опросах. Эта таблица используется и ботом и Django.'
        }),
    )
    
    def link_display(self, obj):
        """Отображает ссылку как кликабельную"""
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            obj.link, obj.link[:50] + '...' if len(obj.link) > 50 else obj.link
        )
    link_display.short_description = 'Ссылка'


@admin.register(MainFallbackLink)
class MainFallbackLinkAdmin(admin.ModelAdmin):
    """
    Админка для главных ссылок по языкам.
    Эти ссылки используются когда нет специфичной ссылки для топика.
    Таблица используется и ботом и Django.
    """
    list_display = ('language', 'link_display', 'id')
    list_filter = ('language',)
    search_fields = ('language', 'link')
    ordering = ('language',)
    
    fieldsets = (
        (None, {
            'fields': ('language', 'link'),
            'description': 'Главная ссылка для языка. Используется когда нет специфичной ссылки для топика. Эта таблица используется и ботом и Django.'
        }),
    )
    
    def link_display(self, obj):
        """Отображает ссылку как кликабельную"""
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            obj.link, obj.link[:50] + '...' if len(obj.link) > 50 else obj.link
        )
    link_display.short_description = 'Ссылка'


@admin.register(SocialMediaCredentials)
class SocialMediaCredentialsAdmin(admin.ModelAdmin):
    """
    Админка для учетных данных API социальных сетей.
    Используется для платформ с прямой интеграцией: Pinterest, Яндекс Дзен, Facebook.
    """
    list_display = ('platform', 'is_active', 'token_status_display', 'updated_at')
    list_filter = ('platform', 'is_active')
    search_fields = ('platform',)
    ordering = ('platform',)
    
    fieldsets = (
        ('Платформа', {
            'fields': ('platform', 'is_active'),
            'description': 'Выберите платформу и активируйте учетные данные'
        }),
        ('Токены доступа', {
            'fields': ('access_token', 'refresh_token', 'token_expires_at'),
            'description': 'Получите токены из разработческого портала соответствующей платформы'
        }),
        ('Дополнительные параметры', {
            'fields': ('extra_data',),
            'description': 'JSON данные: board_id для Pinterest, channel_id для Дзен, page_id для Facebook'
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def token_status_display(self, obj):
        """Отображает статус токена с цветовой индикацией."""
        if not obj.token_expires_at:
            return format_html('<span style="color: #666;">Не установлено</span>')
        
        from django.utils import timezone
        if obj.token_expires_at < timezone.now():
            return format_html('<span style="color: #dc3545;">⚠️ Истёк</span>')
        else:
            days_left = (obj.token_expires_at - timezone.now()).days
            if days_left < 7:
                return format_html(
                    '<span style="color: #ffc107;">⏰ Истекает через {} дней</span>',
                    days_left
                )
            else:
                return format_html(
                    '<span style="color: #28a745;">✅ Действует ({} дней)</span>',
                    days_left
                )
    
    token_status_display.short_description = 'Статус токена'
    
    def get_form(self, request, obj=None, **kwargs):
        """Добавляет подсказки для полей."""
        form = super().get_form(request, obj, **kwargs)
        
        form.base_fields['access_token'].widget.attrs['rows'] = 3
        form.base_fields['refresh_token'].widget.attrs['rows'] = 2
        
        form.base_fields['extra_data'].help_text = (
            'Примеры:\n'
            '• Pinterest: {"board_id": "123456789"}\n'
            '• Дзен: {"channel_id": "your-channel-id"}\n'
            '• Facebook: {"page_id": "123456789"}'
        )
        
        return form