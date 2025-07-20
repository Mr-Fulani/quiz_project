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
    actions = ['make_premium', 'remove_premium', 'remove_user_from_all_channels']

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
        
        # Удаляем связи из базы данных и самого пользователя
        for user in queryset:
            user.channel_subscriptions.all().delete()
            user.delete()  # Полностью удаляем пользователя из базы данных
        
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
        'subscribed_at', 'user_admin_status', 'channel_admin_status'
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
        'subscribed_at', 'unsubscribed_at', 'user_admin_status', 
        'channel_admin_status', 'user_links'
    ]
    actions = ['subscribe', 'unsubscribe', 'sync_from_bot', 'ban_from_channel', 'unban_from_channel']
    
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

    def subscribe(self, request, queryset):
        """
        Активирует выбранные подписки.
        """
        for subscription in queryset:
            subscription.subscribe()
        self.message_user(request, f'{queryset.count()} подписок активировано.')
    subscribe.short_description = "Активировать подписку"

    def unsubscribe(self, request, queryset):
        """
        Деактивирует выбранные подписки.
        """
        for subscription in queryset:
            subscription.unsubscribe()
        self.message_user(request, f'{queryset.count()} подписок деактивировано.')
    unsubscribe.short_description = "Деактивировать подписку"

    def sync_from_bot(self, request, queryset):
        """
        Синхронизирует подписки из SQLAlchemy базы данных бота.
        """
        # Здесь можно добавить логику синхронизации
        self.message_user(request, "Функция синхронизации будет реализована позже.")
    sync_from_bot.short_description = "Синхронизировать из бота"

    def ban_from_channel(self, request, queryset):
        """
        Банит подписчиков в их каналах.
        """
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
                    total_banned += 1
                    self.message_user(request, message, level='SUCCESS')
                else:
                    self.message_user(request, message, level='ERROR')
        
        service.close()
        self.message_user(request, f"Забанено {total_banned} подписчиков в каналах.")
    ban_from_channel.short_description = "🚫 Забанить в каналах"

    def unban_from_channel(self, request, queryset):
        """
        Разбанивает подписчиков в их каналах.
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
                    total_unbanned += 1
                    self.message_user(request, message, level='SUCCESS')
                else:
                    self.message_user(request, message, level='ERROR')
        
        service.close()
        self.message_user(request, f"Разбанено {total_unbanned} подписчиков в каналах.")
    unban_from_channel.short_description = "✅ Разбанить в каналах"


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