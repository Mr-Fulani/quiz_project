# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, TelegramAdmin, DjangoAdmin, SuperAdmin, UserChannelSubscription, TelegramUser
from .utils.telegram_notifications import notify_admin


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Админ-панель для CustomUser с объединёнными полями из Profile.
    """
    list_display = ('username', 'subscription_status', 'language', 'created_at', 'deactivated_at')
    list_filter = ('subscription_status', 'language', 'is_public', 'theme_preference')
    search_fields = ('username', 'email', 'bio', 'location')
    ordering = ('-created_at',)
    fieldsets = (
        (None, {'fields': ('username', 'password', 'email')}),
        ('Personal Info', {
            'fields': (
                'first_name', 'last_name', 'language', 'subscription_status', 'deactivated_at',
                'avatar', 'bio', 'location', 'birth_date', 'website'
            )
        }),
        ('Social Networks', {
            'fields': ('telegram', 'github', 'instagram', 'facebook', 'linkedin', 'youtube')
        }),
        ('Settings', {
            'fields': ('is_public', 'email_notifications', 'theme_preference')
        }),
        ('Statistics', {
            'fields': ('total_points', 'quizzes_completed', 'average_score', 'favorite_category')
        }),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'last_seen')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'email', 'is_active'),
        }),
    )


class BaseAdminAdmin(UserAdmin):
    """
    Базовая админка для всех типов администраторов.
    """
    list_display = ('username', 'email', 'is_active', 'is_superuser', 'phone_number', 'language')
    search_fields = ('username', 'email', 'phone_number')
    list_filter = ('is_active', 'is_superuser', 'is_telegram_admin', 'is_django_admin', 'is_super_admin')


@admin.register(TelegramAdmin)
class TelegramAdminAdmin(BaseAdminAdmin):
    """
    Админка для Telegram-администраторов.
    """
    list_display = ('username', 'telegram_id', 'email', 'is_active', 'phone_number', 'language')
    search_fields = ('username', 'telegram_id', 'email', 'phone_number')
    filter_horizontal = ('groups',)
    fieldsets = (
        (None, {'fields': ('username', 'password', 'email', 'telegram_id')}),
        ('Personal Info', {'fields': ('phone_number', 'language', 'photo')}),
        ('Permissions', {'fields': ('is_active', 'is_telegram_admin', 'groups', 'user_permissions')}),
    )

    def save_model(self, request, obj, form, change):
        """Сохранение объекта с уведомлением."""
        super().save_model(request, obj, form, change)
        groups = obj.groups.all()
        notify_admin('added' if not change else 'updated', obj, groups)

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'telegram_id', 'password1', 'password2', 'email', 'is_active', 'is_telegram_admin'),
        }),
    )


@admin.register(DjangoAdmin)
class DjangoAdminAdmin(BaseAdminAdmin):
    """
    Админка для Django-администраторов.
    """
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_django_admin=True)


@admin.register(SuperAdmin)
class SuperAdminAdmin(BaseAdminAdmin):
    """
    Админка для супер-администраторов.
    """
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_super_admin=True)


@admin.register(UserChannelSubscription)
class UserChannelSubscriptionAdmin(admin.ModelAdmin):
    """
    Админка для подписок на каналы.
    """
    list_display = ["id", "user", "channel", "subscription_status", "subscribed_at", "unsubscribed_at"]
    list_filter = ["subscription_status", "channel"]
    search_fields = ["user__username", "channel__group_name"]


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    """
    Админка для Telegram-пользователей.
    """
    list_display = ('telegram_id', 'username', 'first_name', 'last_name', 'linked_user')
    search_fields = ('telegram_id', 'username', 'first_name', 'last_name')
