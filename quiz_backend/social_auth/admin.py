from django.contrib import admin
from .models import SocialAccount, SocialLoginSession, SocialAuthSettings


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    """
    Админка для социальных аккаунтов с интеграцией с другими системами пользователей.
    """
    list_display = [
        'user', 'provider', 'provider_user_id', 'username', 
        'is_active', 'is_admin', 'admin_type', 'auth_methods_display',
        'created_at', 'last_login_at'
    ]
    list_filter = [
        'provider', 'is_active', 'created_at', 'last_login_at',
        'telegram_user', 'mini_app_user', 'telegram_admin', 'django_admin'
    ]
    search_fields = [
        'user__username', 'user__email', 'provider_user_id', 'username',
        'first_name', 'last_name'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'last_login_at', 'is_admin', 
        'admin_type', 'auth_methods_display'
    ]
    raw_id_fields = ['telegram_user', 'mini_app_user', 'telegram_admin', 'django_admin']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'provider', 'provider_user_id', 'is_active')
        }),
        ('Данные пользователя', {
            'fields': ('username', 'email', 'first_name', 'last_name', 'avatar_url')
        }),
        ('Интеграция с другими системами', {
            'fields': (
                'telegram_user', 'mini_app_user', 'telegram_admin', 'django_admin',
                'is_admin', 'admin_type', 'auth_methods_display'
            ),
            'classes': ('collapse',)
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
    
    actions = [
        'activate_accounts', 'deactivate_accounts', 
        'auto_link_existing_users', 'link_to_existing_users'
    ]
    
    def is_admin(self, obj):
        """
        Отображает статус админа.
        """
        return obj.is_admin
    is_admin.boolean = True
    is_admin.short_description = 'Админ'
    
    def admin_type(self, obj):
        """
        Отображает тип админа.
        """
        return obj.admin_type or '-'
    admin_type.short_description = 'Тип админа'
    
    def auth_methods_display(self, obj):
        """
        Отображает методы авторизации.
        """
        methods = obj.auth_methods
        if len(methods) > 2:
            return f"{', '.join(methods[:2])} +{len(methods)-2}"
        return ', '.join(methods)
    auth_methods_display.short_description = 'Методы авторизации'
    
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
    
    def auto_link_existing_users(self, request, queryset):
        """
        Автоматически связывает SocialAccount с существующими пользователями.
        """
        linked_count = 0
        for social_account in queryset:
            try:
                linked_count += social_account.auto_link_existing_users()
            except Exception as e:
                self.message_user(
                    request, 
                    f"Ошибка при связывании аккаунта {social_account.provider_user_id}: {e}", 
                    level='ERROR'
                )
        
        self.message_user(request, f"Связано {linked_count} аккаунтов.")
    auto_link_existing_users.short_description = "Автоматически связать с существующими пользователями"
    
    def link_to_existing_users(self, request, queryset):
        """
        Ручное связывание SocialAccount с существующими пользователями.
        """
        linked_count = 0
        for social_account in queryset:
            try:
                # Пытаемся связать с TelegramUser
                from accounts.models import TelegramUser
                telegram_user = TelegramUser.objects.filter(
                    telegram_id=int(social_account.provider_user_id)
                ).first()
                if telegram_user and not social_account.telegram_user:
                    social_account.link_to_telegram_user(telegram_user)
                    linked_count += 1
                
                # Пытаемся связать с MiniAppUser
                from accounts.models import MiniAppUser
                mini_app_user = MiniAppUser.objects.filter(
                    telegram_id=int(social_account.provider_user_id)
                ).first()
                if mini_app_user and not social_account.mini_app_user:
                    social_account.link_to_mini_app_user(mini_app_user)
                    linked_count += 1
                
                # Пытаемся связать с TelegramAdmin
                from accounts.models import TelegramAdmin
                telegram_admin = TelegramAdmin.objects.filter(
                    telegram_id=int(social_account.provider_user_id)
                ).first()
                if telegram_admin and not social_account.telegram_admin:
                    social_account.link_to_telegram_admin(telegram_admin)
                    linked_count += 1
                
                # Пытаемся связать с DjangoAdmin (по username)
                if social_account.username:
                    from accounts.models import DjangoAdmin
                    django_admin = DjangoAdmin.objects.filter(
                        username=social_account.username
                    ).first()
                    if django_admin and not social_account.django_admin:
                        social_account.link_to_django_admin(django_admin)
                        linked_count += 1
                        
            except Exception as e:
                self.message_user(
                    request, 
                    f"Ошибка при связывании аккаунта {social_account.provider_user_id}: {e}", 
                    level='ERROR'
                )
        
        self.message_user(request, f"Связано {linked_count} аккаунтов.")
    link_to_existing_users.short_description = "Связать с существующими пользователями"


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
