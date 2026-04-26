# accounts/models.py
import logging
import os
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.db.models import Q, Count
from django.utils import timezone
from django.db.models.signals import post_delete
from django.dispatch import receiver
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit

logger = logging.getLogger(__name__)


class CustomUser(AbstractUser):
    """
    Кастомная модель пользователя с объединёнными полями из Profile.
    Пользователи изолированы по тенанту.
    Superuser имеет tenant=None и видит все данные.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='web_users',
        verbose_name="Тенант",
        help_text="Тенант пользователя. None = superuser (видит все)."
    )
    subscription_status = models.CharField(max_length=20, default='inactive', verbose_name="Статус подписки")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    language = models.CharField(max_length=10, blank=True, null=True, verbose_name="Язык")
    deactivated_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата деактивации")
    telegram_id = models.BigIntegerField(blank=True, null=True, verbose_name="Telegram ID")

    # Поля из Profile
    avatar = models.ImageField(upload_to='avatar/', blank=True, null=True, verbose_name="Аватар")
    # Thumbnail версия аватара для оптимизации загрузки (60x60px для testimonials)
    avatar_thumbnail = ImageSpecField(
        source='avatar',
        processors=[ResizeToFit(120, 120)],  # 120px для retina, отображается как 60px
        format='JPEG',
        options={'quality': 85}
    )
    bio = models.TextField(max_length=500, blank=True, verbose_name="Биография")
    location = models.CharField(max_length=100, blank=True, verbose_name="Местоположение")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    website = models.URLField(max_length=200, blank=True, verbose_name="Веб-сайт")
    telegram = models.CharField(max_length=100, blank=True, verbose_name="Telegram")
    github = models.URLField(blank=True, verbose_name="GitHub")
    instagram = models.URLField(blank=True, verbose_name="Instagram")
    facebook = models.URLField(blank=True, verbose_name="Facebook")
    linkedin = models.URLField(blank=True, verbose_name="LinkedIn")
    youtube = models.URLField(blank=True, verbose_name="YouTube")
    total_points = models.IntegerField(default=0, verbose_name="Всего баллов")
    quizzes_completed = models.IntegerField(default=0, verbose_name="Завершено квизов")
    average_score = models.FloatField(default=0.0, verbose_name="Средний балл")
    favorite_category = models.CharField(max_length=100, blank=True, verbose_name="Любимая категория")
    is_telegram_user = models.BooleanField(default=False, verbose_name="Пользователь Telegram")
    email_notifications = models.BooleanField(default=True, verbose_name="Уведомления по email")
    is_public = models.BooleanField(default=True, verbose_name="Публичный профиль")
    theme_preference = models.CharField(
        max_length=20,
        choices=[('light', 'Light'), ('dark', 'Dark')],
        default='dark',
        verbose_name="Тема интерфейса"
    )
    last_seen = models.DateTimeField(default=timezone.now, verbose_name="Последний визит")

    groups = models.ManyToManyField(
        Group,
        blank=True,
        help_text="Группы, к которым принадлежит пользователь.",
        verbose_name="Группы"
    )
    user_permissions = models.ManyToManyField(
        Permission,
        blank=True,
        help_text="Индивидуальные разрешения пользователя.",
        verbose_name="Разрешения"
    )

    class Meta:
        db_table = 'users'
        verbose_name = 'Пользователь Сайта'
        verbose_name_plural = 'Пользователи Сайта'

    def __str__(self):
        """Строковое представление пользователя."""
        return f"{self.username or 'User'}"

    def get_unread_messages_count(self):
        """Возвращает количество непрочитанных сообщений."""
        return self.received_messages.filter(is_read=False).count()

    def get_statistics(self):
        """Получение статистики пользователя."""
        from tasks.models import TaskStatistics
        # Считаем уникальные translation_group_id вместо количества записей
        # чтобы не учитывать дубликаты от синхронизации статистики между языками
        total_attempts = TaskStatistics.objects.filter(user=self).values('task__translation_group_id').distinct().count()
        solved_tasks = TaskStatistics.objects.filter(user=self, successful=True).values('task__translation_group_id').distinct().count()
        
        return {
            'solved_tasks': solved_tasks,
            'rating': self.calculate_rating(),  # Теперь возвращаем как есть
            'total_attempts': total_attempts
        }

    @property
    def statistics(self):
        """Свойство для доступа к статистике."""
        return self.get_statistics()

    def invalidate_statistics_cache(self):
        """Очищает кэш статистики пользователя."""
        from django.core.cache import cache
        cache_key = f'user_stats_{self.id}'
        cache.delete(cache_key)
        logger.info(f"=== DEBUG: Statistics cache invalidated for user {self.username}")

    @staticmethod
    def get_rating_annotation():
        """Возвращает аннотацию для подсчета рейтинга пользователя.
        Используется как в топ-пользователях, так и в индивидуальной статистике."""
        from django.db.models import Sum, Case, When, Value, IntegerField
        
        return Sum(
            Case(
                When(statistics__successful=True, then=Case(
                    When(statistics__task__difficulty='easy', then=Value(10)),
                    When(statistics__task__difficulty='medium', then=Value(25)),
                    When(statistics__task__difficulty='hard', then=Value(50)),
                    default=Value(10),
                    output_field=IntegerField(),
                )),
                default=0,
                output_field=IntegerField(),
            )
        )

    def calculate_rating(self):
        """Расчёт рейтинга на основе сложности решённых задач. 
        Использует ту же логику, что и для топ-пользователей."""
        rating_data = self.__class__.objects.filter(id=self.id).annotate(
            total_score=self.get_rating_annotation()
        ).first()
        
        # Возвращаем базовый рейтинг (без умножения на 100)
        return (rating_data.total_score or 0) if rating_data else 0

    @property
    def get_avatar_url(self):
        """Возвращает URL аватара или дефолтное изображение."""
        if self.avatar:
            return self.avatar.url
        return '/static/blog/images/avatar/default_avatar.png'
    
    def get_display_name(self):
        """
        Возвращает отображаемое имя пользователя.
        Приоритет: first_name + last_name -> first_name -> email до @ -> username
        
        Returns:
            str: Отображаемое имя пользователя
        """
        # Сначала пробуем first_name + last_name
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        
        # Потом только first_name
        if self.first_name:
            return self.first_name
        
        # Если нет first_name, берем часть email до @
        if self.email and '@' in self.email:
            email_username = self.email.split('@')[0]
            # Ограничиваем длину и убираем спецсимволы для безопасности
            email_username = ''.join(c for c in email_username if c.isalnum() or c in '._-')[:30]
            if email_username:
                return email_username
        
        # В крайнем случае используем username
        return self.username or 'User'
    
    @property
    def get_avatar_thumbnail_url(self):
        """Возвращает URL thumbnail версии аватара (120x120px) для оптимизации загрузки."""
        if self.avatar and hasattr(self, 'avatar_thumbnail'):
            try:
                return self.avatar_thumbnail.url
            except:
                # Если thumbnail еще не сгенерирован, используем оригинал
                return self.avatar.url
        return '/static/blog/images/avatar/default_avatar.png'
    
    @property
    def get_telegram_url(self):
        """
        Возвращает корректный URL для Telegram профиля.
        Нормализует значение поля telegram, преобразуя @username или username в полный URL.
        
        Returns:
            str: URL в формате https://t.me/username или пустая строка
        """
        if not self.telegram:
            return ''
        
        telegram_value = self.telegram.strip()
        
        # Если уже полный URL - возвращаем как есть
        if telegram_value.startswith('http://') or telegram_value.startswith('https://'):
            return telegram_value
        
        # Если начинается с @ - убираем @ и формируем URL
        if telegram_value.startswith('@'):
            username = telegram_value[1:].strip()
            if username:
                return f'https://t.me/{username}'
        
        # Если просто username без @ - формируем URL
        if telegram_value and not telegram_value.startswith('/'):
            # Проверяем, что это не относительный путь
            return f'https://t.me/{telegram_value}'
        
        # Если не можем определить - возвращаем пустую строку
        return ''
    
    @property
    def get_telegram_username(self):
        """
        Возвращает username из поля telegram (без @ и URL префиксов).
        Используется для формирования ссылок типа tg://resolve?domain=username.
        
        Returns:
            str: Username без @ и префиксов или пустая строка
        """
        if not self.telegram:
            return ''
        
        telegram_value = self.telegram.strip()
        
        # Убираем префиксы URL
        for prefix in ['https://t.me/', 'http://t.me/', 'https://telegram.me/', 'http://telegram.me/']:
            if telegram_value.startswith(prefix):
                return telegram_value[len(prefix):].strip()
        
        # Убираем @ если есть
        if telegram_value.startswith('@'):
            return telegram_value[1:].strip()
        
        # Если уже username без префиксов
        return telegram_value

    @property
    def is_online(self):
        """Проверяет, онлайн ли пользователь (последний визит в течение 5 минут)."""
        if not self.last_seen:
            return False
        return timezone.now() - self.last_seen < timedelta(minutes=5)

    @property
    def member_since(self):
        """Возвращает дату регистрации пользователя."""
        return self.date_joined.strftime('%B %Y')

    @property
    def is_admin(self):
        """
        Проверяет, является ли пользователь администратором в любой из систем.
        
        Returns:
            bool: True если пользователь является админом
        """
        return self.is_staff or self.is_superuser

    @property
    def admin_type(self):
        """
        Возвращает тип администратора пользователя.
        
        Returns:
            str: Тип админа или None
        """
        from django.utils.translation import gettext as _
        if self.is_superuser:
            return _("Super Admin")
        elif self.is_staff:
            return _("Django Admin")
        else:
            return None

    @property
    def admin_badge_icon(self):
        """
        Возвращает иконку для бейджа администратора.
        
        Returns:
            str: Название иконки или None
        """
        if self.is_superuser:
            return "shield-checkmark"  # Иконка для суперпользователя
        elif self.is_staff:
            return "shield"  # Иконка для обычного администратора
        return None

    @property
    def admin_badge_color(self):
        """
        Возвращает цвет для бейджа администратора.
        
        Returns:
            str: CSS класс цвета или None
        """
        if self.is_superuser:
            return "admin-badge-superuser"  # Золотой цвет для суперпользователя
        elif self.is_staff:
            return "admin-badge-staff"  # Синий цвет для администратора
        return None

    @property
    def favorite_topics(self):
        """Возвращает топ-3 любимых темы пользователя."""
        from tasks.models import TaskStatistics
        return TaskStatistics.objects.filter(user=self) \
                   .values('task__topic__name') \
                   .annotate(count=Count('id')) \
                   .order_by('-count')[:3]

    def get_progress_data(self):
        """
        Возвращает данные о прогрессе по темам.
        Временная заглушка, чтобы фронтенд не падал.
        """
        # TODO: Реализовать реальную логику выборки прогресса
        return []




class TelegramUser(models.Model):
    """
    Модель пользователя Telegram-бота.
    Хранит данные о пользователях Telegram, включая подписчиков, и их связь с CustomUser.
    Изолированы по тенанту: один человек может быть TelegramUser в нескольких тенантах.
    """
    STATUS_CHOICES = [
        ('active', 'Активна'),
        ('inactive', 'Неактивна'),
    ]

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='telegram_users',
        null=True,
        blank=True,
        verbose_name="Тенант",
        help_text="Тенант, к которому привязан этот Telegram-пользователь"
    )
    telegram_id = models.BigIntegerField(db_index=True, verbose_name="Telegram ID")
    username = models.CharField(max_length=255, blank=True, null=True, verbose_name="@username")
    first_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Имя")
    last_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Фамилия")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    subscription_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='inactive',
        verbose_name="Статус подписки"
    )  # Добавлено: синхронизация с SQLAlchemy
    language = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Язык"
    )  # Добавлено: синхронизация с SQLAlchemy
    deactivated_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Дата деактивации"
    )  # Добавлено: синхронизация с SQLAlchemy
    is_premium = models.BooleanField(default=False, verbose_name="Премиум аккаунт")
    linked_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Связанный пользователь сайта.",
        verbose_name="Связанный пользователь"
    )

    class Meta:
        db_table = 'telegram_users'
        verbose_name = 'Telegram Пользователь'
        verbose_name_plural = 'Telegram Пользователи'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'telegram_id'],
                name='unique_telegram_user_per_tenant'
            )
        ]

    def __str__(self):
        """
        Строковое представление объекта TelegramUser.
        """
        return self.username or f"TelegramUser {self.telegram_id}"









class TelegramAdmin(models.Model):
    """
    Модель администратора Telegram-бота и Mini App.
    Хранит данные для управления Telegram-группами.
    Каждый TelegramAdmin принадлежит одному тенанту.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='telegram_admins',
        null=True,
        blank=True,
        verbose_name="Тенант",
        help_text="Тенант, к которому привязан этот Telegram-админ"
    )
    telegram_id = models.BigIntegerField(
        null=False, db_index=True, verbose_name="Telegram ID"
    )
    username = models.CharField(
        max_length=255, null=True, blank=True, verbose_name="Username"
    )
    language = models.CharField(
        max_length=10, default='ru', null=True, verbose_name="Язык"
    )
    is_active = models.BooleanField(
        default=True, verbose_name="Активен"
    )
    photo = models.CharField(
        max_length=500, null=True, blank=True, verbose_name="Фото"
    )
    groups = models.ManyToManyField(
        'platforms.TelegramGroup',
        related_name='telegram_admins',
        blank=True,
        verbose_name='Telegram Группа/Канал',
        through='TelegramAdminGroup',
    )

    class Meta:
        db_table = 'telegram_admins'
        verbose_name = 'Telegram Администратор'
        verbose_name_plural = 'Telegram Администраторы'

    def __str__(self):
        """Строковое представление."""
        return f"{self.username or 'Admin'} (Telegram ID: {self.telegram_id})"

    @property
    def photo_url(self):
        """Возвращает URL фото или дефолтное изображение."""
        return self.photo or "/static/images/default_avatar.png"



class TelegramAdminGroup(models.Model):
    """
    Промежуточная модель для связи TelegramAdmin и TelegramGroup.
    """
    telegram_admin = models.ForeignKey(
        'TelegramAdmin',
        on_delete=models.CASCADE,
        related_name='admin_groups'
    )
    telegram_group = models.ForeignKey(
        'platforms.TelegramGroup',
        to_field='group_id',
        on_delete=models.CASCADE,
        related_name='group_admins'
    )

    class Meta:
        db_table = 'telegramadmin_groups'
        unique_together = ('telegram_admin', 'telegram_group')
        verbose_name = 'Связь Telegram Администратора и Группы'
        verbose_name_plural = 'Связи Telegram Администраторов и Групп'



class DjangoAdmin(AbstractUser):
    """
    Модель администратора Django-админки.
    Хранит данные для управления сайтом через админ-панель.
    """
    phone_number = models.CharField(max_length=15, null=True, blank=True, verbose_name="Номер телефона")
    language = models.CharField(max_length=10, default='en', verbose_name="Язык")
    is_django_admin = models.BooleanField(default=True, verbose_name="Django Admin")

    class Meta:
        db_table = 'django_admins'
        verbose_name = 'Django Администратор'
        verbose_name_plural = 'Django Администраторы'

    def __str__(self):
        """Строковое представление."""
        return f"{self.username or 'DjangoAdmin'}"




class UserChannelSubscription(models.Model):
    """
    Модель подписки пользователя на Telegram-канал.
    Хранит данные о подписках Telegram-пользователей на каналы/группы.
    """
    STATUS_CHOICES = [
        ('active', 'Активна'),
        ('inactive', 'Неактивна'),
        ('banned', 'Заблокирована'),
    ]

    id = models.AutoField(primary_key=True)
    telegram_user = models.ForeignKey(
        'accounts.TelegramUser',
        on_delete=models.CASCADE,
        related_name='channel_subscriptions',
        verbose_name="Telegram пользователь",
        null=False,  # Делаем обязательным, так как это основа
    )
    channel = models.ForeignKey(
        'platforms.TelegramGroup',
        to_field='group_id',
        db_column='channel_id',
        on_delete=models.CASCADE,
        related_name='channel_subscriptions',
        verbose_name="Группа/Канал"
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='inactive',
        verbose_name="Статус подписки"
    )
    subscribed_at = models.DateTimeField(
        null=True,
        verbose_name="Дата подписки"
    )
    unsubscribed_at = models.DateTimeField(
        null=True,
        verbose_name="Дата отписки"
    )
    banned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата блокировки"
    )
    banned_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата разблокировки"
    )

    class Meta:
        db_table = 'user_channel_subscriptions'
        verbose_name = 'Подписка на канал'
        verbose_name_plural = 'Подписки на каналы'
        constraints = [
            models.UniqueConstraint(fields=['telegram_user', 'channel'], name='unique_telegram_user_channel')
        ]
        indexes = [
            models.Index(fields=['subscription_status']),
            models.Index(fields=['subscribed_at']),
        ]

    def __str__(self):
        """Строковое представление подписки."""
        return f"Подписка {self.telegram_user} на {self.channel} ({self.subscription_status})"

    def subscribe(self):
        """Активировать подписку."""
        self.subscription_status = 'active'
        self.subscribed_at = timezone.now()
        self.unsubscribed_at = None
        self.save()
        
        # Уведомляем админов о новой подписке
        try:
            from accounts.utils_folder.telegram_notifications import notify_all_admins, escape_markdown, escape_username_for_markdown, get_base_url, format_markdown_link
            from django.urls import reverse
            
            # Формируем информацию о пользователе
            username = self.telegram_user.username or "Без username"
            telegram_id = self.telegram_user.telegram_id
            user_language = getattr(self.telegram_user, 'language', 'Не указан')

            # Формируем информацию о канале
            channel_info = self.channel.group_name if hasattr(self.channel, 'group_name') else str(self.channel.group_id)

            # Формируем ссылку на подписку в админке с динамическим URL
            # В модели нет доступа к request, используем fallback на настройки
            # Передаем request=None и tenant из канала для корректного URL
            base_url = get_base_url(None, tenant=getattr(self.channel, 'tenant', None))
            admin_path = reverse('admin:accounts_userchannelsubscription_change', args=[self.id])
            admin_url = f"{base_url}{admin_path}"

            # Экранируем значения для Markdown
            # Для username используем специальную функцию, которая НЕ экранирует подчеркивания
            escaped_username = escape_username_for_markdown(username)
            username_display = f"@{escaped_username}" if self.telegram_user.username else escaped_username
            escaped_language = escape_markdown(str(user_language))
            escaped_channel = escape_markdown(str(channel_info))

            admin_title = "👤 Новая подписка"
            admin_message = (
                f"Пользователь: {username_display} (ID: {telegram_id})\n"
                f"Язык: {escaped_language}\n"
                f"Канал: {escaped_channel}\n\n"
                f"👉 {format_markdown_link('Посмотреть в админке', admin_url)}"
            )

            notify_all_admins(
                notification_type='subscription',
                title=admin_title,
                message=admin_message,
                related_object_id=self.id,
                related_object_type='subscription',
                request=None,
                tenant=getattr(self.channel, 'tenant', None)
            )
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Ошибка отправки уведомления о подписке: {e}")

    def unsubscribe(self):
        """Деактивировать подписку."""
        self.subscription_status = 'inactive'
        self.unsubscribed_at = timezone.now()
        self.save()


class MiniAppUser(models.Model):
    """
    Модель пользователя Telegram Mini App.
    Изолирован по тенанту: один человек может быть MiniAppUser в нескольких инстансах мини-аппа.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='mini_app_users',
        null=True,
        blank=True,
        verbose_name="Тенант",
        help_text="Тенант, к которому привязан пользователь Mini App"
    )
    telegram_id = models.BigIntegerField(
        db_index=True,
        verbose_name="Telegram ID"
    )
    username = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="@username"
    )
    first_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Имя"
    )
    last_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Фамилия"
    )
    language = models.CharField(
        max_length=10, 
        default='ru', 
        verbose_name="Язык"
    )
    avatar = models.ImageField(
        upload_to='mini_app_avatars/', 
        blank=True, 
        null=True, 
        verbose_name="Аватар Mini App"
    )
    telegram_photo_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="URL фото из Telegram"
    )
    
    # Поля социальных сетей
    website = models.URLField(
        max_length=200, 
        blank=True, 
        verbose_name="Веб-сайт"
    )
    telegram = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Telegram"
    )
    github = models.URLField(
        blank=True, 
        verbose_name="GitHub"
    )
    instagram = models.URLField(
        blank=True, 
        verbose_name="Instagram"
    )
    facebook = models.URLField(
        blank=True, 
        verbose_name="Facebook"
    )
    linkedin = models.URLField(
        blank=True, 
        verbose_name="LinkedIn"
    )
    youtube = models.URLField(
        blank=True, 
        verbose_name="YouTube"
    )
    
    # Дополнительные поля для фильтрации
    gender = models.CharField(
        max_length=10,
        choices=[
            ('male', 'Мужской'),
            ('female', 'Женский'),
        ],
        blank=True,
        null=True,
        verbose_name="Пол"
    )
    birth_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата рождения"
    )
    programming_language = models.ForeignKey(
        'topics.Topic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Любимый язык программирования",
        help_text="Ссылка на тему (язык программирования) из базы тем"
    )
    programming_languages = models.ManyToManyField(
        'topics.Topic',
        blank=True,
        related_name='mini_app_users',
        verbose_name="Любимые технологии",
        help_text="Множественный выбор технологий, которые изучает пользователь"
    )
    grade = models.CharField(
        max_length=20,
        choices=[
            ('junior', 'Junior'),
            ('middle', 'Middle'),
            ('senior', 'Senior'),
        ],
        blank=True,
        null=True,
        verbose_name="Грейд",
        help_text="Уровень разработчика"
    )
    is_profile_public = models.BooleanField(
        default=True, 
        verbose_name="Публичный профиль",
        help_text="Определяет, доступен ли профиль для просмотра другим пользователям"
    )
    
    # Настройки уведомлений
    notifications_enabled = models.BooleanField(
        default=True,
        verbose_name="Уведомления включены",
        help_text="Общий переключатель всех уведомлений"
    )
    
    # Поля блокировки
    is_banned = models.BooleanField(
        default=False,
        verbose_name="Заблокирован",
        help_text="Заблокирован ли пользователь за нарушения"
    )
    banned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата блокировки",
        help_text="Когда пользователь был заблокирован"
    )
    banned_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Заблокирован до",
        help_text="Дата окончания блокировки (None = перманентный бан)"
    )
    ban_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name="Причина блокировки",
        help_text="Описание причины блокировки пользователя"
    )
    banned_by_admin_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="ID админа, заблокировавшего",
        help_text="Telegram ID администратора, который заблокировал пользователя"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Дата создания"
    )
    last_seen = models.DateTimeField(
        auto_now=True, 
        verbose_name="Последний визит"
    )
    
    # Связи с другими типами пользователей (опциональные)
    telegram_user = models.OneToOneField(
        'TelegramUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mini_app_user',
        verbose_name="Пользователь бота",
        help_text="Связь с пользователем Telegram бота, если он также использует бота"
    )
    telegram_admin = models.OneToOneField(
        'TelegramAdmin',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mini_app_user',
        verbose_name="Админ бота",
        help_text="Связь с админом Telegram бота, если он также является админом"
    )
    django_admin = models.OneToOneField(
        'DjangoAdmin',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mini_app_user',
        verbose_name="Django админ",
        help_text="Связь с Django админом, если он также управляет сайтом"
    )
    linked_custom_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mini_app_profile',
        verbose_name="Связанный пользователь сайта",
        help_text="Связь с основным пользователем сайта, если он существует"
    )

    class Meta:
        db_table = 'mini_app_users'
        verbose_name = 'Mini App Пользователь'
        verbose_name_plural = 'Mini App Пользователи'
        indexes = [
            models.Index(fields=['tenant', 'telegram_id']),
            models.Index(fields=['username']),
            models.Index(fields=['created_at']),
            models.Index(fields=['last_seen']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'telegram_id'],
                name='unique_mini_app_user_per_tenant'
            )
        ]

    def __str__(self):
        """
        Строковое представление объекта MiniAppUser.
        
        Returns:
            str: Username или Telegram ID пользователя
        """
        return self.username or f"MiniAppUser {self.telegram_id}"

    @property
    def full_name(self):
        """
        Полное имя пользователя.
        
        Returns:
            str: Полное имя или username, или Telegram ID
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"User {self.telegram_id}"
    
    @property
    def age(self):
        """
        Возраст пользователя на основе даты рождения.
        
        Returns:
            int or None: Возраст в годах или None если дата рождения не указана
        """
        if not self.birth_date:
            return None
        
        from datetime import date
        today = date.today()
        age = today.year - self.birth_date.year
        
        # Проверяем, прошел ли день рождения в этом году
        if today.month < self.birth_date.month or (today.month == self.birth_date.month and today.day < self.birth_date.day):
            age -= 1
            
        return age
    
    def get_age_range(self):
        """
        Возвращает возрастной диапазон пользователя.
        
        Returns:
            str or None: Возрастной диапазон или None если возраст неизвестен
        """
        age = self.age
        if age is None:
            return None
        
        if age <= 25:
            return "18-25"
        elif age <= 35:
            return "26-35"
        elif age <= 45:
            return "36-45"
        else:
            return "46+"
    
    def get_social_links(self):
        """
        Возвращает список социальных ссылок пользователя.
        
        Returns:
            list: Список словарей с информацией о социальных сетях
        """
        social_links = []
        
        if self.website and self.website.strip():
            social_links.append({
                "name": "Веб-сайт",
                "url": self.website,
                "icon": "🌐"
            })
        
        if self.telegram and self.telegram.strip():
            # Убираем @ если он есть в начале
            telegram_username = self.telegram.lstrip('@')
            social_links.append({
                "name": "Telegram",
                "url": f"https://t.me/{telegram_username}" if not self.telegram.startswith('http') else self.telegram,
                "icon": "📱"
            })
        
        if self.github and self.github.strip():
            social_links.append({
                "name": "GitHub",
                "url": self.github,
                "icon": "💻"
            })
        
        if self.linkedin and self.linkedin.strip():
            social_links.append({
                "name": "LinkedIn",
                "url": self.linkedin,
                "icon": "💼"
            })
        
        if self.instagram and self.instagram.strip():
            social_links.append({
                "name": "Instagram",
                "url": self.instagram,
                "icon": "📷"
            })
        
        if self.facebook and self.facebook.strip():
            social_links.append({
                "name": "Facebook",
                "url": self.facebook,
                "icon": "👥"
            })
        
        if self.youtube and self.youtube.strip():
            social_links.append({
                "name": "YouTube",
                "url": self.youtube,
                "icon": "📺"
            })
        
        return social_links

    @property
    def is_admin(self):
        """
        Проверяет, является ли пользователь админом в любой из систем.
        
        Returns:
            bool: True если пользователь является админом
        """
        return bool(self.telegram_admin or self.django_admin)

    @property
    def admin_type(self):
        """
        Возвращает тип админа пользователя.
        
        Returns:
            str: Тип админа или None
        """
        if self.telegram_admin and self.django_admin:
            return "Telegram + Django Admin"
        elif self.telegram_admin:
            return "Telegram Admin"
        elif self.django_admin:
            return "Django Admin"
        else:
            return None

    def update_last_seen(self):
        """
        Обновляет время последнего визита пользователя.
        """
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])
    
    def sync_from_telegram(self, telegram_data: dict = None) -> bool:
        """
        Синхронизирует данные пользователя из Telegram.
        
        Получает актуальные данные пользователя из Telegram Bot API или использует переданные данные.
        Обновляет: first_name, last_name, username, telegram_photo_url, language.
        После синхронизации синхронизирует данные с CustomUser если есть связь.
        
        Args:
            telegram_data (dict, optional): Словарь с данными из Telegram. Если не указан,
                пытается получить данные через Bot API.
        
        Returns:
            bool: True если данные были обновлены, False в противном случае
        """
        updated = False
        changed_fields = []
        
        try:
            if telegram_data:
                # Используем переданные данные (например, из Mini App initData)
                first_name = telegram_data.get('first_name')
                last_name = telegram_data.get('last_name')
                username = telegram_data.get('username')
                photo_url = telegram_data.get('photo_url')
                language_code = telegram_data.get('language_code', 'ru')
            else:
                # Пытаемся получить данные через Bot API
                # В Telegram Bot API нет прямого метода для получения данных пользователя по ID
                # без chat_id, поэтому используем данные из telegram_data если они есть
                # или возвращаем False
                logger.warning(f"Не удалось получить данные из Telegram для пользователя {self.telegram_id}: требуется telegram_data")
                return False
            
            # Обновляем first_name ТОЛЬКО если оно пустое
            if first_name and first_name.strip() and not (self.first_name or '').strip():
                self.first_name = first_name.strip()
                changed_fields.append('first_name')
                updated = True
                logger.debug(f"Заполнено first_name для MiniAppUser (telegram_id={self.telegram_id}): {first_name}")
            
            # Обновляем last_name ТОЛЬКО если оно пустое
            last_name_clean = ''
            if last_name is not None:
                last_name_clean = last_name.strip() if last_name else ''
            elif telegram_data and 'last_name' in telegram_data:
                last_name_value = telegram_data.get('last_name')
                last_name_clean = last_name_value.strip() if last_name_value else ''
            
            current_last_name = (self.last_name or '').strip()
            
            # Обновляем только если текущее значение пустое, а новое нет
            if not current_last_name and last_name_clean:
                self.last_name = last_name_clean
                changed_fields.append('last_name')
                updated = True
                logger.info(f"✅ Заполнено last_name для MiniAppUser (telegram_id={self.telegram_id}): '{last_name_clean}'")
            
            # Обновляем username ТОЛЬКО если оно пустое
            username_clean = None
            if username is not None:
                username_clean = username.strip() if username else None
                current_username = (self.username or '').strip() if self.username else None
                
                # Обновляем только если текущее пустое, а новое нет
                if not current_username and username_clean:
                    self.username = username_clean
                    changed_fields.append('username')
                    updated = True
                    logger.info(f"Заполнено username для MiniAppUser (telegram_id={self.telegram_id}): '{username_clean}'")
            
            # Обновляем поле telegram ТОЛЬКО если оно пустое
            telegram_username = username_clean if username_clean is not None else (self.username.strip() if self.username else None)
            current_telegram = (self.telegram or '').strip()
            
            if telegram_username and not current_telegram:
                telegram_link = f"https://t.me/{telegram_username}"
                self.telegram = telegram_link
                changed_fields.append('telegram')
                updated = True
                logger.info(f"Заполнено поле telegram для MiniAppUser (telegram_id={self.telegram_id}): '{telegram_link}'")
            
            # Обновляем telegram_photo_url и скачиваем аватарку
            if photo_url and photo_url.strip():
                photo_url_clean = photo_url.strip()
                current_photo_url = (self.telegram_photo_url or '').strip()
                photo_url_changed = photo_url_clean != current_photo_url
                
                if photo_url_changed:
                    self.telegram_photo_url = photo_url_clean
                    changed_fields.append('telegram_photo_url')
                    updated = True
                    logger.info(f"Обновлен telegram_photo_url для MiniAppUser (telegram_id={self.telegram_id}): {photo_url_clean}")
                
                # Скачиваем аватарку из Telegram только если:
                # 1. У пользователя нет аватарки (self.avatar пустое)
                # 2. ИЛИ photo_url изменился (пользователь обновил аватарку в Telegram)
                has_existing_avatar = self.avatar and hasattr(self.avatar, 'name') and self.avatar.name
                
                should_download_avatar = not has_existing_avatar or photo_url_changed
                
                if should_download_avatar:
                    try:
                        import urllib.request
                        import urllib.parse
                        import time
                        from django.core.files.base import ContentFile
                        
                        logger.info(f"📥 Загрузка аватарки для MiniAppUser (telegram_id={self.telegram_id}): has_existing_avatar={has_existing_avatar}, photo_url_changed={photo_url_changed}")
                        
                        # Загружаем изображение
                        req = urllib.request.Request(photo_url_clean)
                        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                        
                        with urllib.request.urlopen(req, timeout=10) as response:
                            image_data = response.read()
                            
                            # Определяем расширение файла
                            content_type = response.headers.get('Content-Type', '')
                            ext = 'jpg'  # по умолчанию
                            if 'jpeg' in content_type or 'jpg' in content_type:
                                ext = 'jpg'
                            elif 'png' in content_type:
                                ext = 'png'
                            elif 'webp' in content_type:
                                ext = 'webp'
                            else:
                                # Пытаемся определить по URL
                                parsed_url = urllib.parse.urlparse(photo_url_clean)
                                path = parsed_url.path.lower()
                                if path.endswith('.png'):
                                    ext = 'png'
                                elif path.endswith('.webp'):
                                    ext = 'webp'
                                elif path.endswith('.jpg') or path.endswith('.jpeg'):
                                    ext = 'jpg'
                            
                            # Создаем имя файла
                            filename = f"telegram_avatar_{self.telegram_id}_{int(time.time())}.{ext}"
                            
                            # Сохраняем в поле avatar MiniAppUser
                            self.avatar.save(filename, ContentFile(image_data), save=False)
                            changed_fields.append('avatar')
                            updated = True
                            
                            if not has_existing_avatar:
                                logger.info(f"✅ Аватарка загружена из Telegram для MiniAppUser (telegram_id={self.telegram_id}): {filename} (аватарки не было)")
                            else:
                                logger.info(f"✅ Аватарка обновлена из Telegram для MiniAppUser (telegram_id={self.telegram_id}): {filename} (photo_url изменился)")
                            
                            # Также скачиваем в CustomUser если есть связь (только если у CustomUser нет аватарки)
                            if hasattr(self, 'linked_custom_user') and self.linked_custom_user:
                                try:
                                    custom_user_has_avatar = self.linked_custom_user.avatar and hasattr(self.linked_custom_user.avatar, 'name') and self.linked_custom_user.avatar.name
                                    if not custom_user_has_avatar:
                                        from social_auth.services import TelegramAuthService
                                        if TelegramAuthService._download_avatar_from_url(photo_url_clean, self.linked_custom_user):
                                            logger.info(f"✅ Аватарка также загружена для связанного CustomUser (id={self.linked_custom_user.id}) - аватарки не было")
                                    else:
                                        logger.debug(f"⏭️ У CustomUser (id={self.linked_custom_user.id}) уже есть аватарка, пропускаем загрузку")
                                except Exception as custom_avatar_error:
                                    logger.warning(f"Ошибка при загрузке аватарки в CustomUser: {custom_avatar_error}")
                            
                    except Exception as avatar_error:
                        logger.warning(f"Ошибка при скачивании аватарки для MiniAppUser (telegram_id={self.telegram_id}): {avatar_error}")
                else:
                    logger.debug(f"⏭️ Пропуск загрузки аватарки для MiniAppUser (telegram_id={self.telegram_id}): аватарка уже есть и photo_url не изменился")
            
            # Обновляем language
            if language_code and language_code.strip():
                language = language_code.split('_')[0] if '_' in language_code else language_code
                if language.strip() != (self.language or 'ru').strip():
                    self.language = language.strip()
                    changed_fields.append('language')
                    updated = True
                    logger.debug(f"Обновлен language для MiniAppUser (telegram_id={self.telegram_id}): {language}")
            
            if updated and changed_fields:
                self.save(update_fields=changed_fields)
                logger.info(f"Синхронизированы данные из Telegram для MiniAppUser (telegram_id={self.telegram_id}): {', '.join(changed_fields)}")
                
                # Синхронизируем с CustomUser если есть связь
                if hasattr(self, 'linked_custom_user') and self.linked_custom_user:
                    try:
                        custom_user = self.linked_custom_user
                        custom_updated = False
                        custom_changed_fields = []
                        
                        # Синхронизируем базовые поля
                        if 'first_name' in changed_fields and self.first_name:
                            if not custom_user.first_name or custom_user.first_name.strip() != self.first_name.strip():
                                custom_user.first_name = self.first_name
                                custom_changed_fields.append('first_name')
                                custom_updated = True
                        
                        if 'last_name' in changed_fields:
                            new_last_name = (self.last_name or '').strip()
                            current_custom_last_name = (custom_user.last_name or '').strip()
                            if new_last_name != current_custom_last_name:
                                custom_user.last_name = self.last_name
                                custom_changed_fields.append('last_name')
                                custom_updated = True
                                logger.info(f"✅ Синхронизировано last_name для CustomUser (id={custom_user.id}) из MiniAppUser (telegram_id={self.telegram_id}): '{new_last_name}' (было: '{current_custom_last_name}')")
                            else:
                                logger.debug(f"⏭️ last_name не изменилось для CustomUser (id={custom_user.id}): '{new_last_name}'")
                        
                        if 'language' in changed_fields and self.language:
                            if not custom_user.language or custom_user.language.strip() != self.language.strip():
                                custom_user.language = self.language
                                custom_changed_fields.append('language')
                                custom_updated = True
                        
                        if custom_updated and custom_changed_fields:
                            custom_user.save(update_fields=custom_changed_fields)
                            logger.info(f"Синхронизированы данные из Telegram для CustomUser (id={custom_user.id}) из MiniAppUser (telegram_id={self.telegram_id}): {', '.join(custom_changed_fields)}")
                    except Exception as sync_error:
                        logger.warning(f"Ошибка при синхронизации данных из Telegram с CustomUser для MiniAppUser telegram_id={self.telegram_id}: {sync_error}")
            
            return updated
            
        except Exception as e:
            logger.error(f"Ошибка при синхронизации данных из Telegram для MiniAppUser (telegram_id={self.telegram_id}): {e}")
            return False

    def link_to_telegram_user(self, telegram_user):
        """
        Связывает MiniAppUser с TelegramUser.
        
        Args:
            telegram_user (TelegramUser): Объект TelegramUser для связи
        """
        if telegram_user.telegram_id != self.telegram_id:
            raise ValueError("Telegram ID не совпадает")
        
        self.telegram_user = telegram_user
        self.save(update_fields=['telegram_user'])

    def link_to_telegram_admin(self, telegram_admin):
        """
        Связывает MiniAppUser с TelegramAdmin.
        
        Args:
            telegram_admin (TelegramAdmin): Объект TelegramAdmin для связи
        """
        if telegram_admin.telegram_id != self.telegram_id:
            raise ValueError("Telegram ID не совпадает")
        
        self.telegram_admin = telegram_admin
        self.save(update_fields=['telegram_admin'])

    def link_to_django_admin(self, django_admin):
        """
        Связывает MiniAppUser с DjangoAdmin.
        
        Args:
            django_admin (DjangoAdmin): Объект DjangoAdmin для связи
        """
        # Для DjangoAdmin нет telegram_id, поэтому проверяем username
        if django_admin.username != self.username:
            raise ValueError("Username не совпадает")
        
        self.django_admin = django_admin
        self.save(update_fields=['django_admin'])

    def merge_statistics_with_custom_user(self, custom_user):
        """
        Объединяет статистику мини-аппа с основной статистикой пользователя.
        
        Args:
            custom_user (CustomUser): Объект CustomUser для объединения
        """
        from tasks.models import MiniAppTaskStatistics
        
        # Получаем всю статистику мини-аппа для этого пользователя
        mini_app_stats = MiniAppTaskStatistics.objects.filter(mini_app_user=self)
        
        merged_count = 0
        for mini_app_stat in mini_app_stats:
            try:
                mini_app_stat.merge_to_main_statistics(custom_user)
                merged_count += 1
            except Exception as e:
                logger.error(f"Ошибка при объединении статистики {mini_app_stat.id}: {e}")
        
        logger.info(f"Объединено {merged_count} записей статистики для пользователя {self.telegram_id}")
        return merged_count

    def get_combined_statistics(self):
        """
        Возвращает объединенную статистику пользователя (мини-апп + основной сайт).
        
        Returns:
            dict: Объединенная статистика
        """
        from tasks.models import TaskStatistics, MiniAppTaskStatistics
        from django.db.models import Count, Q
        
        # Статистика с основного сайта
        # Считаем уникальные translation_group_id вместо количества записей
        main_total_attempts = TaskStatistics.objects.filter(user__telegram_id=self.telegram_id).values('task__translation_group_id').distinct().count()
        main_successful_attempts = TaskStatistics.objects.filter(user__telegram_id=self.telegram_id, successful=True).values('task__translation_group_id').distinct().count()
        
        main_stats = {
            'main_total_attempts': main_total_attempts,
            'main_successful_attempts': main_successful_attempts
        }
        
        # Статистика из мини-аппа
        # Считаем уникальные translation_group_id вместо количества записей
        mini_app_total_attempts = MiniAppTaskStatistics.objects.filter(mini_app_user=self).values('task__translation_group_id').distinct().count()
        mini_app_successful_attempts = MiniAppTaskStatistics.objects.filter(mini_app_user=self, successful=True).values('task__translation_group_id').distinct().count()
        
        mini_app_stats = {
            'mini_app_total_attempts': mini_app_total_attempts,
            'mini_app_successful_attempts': mini_app_successful_attempts
        }
        
        # Объединяем статистику
        total_attempts = (main_stats['main_total_attempts'] or 0) + (mini_app_stats['mini_app_total_attempts'] or 0)
        total_successful = (main_stats['main_successful_attempts'] or 0) + (mini_app_stats['mini_app_successful_attempts'] or 0)
        
        success_rate = (total_successful / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            'total_attempts': total_attempts,
            'successful_attempts': total_successful,
            'success_rate': round(success_rate, 1),
            'main_site_attempts': main_stats['main_total_attempts'] or 0,
            'mini_app_attempts': mini_app_stats['mini_app_total_attempts'] or 0,
            'main_site_successful': main_stats['main_successful_attempts'] or 0,
            'mini_app_successful': mini_app_stats['mini_app_successful_attempts'] or 0
        }
    
    @staticmethod
    def get_rating_annotation():
        """
        Возвращает аннотацию для подсчета рейтинга Mini App пользователя.
        """
        from tasks.models import MiniAppTaskStatistics # Импорт внутри функции для избежания циклических зависимостей
        from django.db.models import Sum, Case, When, Value, IntegerField
        
        return Sum(
            Case(
                When(task_statistics__successful=True, then=Case(
                    When(task_statistics__task__difficulty='easy', then=Value(10)),
                    When(task_statistics__task__difficulty='medium', then=Value(25)),
                    When(task_statistics__task__difficulty='hard', then=Value(50)),
                    default=Value(10),
                    output_field=IntegerField(),
                )),
                default=0,
                output_field=IntegerField(),
            )
        )
    
    def calculate_rating(self):
        """
        Расчёт рейтинга Mini App пользователя на основе сложности решённых задач.
        """
        rating_data = self.__class__.objects.filter(id=self.id).annotate(
            total_score=self.get_rating_annotation()
        ).first()
        
        return (rating_data.total_score or 0) if rating_data else 0

    @property
    def quizzes_completed(self):
        """
        Возвращает количество завершенных квизов для MiniAppUser.
        """
        from tasks.models import MiniAppTaskStatistics
        return MiniAppTaskStatistics.objects.filter(mini_app_user=self, successful=True).count()
    
    @property
    def average_score(self):
        """
        Возвращает средний балл (процент успешности) для MiniAppUser.
        """
        from tasks.models import MiniAppTaskStatistics
        total_attempts = MiniAppTaskStatistics.objects.filter(mini_app_user=self).count()
        successful_attempts = MiniAppTaskStatistics.objects.filter(mini_app_user=self, successful=True).count()
        
        if total_attempts == 0:
            return 0.0
        return round((successful_attempts / total_attempts) * 100, 1)

    @property
    def is_online(self):
        """
        Проверяет, онлайн ли пользователь (последний визит в течение 5 минут).
        """
        if not self.last_seen:
            return False
        return timezone.now() - self.last_seen < timedelta(minutes=5)
    
    def ban_user(self, duration_hours=None, reason="", admin_id=None):
        """
        Блокирует пользователя.
        
        Args:
            duration_hours (int, optional): Длительность бана в часах. 
                                           None означает перманентный бан.
            reason (str): Причина блокировки
            admin_id (int, optional): Telegram ID администратора, который блокирует
        
        Returns:
            bool: True если пользователь был успешно заблокирован
        """
        from datetime import timedelta
        from django.utils import timezone
        
        self.is_banned = True
        self.banned_at = timezone.now()
        self.ban_reason = reason
        self.banned_by_admin_id = admin_id
        
        if duration_hours is not None:
            self.banned_until = timezone.now() + timedelta(hours=duration_hours)
        else:
            # Перманентный бан
            self.banned_until = None
        
        self.save()
        return True
    
    def unban_user(self):
        """
        Разблокирует пользователя.
        
        Returns:
            bool: True если пользователь был успешно разблокирован
        """
        self.is_banned = False
        self.banned_until = None
        # Сохраняем историю бана (banned_at, ban_reason, banned_by_admin_id)
        self.save()
        return True
    
    def check_ban_expired(self):
        """
        Проверяет, истёк ли срок блокировки пользователя.
        Если истёк - автоматически разблокирует.
        
        Returns:
            bool: True если бан истёк и пользователь был разблокирован, False если бан ещё активен
        """
        from django.utils import timezone
        
        if self.is_banned and self.banned_until:
            if timezone.now() >= self.banned_until:
                self.unban_user()
                return True
        return False
    
    @property
    def ban_status_text(self):
        """
        Возвращает текстовое описание статуса блокировки.
        
        Returns:
            str: Описание статуса блокировки
        """
        if not self.is_banned:
            return "Не заблокирован"
        
        from django.utils import timezone
        
        if self.banned_until is None:
            return "Заблокирован навсегда"
        
        if timezone.now() >= self.banned_until:
            return "Блокировка истекла"
        
        remaining = self.banned_until - timezone.now()
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)
        
        if hours > 24:
            days = hours // 24
            return f"Заблокирован ещё на {days} дн."
        elif hours > 0:
            return f"Заблокирован ещё на {hours} ч. {minutes} мин."
        else:
            return f"Заблокирован ещё на {minutes} мин."


class Notification(models.Model):
    """
    Модель уведомлений для пользователей Mini App.
    
    Хранит историю уведомлений для просмотра в приложении,
    отслеживает отправку в Telegram и статус прочтения.
    """
    
    NOTIFICATION_TYPES = [
        ('message', 'Новое сообщение'),
        ('comment_reply', 'Ответ на комментарий'),
        ('report', 'Жалоба на комментарий'),
        ('subscription', 'Новая подписка'),
        ('comment', 'Новый комментарий'),
        ('donation', 'Новый донат'),
        ('feedback', 'Обратная связь'),
        ('other', 'Другое'),
    ]
    
    RELATED_OBJECT_TYPES = [
        ('message', 'Сообщение'),
        ('comment', 'Комментарий'),
        ('report', 'Жалоба'),
        ('subscription', 'Подписка'),
        ('donation', 'Донат'),
        ('feedback', 'Обратная связь'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        verbose_name="Тенант",
        help_text="Тенант, к которому привязано уведомление (опционально для глобальных)"
    )
    recipient_telegram_id = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Telegram ID получателя",
        help_text="ID получателя уведомления в Telegram. NULL для админских уведомлений (всем админам)"
    )
    is_admin_notification = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Уведомление для админов",
        help_text="Если True, уведомление предназначено всем админам (recipient_telegram_id должен быть NULL)"
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        verbose_name="Тип уведомления",
        help_text="Тип события, вызвавшего уведомление"
    )
    title = models.CharField(
        max_length=255,
        verbose_name="Заголовок",
        help_text="Краткий заголовок уведомления"
    )
    message = models.TextField(
        verbose_name="Сообщение",
        help_text="Полный текст уведомления"
    )
    related_object_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="ID связанного объекта",
        help_text="ID объекта, с которым связано уведомление"
    )
    related_object_type = models.CharField(
        max_length=20,
        choices=RELATED_OBJECT_TYPES,
        null=True,
        blank=True,
        verbose_name="Тип связанного объекта",
        help_text="Тип объекта (message, comment, report, subscription)"
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Прочитано",
        help_text="Отметка о прочтении уведомления"
    )
    sent_to_telegram = models.BooleanField(
        default=False,
        verbose_name="Отправлено в Telegram",
        help_text="Отметка об отправке уведомления в Telegram"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Дата создания",
        help_text="Время создания уведомления"
    )
    
    class Meta:
        db_table = 'notifications'
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient_telegram_id', '-created_at']),
            models.Index(fields=['recipient_telegram_id', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['is_admin_notification', '-created_at']),
        ]
    
    def __str__(self):
        """
        Строковое представление уведомления.
        
        Returns:
            str: Заголовок уведомления и получатель
        """
        if self.is_admin_notification:
            return f"{self.title} (для всех админов)"
        return f"{self.title} (для {self.recipient_telegram_id})"
    
    def mark_as_read(self):
        """
        Отмечает уведомление как прочитанное.
        """
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
    
    def mark_as_sent(self):
        """
        Отмечает уведомление как отправленное в Telegram.
        """
        if not self.sent_to_telegram:
            self.sent_to_telegram = True
            self.save(update_fields=['sent_to_telegram'])


class UserAvatar(models.Model):
    """
    Модель для хранения нескольких аватарок пользователя Mini App.
    
    Пользователь может иметь до 3 аватарок (изображения или GIF),
    которые отображаются в виде галереи со свайпером.
    """
    user = models.ForeignKey(
        'MiniAppUser',
        on_delete=models.CASCADE,
        related_name='avatars',
        verbose_name="Пользователь"
    )
    image = models.ImageField(
        upload_to='mini_app_avatars/',
        verbose_name="Изображение аватарки",
        help_text="Поддерживаются изображения и GIF файлы"
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Порядок отображения",
        help_text="Порядок отображения в галерее (0, 1, 2)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    
    class Meta:
        db_table = 'user_avatars'
        verbose_name = 'Аватарка пользователя'
        verbose_name_plural = 'Аватарки пользователей'
        ordering = ['order']
        unique_together = [['user', 'order']]
        indexes = [
            models.Index(fields=['user', 'order']),
        ]
    
    def __str__(self):
        """
        Строковое представление объекта UserAvatar.
        
        Returns:
            str: Username пользователя и порядковый номер аватарки
        """
        return f"{self.user.username or self.user.telegram_id} - Avatar {self.order + 1}"
    
    def save(self, *args, **kwargs):
        """
        Переопределяем save для валидации количества аватарок.
        Максимум 3 аватарки на пользователя.
        """
        # Проверяем количество существующих аватарок
        if not self.pk:  # Только при создании новой аватарки
            existing_count = UserAvatar.objects.filter(user=self.user).count()
            if existing_count >= 3:
                raise ValueError("Пользователь может иметь максимум 3 аватарки")
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Переопределяем delete для автоматического удаления файлов.
        """
        # Удаляем физический файл
        if self.image:
            try:
                if os.path.isfile(self.image.path):
                    os.remove(self.image.path)
            except (ValueError, OSError):
                # Игнорируем ошибки удаления файлов
                pass
        
        super().delete(*args, **kwargs)
    
    @property
    def is_gif(self):
        """
        Проверяет, является ли аватарка GIF файлом.
        
        Returns:
            bool: True если файл имеет расширение .gif
        """
        if self.image:
            return self.image.name.lower().endswith('.gif')
        return False


@receiver(post_delete, sender=UserAvatar)
def delete_user_avatar_file(sender, instance, **kwargs):
    """
    Сигнал для автоматического удаления файла аватарки при удалении записи.
    """
    if instance.image:
        try:
            if os.path.isfile(instance.image.path):
                os.remove(instance.image.path)
                logger.info(f"Удален файл аватарки: {instance.image.path}")
        except (ValueError, OSError) as e:
            logger.warning(f"Не удалось удалить файл аватарки {instance.image.path}: {e}")

