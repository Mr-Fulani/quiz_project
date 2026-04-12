# tenants/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import Tenant
from .middleware import clear_tenant_cache


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """
    Adminка для управления тенантами.
    Видна ТОЛЬКО суперпользователям.
    """
    list_display = [
        'slug', 'name', 'domain_link', 'mini_app_domain',
        'bot_username_link', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'default_language']
    search_fields = ['slug', 'name', 'domain', 'bot_username']
    readonly_fields = ['created_at', 'updated_at', 'site_url_display', 'bot_link_display']
    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        ('🏢 Идентификация', {
            'fields': ('slug', 'name', 'is_active')
        }),
        ('🌐 Домены', {
            'fields': ('domain', 'mini_app_domain', 'site_url_display')
        }),
        ('🤖 Telegram Бот', {
            'fields': ('bot_token', 'bot_username', 'bot_link_display')
        }),
        ('🎨 Брендинг', {
            'fields': ('site_name', 'site_description', 'theme_color', 'logo')
        }),
        ('🔍 SEO', {
            'fields': ('default_language', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('📅 Мета', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_module_perms(self, request):
        """Только суперпользователи видят этот раздел."""
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def domain_link(self, obj):
        url = f'https://{obj.domain}'
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.domain)
    domain_link.short_description = 'Домен'

    def bot_username_link(self, obj):
        if obj.bot_username:
            url = f'https://t.me/{obj.bot_username}'
            return format_html('<a href="{}" target="_blank">@{}</a>', url, obj.bot_username)
        return '—'
    bot_username_link.short_description = 'Бот'

    def site_url_display(self, obj):
        return format_html(
            '<a href="{url}" target="_blank">{url}</a>',
            url=obj.site_url
        )
    site_url_display.short_description = 'URL сайта'

    def bot_link_display(self, obj):
        if obj.bot_link:
            return format_html(
                '<a href="{url}" target="_blank">{url}</a>',
                url=obj.bot_link
            )
        return '—'
    bot_link_display.short_description = 'Ссылка на бота'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Очищаем кэш тенантов при изменении
        clear_tenant_cache()
