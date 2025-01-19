"""
Конфигурация административной панели Django для моделей пользователей и групп.

Этот модуль содержит настройки отображения и управления моделями в админ-панели Django:
- User: Модель пользователя Telegram
- Group: Модель для каналов и групп Telegram
- UserChannelSubscription: Модель подписок пользователей на каналы
- Admin: Модель администраторов системы
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import User, Group, UserChannelSubscription, Admin


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """
    Настройка отображения модели User в админ-панели.

    Attributes:
        list_display: Отображаемые поля в списке пользователей
        list_filter: Фильтры для списка пользователей
        search_fields: Поля, по которым возможен поиск
    """
    list_display = ('id', 'telegram_id', 'username', 'is_active', 'language')
    list_filter = ('is_active', 'language')
    search_fields = ('telegram_id', 'username')
    readonly_fields = ('telegram_id',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('telegram_id', 'username', 'is_active', 'language')
        }),
        ('Контактная информация', {
            'fields': ('email', 'phone_number')
        }),
        ('Медиа', {
            'fields': ('avatar', 'photo')
        }),
    )

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """
    Настройка отображения модели Group в админ-панели.

    Attributes:
        list_display: Отображаемые поля в списке групп/каналов
        list_filter: Фильтры для списка групп
        search_fields: Поля, по которым возможен поиск
    """
    list_display = ('id', 'group_name', 'group_id', 'language', 'location_type')
    list_filter = ('location_type', 'language')
    search_fields = ('group_name', 'group_id')


@admin.register(UserChannelSubscription)
class UserChannelSubscriptionAdmin(admin.ModelAdmin):
    """
    Настройка отображения модели UserChannelSubscription в админ-панели.

    Attributes:
        list_display: Отображаемые поля в списке подписок
        list_filter: Фильтры для списка подписок
        search_fields: Поля, по которым возможен поиск
    """
    list_display = ('id', 'user', 'channel', 'subscription_status')
    list_filter = ('subscription_status',)
    search_fields = ('user__telegram_id', 'channel__group_name')






@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    """
    Настройка отображения модели Admin в админ-панели.

    Attributes:
        list_display: Отображаемые поля в списке администраторов
        list_filter: Фильтры для списка администраторов
        search_fields: Поля, по которым возможен поиск
        readonly_fields: Поля, которые нельзя редактировать
        fieldsets: Группировка полей при редактировании

    Methods:
        show_photo: Метод для отображения фотографии администратора в админ-панели
    """
    list_display = ('id', 'telegram_id', 'username', 'language', 'phone_number', 'is_active', 'show_photo')
    list_filter = ('language', 'is_active')
    search_fields = ('telegram_id', 'username', 'phone_number')
    readonly_fields = ('telegram_id',)
    fieldsets = (
        (None, {
            'fields': ('telegram_id', 'username', 'photo')
        }),
        ('Дополнительная информация', {
            'fields': ('language', 'phone_number', 'is_active'),
        }),
    )

    def show_photo(self, obj):
        """
        Отображает фотографию администратора в админ-панели.

        Args:
            obj: Экземпляр модели Admin

        Returns:
            str: HTML-код для отображения фотографии или текст "Нет фото"
        """
        if obj.photo:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />', obj.photo.url)
        return "Нет фото"
    show_photo.short_description = "Фото"  # Название колонки в админке

