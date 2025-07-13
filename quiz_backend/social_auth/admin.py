from django.contrib import admin
from .models import SocialAccount, SocialLoginSession, SocialAuthSettings


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    """
    Админка для социальных аккаунтов.
    """
    list_display = [
        'user', 'provider', 'provider_user_id', 'username', 
        'is_active', 'created_at', 'last_login_at'
    ]
    list_filter = ['provider', 'is_active', 'created_at', 'last_login_at']
    search_fields = ['user__username', 'user__email', 'provider_user_id', 'username']
    readonly_fields = ['created_at', 'updated_at', 'last_login_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'provider', 'provider_user_id', 'is_active')
        }),
        ('Данные пользователя', {
            'fields': ('username', 'email', 'first_name', 'last_name', 'avatar_url')
        }),
        ('Токены', {
            'fields': ('access_token', 'refresh_token', 'token_expires_at'),
            'classes': ('collapse',)
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at', 'last_login_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_accounts', 'deactivate_accounts']
    
    def activate_accounts(self, request, queryset):
        """Активирует выбранные аккаунты."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} аккаунтов активировано.')
    activate_accounts.short_description = "Активировать выбранные аккаунты"
    
    def deactivate_accounts(self, request, queryset):
        """Деактивирует выбранные аккаунты."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} аккаунтов деактивировано.')
    deactivate_accounts.short_description = "Деактивировать выбранные аккаунты"


@admin.register(SocialLoginSession)
class SocialLoginSessionAdmin(admin.ModelAdmin):
    """
    Админка для сессий социальной аутентификации.
    """
    list_display = [
        'session_id', 'social_account', 'ip_address', 
        'is_successful', 'created_at'
    ]
    list_filter = ['is_successful', 'created_at', 'social_account__provider']
    search_fields = ['session_id', 'social_account__user__username', 'ip_address']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('session_id', 'social_account', 'is_successful')
        }),
        ('Детали запроса', {
            'fields': ('ip_address', 'user_agent', 'error_message')
        }),
        ('Дата', {
            'fields': ('created_at',)
        }),
    )
    
    def has_add_permission(self, request):
        """Запрещаем создание сессий вручную."""
        return False


@admin.register(SocialAuthSettings)
class SocialAuthSettingsAdmin(admin.ModelAdmin):
    """
    Админка для настроек социальной аутентификации.
    """
    list_display = ['provider', 'client_id', 'is_enabled', 'updated_at']
    list_filter = ['provider', 'is_enabled']
    search_fields = ['provider']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['provider']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('provider', 'is_enabled')
        }),
        ('Конфигурация', {
            'fields': ('client_id', 'client_secret')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['enable_providers', 'disable_providers']
    
    def enable_providers(self, request, queryset):
        """Включает выбранные провайдеры."""
        updated = queryset.update(is_enabled=True)
        self.message_user(request, f'{updated} провайдеров включено.')
    enable_providers.short_description = "Включить выбранные провайдеры"
    
    def disable_providers(self, request, queryset):
        """Отключает выбранные провайдеры."""
        updated = queryset.update(is_enabled=False)
        self.message_user(request, f'{updated} провайдеров отключено.')
    disable_providers.short_description = "Отключить выбранные провайдеры"
