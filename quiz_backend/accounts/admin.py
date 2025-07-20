from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from accounts.models import CustomUser, TelegramUser, TelegramAdmin, TelegramAdminGroup, DjangoAdmin, UserChannelSubscription, MiniAppUser


class TelegramAdminGroupInline(admin.TabularInline):
    """
    Inline-форма для связи TelegramAdmin с группами/каналами.
    """
    model = TelegramAdminGroup
    extra = 1
    verbose_name = "Группа/Канал"
    verbose_name_plural = "Группы/Каналы"
    fields = ['telegram_group']
    raw_id_fields = ['telegram_group']


class TelegramAdminAdmin(admin.ModelAdmin):
    """
    Админ-панель для TelegramAdmin.
    """
    list_display = ['telegram_id', 'username', 'language', 'is_active', 'photo', 'group_count']
    search_fields = ['telegram_id', 'username']
    list_filter = ['is_active', 'language']
    inlines = [TelegramAdminGroupInline]
    actions = ['make_active', 'make_inactive']

    def group_count(self, obj):
        """
        Подсчёт групп/каналов админа.
        """
        return obj.groups.count()
    group_count.short_description = 'Группы'

    def make_active(self, request, queryset):
        """
        Активировать админов.
        """
        queryset.update(is_active=True)
    make_active.short_description = "Активировать админов"

    def make_inactive(self, request, queryset):
        """
        Деактивировать админов.
        """
        queryset.update(is_active=False)
    make_inactive.short_description = "Деактивировать админов"


class DjangoAdminAdmin(admin.ModelAdmin):
    """
    Админ-панель для DjangoAdmin.
    """
    list_display = ['username', 'email', 'is_django_admin', 'is_staff', 'is_active', 'last_login']
    search_fields = ['username', 'email', 'phone_number']
    list_filter = ['is_django_admin', 'is_staff', 'is_active']
    actions = ['make_staff', 'remove_staff']

    def make_staff(self, request, queryset):
        """
        Дать права персонала.
        """
        queryset.update(is_staff=True)
    make_staff.short_description = "Сделать персоналом"

    def remove_staff(self, request, queryset):
        """
        Убрать права персонала.
        """
        queryset.update(is_staff=False)
    remove_staff.short_description = "Убрать права персонала"


class CustomUserAdmin(UserAdmin):
    """
    Админ-панель для CustomUser с действием для создания DjangoAdmin.
    """
    model = CustomUser
    list_display = ['username', 'email', 'is_active', 'is_staff', 'telegram_id', 'subscription_status', 'created_at']
    search_fields = ['username', 'email', 'telegram_id']
    list_filter = ['is_active', 'is_staff', 'subscription_status', 'language']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Персональная информация', {'fields': ('email', 'telegram_id', 'avatar', 'bio', 'location', 'birth_date', 'website')}),
        ('Социальные сети', {'fields': ('telegram', 'github', 'instagram', 'facebook', 'linkedin', 'youtube')}),
        ('Статистика', {'fields': ('total_points', 'quizzes_completed', 'average_score', 'favorite_category')}),
        ('Настройки', {'fields': ('language', 'is_telegram_user', 'email_notifications', 'is_public', 'theme_preference')}),
        ('Разрешения', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'date_joined', 'deactivated_at', 'last_seen')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'telegram_id', 'password1', 'password2', 'is_active', 'is_staff'),
        }),
    )
    actions = ['make_django_admin']

    def make_django_admin(self, request, queryset):
        """
        Создаёт DjangoAdmin из выбранных CustomUser.
        """
        for user in queryset:
            if not DjangoAdmin.objects.filter(username=user.username).exists():
                DjangoAdmin.objects.create(
                    username=user.username,
                    email=user.email,
                    password=user.password,
                    is_django_admin=True,
                    is_staff=True,
                    language=user.language or 'ru',
                    phone_number=None
                )
        self.message_user(request, f"Выбранные пользователи добавлены как DjangoAdmin.")
    make_django_admin.short_description = "Сделать Django-админом"


class TelegramUserAdmin(admin.ModelAdmin):
    """
    Админ-панель для TelegramUser.
    """
    list_display = ['telegram_id', 'username', 'first_name', 'last_name', 'subscription_status', 'language', 'is_premium', 'created_at']
    search_fields = ['telegram_id', 'username', 'first_name', 'last_name']
    list_filter = ['subscription_status', 'language', 'is_premium', 'created_at']
    actions = ['make_premium', 'remove_premium']

    def make_premium(self, request, queryset):
        """
        Дать премиум-статус.
        """
        queryset.update(is_premium=True)
    make_premium.short_description = "Дать премиум-статус"

    def remove_premium(self, request, queryset):
        """
        Убрать премиум-статус.
        """
        queryset.update(is_premium=False)
    remove_premium.short_description = "Убрать премиум-статус"


class UserChannelSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['telegram_user', 'channel', 'subscription_status', 'subscribed_at']
    search_fields = ['telegram_user__username', 'channel__group_name', 'channel__group_id']
    list_filter = ['subscription_status', 'subscribed_at']
    raw_id_fields = ['telegram_user', 'channel']
    actions = ['subscribe', 'unsubscribe']

    def subscribe(self, request, queryset):
        for subscription in queryset:
            subscription.subscribe()
    subscribe.short_description = "Активировать подписку"

    def unsubscribe(self, request, queryset):
        for subscription in queryset:
            subscription.unsubscribe()
    unsubscribe.short_description = "Деактивировать подписку"


class MiniAppUserAdmin(admin.ModelAdmin):
    """
    Админ-панель для MiniAppUser.
    """
    list_display = ['telegram_id', 'username', 'full_name', 'language', 'is_admin', 'admin_type', 'created_at', 'last_seen']
    search_fields = ['telegram_id', 'username', 'first_name', 'last_name']
    list_filter = ['language', 'created_at', 'last_seen']
    readonly_fields = ['created_at', 'last_seen', 'is_admin', 'admin_type', 'full_name']
    raw_id_fields = ['telegram_user', 'telegram_admin', 'django_admin']
    actions = ['update_last_seen', 'link_to_existing_users']

    def update_last_seen(self, request, queryset):
        """
        Обновляет время последнего визита для выбранных пользователей.
        """
        for user in queryset:
            user.update_last_seen()
        self.message_user(request, f"Время последнего визита обновлено для {queryset.count()} пользователей.")
    update_last_seen.short_description = "Обновить время последнего визита"

    def link_to_existing_users(self, request, queryset):
        """
        Автоматически связывает MiniAppUser с существующими пользователями.
        """
        linked_count = 0
        for mini_app_user in queryset:
            try:
                # Пытаемся связать с TelegramUser
                telegram_user = TelegramUser.objects.filter(telegram_id=mini_app_user.telegram_id).first()
                if telegram_user and not mini_app_user.telegram_user:
                    mini_app_user.link_to_telegram_user(telegram_user)
                    linked_count += 1
                
                # Пытаемся связать с TelegramAdmin
                telegram_admin = TelegramAdmin.objects.filter(telegram_id=mini_app_user.telegram_id).first()
                if telegram_admin and not mini_app_user.telegram_admin:
                    mini_app_user.link_to_telegram_admin(telegram_admin)
                    linked_count += 1
                
                # Пытаемся связать с DjangoAdmin (по username)
                if mini_app_user.username:
                    django_admin = DjangoAdmin.objects.filter(username=mini_app_user.username).first()
                    if django_admin and not mini_app_user.django_admin:
                        mini_app_user.link_to_django_admin(django_admin)
                        linked_count += 1
                        
            except Exception as e:
                self.message_user(request, f"Ошибка при связывании пользователя {mini_app_user.telegram_id}: {e}", level='ERROR')
        
        self.message_user(request, f"Связано {linked_count} пользователей.")
    link_to_existing_users.short_description = "Связать с существующими пользователями"


# Регистрация моделей
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(TelegramUser, TelegramUserAdmin)
admin.site.register(TelegramAdmin, TelegramAdminAdmin)
admin.site.register(DjangoAdmin, DjangoAdminAdmin)
admin.site.register(UserChannelSubscription, UserChannelSubscriptionAdmin)
admin.site.register(MiniAppUser, MiniAppUserAdmin)