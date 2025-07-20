import sys
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from accounts.models import CustomUser, TelegramUser, TelegramAdmin, TelegramAdminGroup, DjangoAdmin, UserChannelSubscription, MiniAppUser

# Импортируем миксин для сводной информации
try:
    from .admin_overview import UserOverviewMixin
except ImportError:
    # Если файл не найден, создаем пустой миксин
    class UserOverviewMixin:
        pass


class SocialAccountInline(admin.TabularInline):
    """
    Inline-форма для отображения социальных аккаунтов пользователя.
    """
    from social_auth.models import SocialAccount
    
    model = SocialAccount
    extra = 0
    verbose_name = "Социальный аккаунт"
    verbose_name_plural = "Социальные аккаунты"
    readonly_fields = ['provider', 'provider_user_id', 'is_active', 'created_at', 'last_login_at']
    fields = ['provider', 'provider_user_id', 'username', 'is_active', 'created_at']
    
    def has_add_permission(self, request, obj=None):
        """Запрещаем создание социальных аккаунтов вручную."""
        return False


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


from .telegram_admin_service import TelegramAdminService, run_async_function


class TelegramAdminAdmin(admin.ModelAdmin):
    """
    Админ-панель для TelegramAdmin с интеграцией Telegram Bot API.
    """
    list_display = ['telegram_id', 'username', 'language', 'is_active', 'photo', 'group_count']
    search_fields = ['telegram_id', 'username']
    list_filter = ['is_active', 'language']
    inlines = [TelegramAdminGroupInline]
    actions = [
        'make_active', 'make_inactive', 
        'remove_admin_rights_from_all_channels', 'remove_admin_rights_from_selected_channels',
        'delete_admin_completely', 'remove_user_from_all_channels', 'remove_user_from_selected_channels',
        'ban_from_all_channels', 'unban_from_all_channels',
        'check_bot_permissions'
    ]

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
        self.message_user(request, f"Активировано {queryset.count()} админов.")
    make_active.short_description = "Активировать админов"

    def make_inactive(self, request, queryset):
        """
        Деактивировать админов.
        """
        queryset.update(is_active=False)
        self.message_user(request, f"Деактивировано {queryset.count()} админов.")
    make_inactive.short_description = "Деактивировать админов"

    def remove_admin_rights_from_all_channels(self, request, queryset):
        """
        Удаляет права администратора из всех каналов, но оставляет админа в таблице.
        """
        total_removed = 0
        
        for admin in queryset:
            channel_ids = [group.group_id for group in admin.groups.all()]
            if channel_ids:
                service = TelegramAdminService()
                try:
                    success_count, messages = run_async_function(
                        service.remove_admin_from_all_channels,
                        admin.telegram_id,
                        channel_ids
                    )
                    total_removed += success_count
                    
                    # Показываем сообщения
                    for message in messages:
                        if "успешно" in message:
                            self.message_user(request, message, level='SUCCESS')
                        else:
                            self.message_user(request, message, level='ERROR')
                finally:
                    service.close()
        
        # Удаляем связи из базы данных
        for admin in queryset:
            admin.groups.clear()
        
        self.message_user(
            request, 
            f"Удалены права администратора у {total_removed} пользователей из каналов. Связи в базе данных очищены."
        )
    remove_admin_rights_from_all_channels.short_description = "👤 Убрать права админа из всех каналов"

    def remove_admin_rights_from_selected_channels(self, request, queryset):
        """
        Удаляет права администратора из выбранных каналов.
        """
        # Здесь можно добавить форму для выбора каналов
        self.message_user(request, "Функция в разработке. Используйте 'Убрать права админа из всех каналов'.")
    remove_admin_rights_from_selected_channels.short_description = "👤 Убрать права админа из выбранных каналов"

    def delete_admin_completely(self, request, queryset):
        """
        Полностью удаляет админов: убирает права из Telegram + удаляет из таблицы админов.
        """
        total_removed = 0
        
        for admin in queryset:
            channel_ids = [group.group_id for group in admin.groups.all()]
            if channel_ids:
                service = TelegramAdminService()
                try:
                    success_count, messages = run_async_function(
                        service.remove_admin_from_all_channels,
                        admin.telegram_id,
                        channel_ids
                    )
                    total_removed += success_count
                    
                    # Показываем сообщения
                    for message in messages:
                        if "успешно" in message:
                            self.message_user(request, message, level='SUCCESS')
                        else:
                            self.message_user(request, message, level='ERROR')
                finally:
                    service.close()
        
        # Полностью удаляем админов из базы данных
        admin_count = queryset.count()
        queryset.delete()
        
        self.message_user(
            request, 
            f"Полностью удалено {admin_count} администраторов: права убраны из Telegram, записи удалены из базы данных."
        )
    delete_admin_completely.short_description = "🗑️ Полностью удалить админа (Telegram + БД)"

    def remove_user_from_all_channels(self, request, queryset):
        """
        Полностью удаляет админов из всех их каналов (кикает).
        """
        total_removed = 0
        
        for admin in queryset:
            channel_ids = [group.group_id for group in admin.groups.all()]
            if channel_ids:
                service = TelegramAdminService()
                try:
                    success_count, messages = run_async_function(
                        service.remove_user_from_all_channels,
                        admin.telegram_id,
                        channel_ids
                    )
                    total_removed += success_count
                    
                    # Показываем сообщения
                    for message in messages:
                        if "успешно" in message:
                            self.message_user(request, message, level='SUCCESS')
                        else:
                            self.message_user(request, message, level='ERROR')
                finally:
                    service.close()
        
        # Удаляем связи из базы данных
        for admin in queryset:
            admin.groups.clear()
        
        self.message_user(
            request, 
            f"Удалено {total_removed} пользователей из каналов. Связи в базе данных очищены."
        )
    remove_user_from_all_channels.short_description = "🚫 Удалить из всех каналов (кик)"

    def remove_user_from_selected_channels(self, request, queryset):
        """
        Удаляет админов из выбранных каналов.
        """
        # Здесь можно добавить форму для выбора каналов
        self.message_user(request, "Функция в разработке. Используйте 'Удалить из всех каналов'.")
    remove_user_from_selected_channels.short_description = "🚫 Удалить из выбранных каналов"

    def ban_from_all_channels(self, request, queryset):
        """
        Банит админов во всех их каналах.
        """
        service = TelegramAdminService()
        total_banned = 0
        
        for admin in queryset:
            channel_ids = [group.group_id for group in admin.groups.all()]
            for chat_id in channel_ids:
                success, message = run_async_function(
                    service.ban_user_from_channel,
                    chat_id,
                    admin.telegram_id
                )
                if success:
                    total_banned += 1
                    self.message_user(request, message, level='SUCCESS')
                else:
                    self.message_user(request, message, level='ERROR')
        
        service.close()
        self.message_user(request, f"Забанено {total_banned} пользователей в каналах.")
    ban_from_all_channels.short_description = "🚫 Забанить во всех каналах"

    def unban_from_all_channels(self, request, queryset):
        """
        Разбанивает админов во всех их каналах.
        """
        service = TelegramAdminService()
        total_unbanned = 0
        
        for admin in queryset:
            channel_ids = [group.group_id for group in admin.groups.all()]
            for chat_id in channel_ids:
                success, message = run_async_function(
                    service.unban_user_from_channel,
                    chat_id,
                    admin.telegram_id
                )
                if success:
                    total_unbanned += 1
                    self.message_user(request, message, level='SUCCESS')
                else:
                    self.message_user(request, message, level='ERROR')
        
        service.close()
        self.message_user(request, f"Разбанено {total_unbanned} пользователей в каналах.")
    unban_from_all_channels.short_description = "✅ Разбанить во всех каналах"

    def check_bot_permissions(self, request, queryset):
        """
        Проверяет права бота в каналах админов.
        """
        service = TelegramAdminService()
        checked_channels = set()
        
        for admin in queryset:
            for group in admin.groups.all():
                if group.group_id not in checked_channels:
                    try:
                        has_permissions, message = run_async_function(
                            service.check_bot_permissions,
                            group.group_id
                        )
                        if has_permissions:
                            self.message_user(request, f"✅ {group.group_name}: {message}", level='SUCCESS')
                        else:
                            self.message_user(request, f"❌ {group.group_name}: {message}", level='ERROR')
                        checked_channels.add(group.group_id)
                    except Exception as e:
                        self.message_user(request, f"❌ {group.group_name}: Ошибка проверки прав: {e}", level='ERROR')
        
        service.close()
        self.message_user(request, f"Проверено {len(checked_channels)} каналов.")
    check_bot_permissions.short_description = "🔍 Проверить права бота в каналах"


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


class CustomUserAdmin(UserOverviewMixin, UserAdmin):
    """
    Админ-панель для CustomUser с интеграцией социальных аккаунтов и действием для создания DjangoAdmin.
    """
    model = CustomUser
    list_display = [
        'username', 'email', 'is_active', 'is_staff', 'telegram_id', 
        'subscription_status', 'social_accounts_display', 'created_at'
    ]
    search_fields = ['username', 'email', 'telegram_id']
    list_filter = [
        'is_active', 'is_staff', 'subscription_status', 'language',
        'social_accounts__provider', 'social_accounts__is_active'
    ]
    inlines = [SocialAccountInline]
    
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
    actions = ['make_django_admin', 'link_social_accounts', 'show_user_overview', 'show_user_details']
    
    def social_accounts_display(self, obj):
        """
        Отображает социальные аккаунты пользователя.
        """
        accounts = obj.social_accounts.filter(is_active=True)
        if not accounts:
            return '-'
        
        providers = [account.provider for account in accounts]
        if len(providers) > 2:
            return f"{', '.join(providers[:2])} +{len(providers)-2}"
        return ', '.join(providers)
    social_accounts_display.short_description = 'Социальные аккаунты'
    
    def link_social_accounts(self, request, queryset):
        """
        Связывает социальные аккаунты пользователей с существующими системами.
        """
        linked_count = 0
        for user in queryset:
            for social_account in user.social_accounts.filter(is_active=True):
                try:
                    linked_count += social_account.auto_link_existing_users()
                except Exception as e:
                    self.message_user(
                        request, 
                        f"Ошибка при связывании аккаунта {social_account.provider_user_id}: {e}", 
                        level='ERROR'
                    )
        
        self.message_user(request, f"Связано {linked_count} социальных аккаунтов.")
    link_social_accounts.short_description = "Связать социальные аккаунты"

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
    actions = ['remove_user_from_all_channels', 'sync_with_telegram']
    
    def delete_queryset(self, request, queryset):
        """
        Переопределяем стандартное удаление, чтобы использовать нашу логику.
        """
        print(f"=== DEBUG: delete_queryset вызван для {queryset.count()} TelegramUser объектов ===", file=sys.stderr)
        self.remove_user_from_all_channels(request, queryset)
        # После удаления из Telegram, удаляем из базы данных
        super().delete_queryset(request, queryset)
    
    def delete_model(self, request, obj):
        """
        Переопределяем удаление одного объекта.
        """
        print(f"=== DEBUG: delete_model вызван для TelegramUser объекта {obj.id} ===", file=sys.stderr)
        self.remove_user_from_all_channels(request, [obj])
        # После удаления из Telegram, удаляем из базы данных
        super().delete_model(request, obj)

    def sync_with_telegram(self, request, queryset):
        """
        Синхронизирует данные пользователей с Telegram.
        """
        from accounts.telegram_admin_service import TelegramAdminService, run_async_function
        service = TelegramAdminService()
        synced_count = 0
        
        try:
            for user in queryset:
                try:
                    # Получаем актуальные данные пользователя из Telegram
                    user_info = run_async_function(
                        service.bot.get_chat,
                        user.telegram_id
                    )
                    
                    # Обновляем данные пользователя
                    user.username = user_info.username
                    user.first_name = user_info.first_name
                    user.last_name = user_info.last_name
                    user.is_premium = getattr(user_info, 'is_premium', False)
                    user.save()
                    
                    synced_count += 1
                    self.message_user(
                        request, 
                        f"✅ Синхронизирован пользователь {user.username or user.telegram_id}", 
                        level='SUCCESS'
                    )
                except Exception as e:
                    self.message_user(
                        request, 
                        f"❌ Ошибка синхронизации пользователя {user.telegram_id}: {e}", 
                        level='ERROR'
                    )
        finally:
            service.close()
        
        self.message_user(
            request, 
            f"Синхронизировано {synced_count} пользователей из {queryset.count()}"
        )
    sync_with_telegram.short_description = "🔄 Синхронизировать с Telegram"

    def remove_user_from_all_channels(self, request, queryset):
        """
        Полностью удаляет пользователей из всех их каналов (кикает).
        """
        from accounts.telegram_admin_service import TelegramAdminService, run_async_function
        total_removed = 0

        for user in queryset:
            # Получаем все каналы, где пользователь состоит
            channel_ids = [sub.channel.group_id for sub in user.channel_subscriptions.all()]
            if channel_ids:
                service = TelegramAdminService()
                try:
                    success_count, messages = run_async_function(
                        service.remove_user_from_all_channels,
                        user.telegram_id,
                        channel_ids
                    )
                    total_removed += success_count
                    for message in messages:
                        if "успешно" in message:
                            self.message_user(request, message, level='SUCCESS')
                        else:
                            self.message_user(request, message, level='ERROR')
                finally:
                    service.close()
        
        # Удаляем только связи из базы данных (самого пользователя удалит delete_queryset)
        for user in queryset:
            user.channel_subscriptions.all().delete()
        
        self.message_user(
            request,
            f"Удалено {total_removed} пользователей из каналов. Связи в базе данных очищены."
        )
    remove_user_from_all_channels.short_description = "🚫 Удалить из всех каналов (кик)"


class UserChannelSubscriptionAdmin(admin.ModelAdmin):
    """
    Админ-панель для подписок пользователей на каналы.
    """
    list_display = [
        'telegram_user', 'channel', 'subscription_status', 
        'subscribed_at', 'banned_status', 'user_admin_status', 'channel_admin_status'
    ]
    search_fields = [
        'telegram_user__username', 'telegram_user__first_name', 'telegram_user__last_name',
        'channel__group_name', 'channel__group_id'
    ]
    list_filter = [
        'subscription_status', 'subscribed_at', 'unsubscribed_at',
        'telegram_user__is_premium'
    ]
    raw_id_fields = ['telegram_user', 'channel']
    readonly_fields = [
        'subscribed_at', 'unsubscribed_at', 'banned_at', 'banned_until',
        'user_admin_status', 'channel_admin_status', 'user_links', 'banned_status'
    ]
    actions = ['remove_from_channel', 'ban_from_channel', 'unban_from_channel', 'sync_from_bot', 'promote_to_admin']
    
    def delete_queryset(self, request, queryset):
        """
        Переопределяем стандартное удаление, чтобы использовать нашу логику.
        """
        print(f"=== DEBUG: delete_queryset вызван для {queryset.count()} объектов ===", file=sys.stderr)
        self.remove_from_channel(request, queryset)
    
    def delete_model(self, request, obj):
        """
        Переопределяем удаление одного объекта.
        """
        print(f"=== DEBUG: delete_model вызван для объекта {obj.id} ===", file=sys.stderr)
        self.remove_from_channel(request, [obj])
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('telegram_user', 'channel', 'subscription_status')
        }),
        ('Даты', {
            'fields': ('subscribed_at', 'unsubscribed_at'),
            'classes': ('collapse',)
        }),
        ('Дополнительная информация', {
            'fields': ('user_admin_status', 'channel_admin_status', 'user_links'),
            'classes': ('collapse',)
        }),
    )

    def user_admin_status(self, obj):
        """
        Отображает статус админа пользователя.
        """
        if obj.telegram_user:
            # Проверяем, является ли пользователь админом этого канала
            from accounts.models import TelegramAdmin
            admin = TelegramAdmin.objects.filter(
                telegram_id=obj.telegram_user.telegram_id,
                groups__group_id=obj.channel.group_id
            ).first()
            if admin:
                return "✅ Админ канала"
            
            # Проверяем, является ли пользователь Django админом
            from accounts.models import DjangoAdmin
            django_admin = DjangoAdmin.objects.filter(
                username=obj.telegram_user.username
            ).first()
            if django_admin:
                return "✅ Django админ"
        
        return "❌ Не админ"
    user_admin_status.short_description = 'Статус админа'

    def channel_admin_status(self, obj):
        """
        Отображает информацию о канале и его админах.
        """
        if obj.channel:
            # Подсчитываем количество админов канала
            from accounts.models import TelegramAdmin
            admin_count = TelegramAdmin.objects.filter(
                groups__group_id=obj.channel.group_id
            ).count()
            return f"👥 {admin_count} админов"
        return "-"
    channel_admin_status.short_description = 'Админы канала'

    def user_links(self, obj):
        """
        Отображает ссылки на связанные записи пользователя.
        """
        links = []
        
        if obj.telegram_user:
            # Ссылка на TelegramUser
            from django.urls import reverse
            url = reverse('admin:accounts_telegramuser_change', args=[obj.telegram_user.id])
            links.append(f'<a href="{url}">Telegram User</a>')
            
            # Ссылка на TelegramAdmin если есть
            from accounts.models import TelegramAdmin
            admin = TelegramAdmin.objects.filter(
                telegram_id=obj.telegram_user.telegram_id
            ).first()
            if admin:
                url = reverse('admin:accounts_telegramadmin_change', args=[admin.id])
                links.append(f'<a href="{url}">Telegram Admin</a>')
            
            # Ссылка на DjangoAdmin если есть
            from accounts.models import DjangoAdmin
            django_admin = DjangoAdmin.objects.filter(
                username=obj.telegram_user.username
            ).first()
            if django_admin:
                url = reverse('admin:accounts_djangoadmin_change', args=[django_admin.id])
                links.append(f'<a href="{url}">Django Admin</a>')
        
        if not links:
            return '-'
        
        from django.utils.safestring import mark_safe
        return mark_safe(' | '.join(links))
    user_links.short_description = 'Ссылки на пользователя'

    def banned_status(self, obj):
        """
        Показывает статус блокировки пользователя.
        """
        from django.utils.safestring import mark_safe
        from django.utils import timezone
        
        if obj.subscription_status == 'banned':
            if obj.banned_until:
                now = timezone.now()
                if obj.banned_until > now:
                    # Еще заблокирован
                    remaining = obj.banned_until - now
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    return mark_safe(f'<span style="color: red;">🚫 Заблокирован ({hours}ч {minutes}м)</span>')
                else:
                    # Время блокировки истекло
                    return mark_safe('<span style="color: orange;">⚠️ Блокировка истекла</span>')
            else:
                return mark_safe('<span style="color: red;">🚫 Заблокирован</span>')
        else:
            return mark_safe('<span style="color: green;">✅ Активен</span>')
    banned_status.short_description = 'Статус блокировки'

    def remove_from_channel(self, request, queryset):
        """
        Удаляет пользователей из каналов (кикает).
        """
        from accounts.telegram_admin_service import TelegramAdminService, run_async_function
        import logging
        import sys
        import asyncio
        
        # Настраиваем логирование для отладки
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        
        # Выводим в консоль для отладки
        print(f"=== DEBUG: Начинаем массовое удаление {queryset.count()} подписок ===", file=sys.stderr)
        logger.info(f"Начинаем массовое удаление {queryset.count()} подписок")
        
        removed_count = 0
        
        try:
            for subscription in queryset:
                try:
                    print(f"=== DEBUG: Обрабатываем подписку {subscription.id} ===", file=sys.stderr)
                    logger.info(f"Обрабатываем подписку {subscription.id}: пользователь {subscription.telegram_user.telegram_id} в канале {subscription.channel.group_id}")
                    
                    # Проверяем, что у нас есть все необходимые данные
                    if not subscription.channel or not subscription.telegram_user:
                        error_msg = f"❌ Отсутствуют данные для подписки {subscription.id}"
                        print(f"=== DEBUG: {error_msg} ===", file=sys.stderr)
                        logger.error(error_msg)
                        self.message_user(request, error_msg, level='ERROR')
                        continue
                    
                    # Создаем новый сервис для каждой операции
                    service = TelegramAdminService()
                    try:
                        # Удаляем пользователя из канала
                        print(f"=== DEBUG: Вызываем remove_user_from_channel для пользователя {subscription.telegram_user.telegram_id} в канале {subscription.channel.group_id} ===", file=sys.stderr)
                        logger.info(f"Вызываем remove_user_from_channel для пользователя {subscription.telegram_user.telegram_id} в канале {subscription.channel.group_id}")
                        success, message = run_async_function(
                            service.remove_user_from_channel,
                            subscription.channel.group_id,
                            subscription.telegram_user.telegram_id
                        )
                        
                        print(f"=== DEBUG: Результат удаления: success={success}, message={message} ===", file=sys.stderr)
                        logger.info(f"Результат удаления: success={success}, message={message}")
                        
                        if success:
                            removed_count += 1
                            subscription.delete()  # Удаляем подписку из базы данных
                            print(f"=== DEBUG: Подписка {subscription.id} удалена из базы данных ===", file=sys.stderr)
                            logger.info(f"Подписка {subscription.id} удалена из базы данных")
                            self.message_user(
                                request, 
                                f"✅ {message}", 
                                level='SUCCESS'
                            )
                        else:
                            print(f"=== DEBUG: Не удалось удалить пользователя: {message} ===", file=sys.stderr)
                            logger.error(f"Не удалось удалить пользователя: {message}")
                            self.message_user(
                                request, 
                                f"❌ {message}", 
                                level='ERROR'
                            )
                    finally:
                        service.close()
                        
                except Exception as e:
                    error_msg = f"❌ Ошибка удаления пользователя {subscription.telegram_user.telegram_id} из канала {subscription.channel.group_id}: {e}"
                    print(f"=== DEBUG: {error_msg} ===", file=sys.stderr)
                    logger.error(error_msg, exc_info=True)
                    self.message_user(request, error_msg, level='ERROR')
        except Exception as e:
            print(f"=== DEBUG: Общая ошибка: {e} ===", file=sys.stderr)
            logger.error(f"Общая ошибка: {e}", exc_info=True)
        
        print(f"=== DEBUG: Завершено массовое удаление. Удалено {removed_count} из {queryset.count()} ===", file=sys.stderr)
        logger.info(f"Завершено массовое удаление. Удалено {removed_count} из {queryset.count()}")
        
        self.message_user(
            request, 
            f"Удалено {removed_count} пользователей из каналов из {queryset.count()}"
        )
    remove_from_channel.short_description = "🚫 Удалить из канала"

    def sync_from_bot(self, request, queryset):
        """
        Синхронизирует подписки из SQLAlchemy базы данных бота.
        """
        # Здесь можно добавить логику синхронизации
        self.message_user(request, "Функция синхронизации будет реализована позже.")
    sync_from_bot.short_description = "Синхронизировать из бота"

    def ban_from_channel(self, request, queryset):
        """
        Отмечает подписчиков как заблокированных в базе данных.
        """
        from django.utils import timezone
        from datetime import datetime, timedelta
        
        service = TelegramAdminService()
        total_banned = 0
        
        for subscription in queryset:
            if subscription.channel and subscription.telegram_user:
                success, message = run_async_function(
                    service.ban_user_from_channel,
                    subscription.channel.group_id,
                    subscription.telegram_user.telegram_id
                )
                if success:
                    # Обновляем статус в базе данных
                    subscription.subscription_status = 'banned'
                    subscription.banned_at = timezone.now()
                    subscription.banned_until = timezone.now() + timedelta(hours=24)
                    subscription.save()
                    
                    total_banned += 1
                    self.message_user(request, message, level='SUCCESS')
                else:
                    self.message_user(request, message, level='ERROR')
        
        service.close()
        self.message_user(request, f"Заблокировано {total_banned} подписчиков в каналах.")
    ban_from_channel.short_description = "🚫 Заблокировать в системе (24 часа)"

    def unban_from_channel(self, request, queryset):
        """
        Отмечает подписчиков как разблокированных в базе данных.
        """
        service = TelegramAdminService()
        total_unbanned = 0
        
        for subscription in queryset:
            if subscription.channel and subscription.telegram_user:
                success, message = run_async_function(
                    service.unban_user_from_channel,
                    subscription.channel.group_id,
                    subscription.telegram_user.telegram_id
                )
                if success:
                    # Обновляем статус в базе данных
                    subscription.subscription_status = 'active'
                    subscription.banned_at = None
                    subscription.banned_until = None
                    subscription.save()
                    
                    total_unbanned += 1
                    self.message_user(request, message, level='SUCCESS')
                else:
                    self.message_user(request, message, level='ERROR')
        
        service.close()
        self.message_user(request, f"Разблокировано {total_unbanned} подписчиков в каналах.")
    unban_from_channel.short_description = "✅ Разблокировать в системе"

    def promote_to_admin(self, request, queryset):
        """
        Назначает пользователей администраторами в их каналах.
        """
        from accounts.telegram_admin_service import TelegramAdminService, run_async_function
        from accounts.models import TelegramAdmin, TelegramAdminGroup
        from platforms.models import TelegramGroup
        import logging
        logger = logging.getLogger(__name__)
        
        total_promoted = 0
        
        for subscription in queryset:
            user = subscription.telegram_user
            channel = subscription.channel
            
            # Проверяем, не является ли пользователь уже админом этого канала
            existing_admin = TelegramAdmin.objects.filter(
                telegram_id=user.telegram_id,
                groups__group_id=channel.group_id
            ).first()
            
            if existing_admin:
                self.message_user(
                    request, 
                    f"⚠️ Пользователь {user.username or user.telegram_id} уже является админом канала {channel.group_name}", 
                    level='WARNING'
                )
                continue
            
            service = TelegramAdminService()
            try:
                # Назначаем админом в Telegram
                success, message = run_async_function(
                    service.promote_user_to_admin,
                    channel.group_id,
                    user.telegram_id
                )
                
                if success:
                    # Создаем или получаем запись TelegramAdmin
                    admin, created = TelegramAdmin.objects.get_or_create(
                        telegram_id=user.telegram_id,
                        defaults={
                            'username': user.username,
                            'language': user.language,
                            'is_active': True
                        }
                    )
                    
                    # Если запись уже существовала, обновляем данные
                    if not created:
                        admin.username = user.username
                        admin.language = user.language
                        admin.save()
                    
                    # Связываем админа с каналом
                    admin_group, created = TelegramAdminGroup.objects.get_or_create(
                        telegram_admin=admin,
                        telegram_group=channel
                    )
                    
                    # Отправляем сообщение пользователю
                    channel_name = channel.group_name or f"канал {channel.group_id}"
                    
                    # Формируем ссылку на канал
                    if channel.username:
                        channel_link = f"https://t.me/{channel.username}"
                        channel_display = f"<a href='{channel_link}'>{channel_name}</a>"
                    else:
                        # Если нет username, используем просто название
                        channel_display = f"<b>{channel_name}</b>"
                    
                    notification_message = f"""
🎉 <b>Поздравляем!</b>

Вас назначили администратором в канале {channel_display}

Теперь у вас есть права на:
• Управление сообщениями
• Удаление сообщений
• Приглашение пользователей
• Ограничение участников
• Закрепление сообщений

Спасибо за вашу помощь в модерации! 🙏
                    """.strip()
                    
                    # Создаем новый сервис для отправки сообщения
                    message_service = TelegramAdminService()
                    try:
                        message_sent, message_result = run_async_function(
                            message_service.send_message_to_user,
                            user.telegram_id,
                            notification_message
                        )
                        
                        if message_sent:
                            logger.info(f"Уведомление отправлено пользователю {user.telegram_id}")
                        else:
                            logger.warning(f"Не удалось отправить уведомление пользователю {user.telegram_id}: {message_result}")
                    finally:
                        message_service.close()
                    
                    total_promoted += 1
                    
                    self.message_user(
                        request, 
                        f"✅ {message}", 
                        level='SUCCESS'
                    )
                else:
                    self.message_user(
                        request, 
                        f"❌ {message}", 
                        level='ERROR'
                    )
                    
            finally:
                service.close()
        
        self.message_user(
            request, 
            f"Назначено {total_promoted} администраторов из {queryset.count()} подписок"
        )
    promote_to_admin.short_description = "👑 Назначить админом"


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