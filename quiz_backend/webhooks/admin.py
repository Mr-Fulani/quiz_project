from django.contrib import admin
from .models import Webhook, DefaultLink, MainFallbackLink

@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    """
    Админка для управления вебхуками
    """
    list_display = ('id', 'service_name', 'url', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'service_name', 'created_at')
    search_fields = ('service_name', 'url')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    actions = ['activate_webhooks', 'deactivate_webhooks']

    def activate_webhooks(self, request, queryset):
        """Активировать выбранные вебхуки"""
        queryset.update(is_active=True)
    activate_webhooks.short_description = 'Активировать выбранные вебхуки'

    def deactivate_webhooks(self, request, queryset):
        """Деактивировать выбранные вебхуки"""
        queryset.update(is_active=False)
    deactivate_webhooks.short_description = 'Деактивировать выбранные вебхуки'

@admin.register(DefaultLink)
class DefaultLinkAdmin(admin.ModelAdmin):
    """
    Админка для управления ссылками по умолчанию
    """
    list_display = ('id', 'language', 'topic', 'link')
    list_filter = ('language', 'topic')
    search_fields = ('language', 'topic', 'link')
    ordering = ('language', 'topic')

@admin.register(MainFallbackLink)
class MainFallbackLinkAdmin(admin.ModelAdmin):
    """
    Админка для управления основными резервными ссылками
    """
    list_display = ('id', 'language', 'link')
    list_filter = ('language',)
    search_fields = ('language', 'link')
    ordering = ('language',)

    def save_model(self, request, obj, form, change):
        """
        Приводим язык к нижнему регистру перед сохранением
        """
        obj.language = obj.language.lower()
        super().save_model(request, obj, form, change)
