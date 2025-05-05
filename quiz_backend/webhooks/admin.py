import logging
import re

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.html import format_html

from .models import Webhook

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
    list_display = ('id', 'url_link', 'service_name', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'service_name')
    search_fields = ('url', 'service_name')
    ordering = ('-created_at',)
    actions = ['activate_webhooks', 'deactivate_webhooks']
    readonly_fields = ('created_at', 'updated_at')

    def url_link(self, obj):
        """Отображает URL как кликабельную ссылку."""
        return format_html('<a href="{0}" target="_blank">{0}</a>', obj.url)

    url_link.short_description = 'URL'

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