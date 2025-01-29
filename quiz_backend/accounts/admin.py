from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, TelegramAdmin, DjangoAdmin, SuperAdmin

from .utils.telegram_notifications import notify_admin







@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Админка для модели CustomUser
    """
    list_display = ('username', 'subscription_status', 'language', 'created_at', 'deactivated_at')
    list_filter = ('subscription_status', 'language')
    search_fields = ('username', 'email')
    ordering = ('-created_at',)
    fieldsets = (
        (None, {'fields': ('username', 'password', 'email')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'language', 'subscription_status', 'deactivated_at')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
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
    Админка для Telegram администраторов.
    """
    list_display = ('username', 'telegram_id', 'email', 'is_active', 'phone_number', 'language')  # Telegram ID добавлен
    search_fields = ('username', 'telegram_id', 'email', 'phone_number')
    filter_horizontal = ('groups',)  # Удобный интерфейс для выбора групп
    fieldsets = (
        (None, {'fields': ('username', 'password', 'email', 'telegram_id')}),
        ('Personal Info', {'fields': ('phone_number', 'language', 'photo')}),
        ('Permissions', {'fields': ('is_active', 'is_telegram_admin', 'groups', 'user_permissions')}),
    )

    def save_model(self, request, obj, form, change):
        """
        Переопределяет сохранение объекта в админке.
        """
        super().save_model(request, obj, form, change)
        # Получаем список групп, к которым привязан администратор
        groups = obj.groups.all()
        notify_admin('added' if not change else 'updated', obj, groups)



    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'telegram_id', 'password1', 'password2', 'email', 'is_active', 'is_telegram_admin'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        print("Queryset for TelegramAdmin:", qs)
        return qs


@admin.register(DjangoAdmin)
class DjangoAdminAdmin(BaseAdminAdmin):
    """
    Админка для Django администраторов
    """
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_django_admin=True)


@admin.register(SuperAdmin)
class SuperAdminAdmin(BaseAdminAdmin):
    """
    Админка для супер администраторов
    """
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_super_admin=True)
