# accounts/models.py
import logging
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.db.models import Q, Count
from django.utils import timezone

logger = logging.getLogger(__name__)


class CustomUser(AbstractUser):
    """
    Кастомная модель пользователя с объединёнными полями из Profile.
    """
    subscription_status = models.CharField(max_length=20, default='inactive', verbose_name="Статус подписки")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    language = models.CharField(max_length=10, blank=True, null=True, verbose_name="Язык")
    deactivated_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата деактивации")
    telegram_id = models.BigIntegerField(blank=True, null=True, verbose_name="Telegram ID")

    # Поля из Profile
    avatar = models.ImageField(upload_to='avatar/', blank=True, null=True, verbose_name="Аватар")
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
        stats = TaskStatistics.objects.filter(user=self).aggregate(
            solved_tasks=Count('id', filter=Q(successful=True)),
            total_attempts=Count('id')
        )
        return {
            'solved_tasks': stats['solved_tasks'],
            'rating': self.calculate_rating(),  # Теперь возвращаем как есть
            'total_attempts': stats['total_attempts']
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
    """
    STATUS_CHOICES = [
        ('active', 'Активна'),
        ('inactive', 'Неактивна'),
    ]

    telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
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
        db_table = 'telegram_users'  # Добавлено: явное указание имени таблицы
        verbose_name = 'Telegram Пользователь'
        verbose_name_plural = 'Telegram Пользователи'

    def __str__(self):
        """
        Строковое представление объекта TelegramUser.
        """
        return self.username or f"TelegramUser {self.telegram_id}"









class TelegramAdmin(models.Model):
    """
    Модель администратора Telegram-бота и Mini App.
    Хранит данные для управления Telegram-группами.
    """
    telegram_id = models.BigIntegerField(
        unique=True, null=False, db_index=True, verbose_name="Telegram ID"
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

    def unsubscribe(self):
        """Деактивировать подписку."""
        self.subscription_status = 'inactive'
        self.unsubscribed_at = timezone.now()
        self.save()


class MiniAppUser(models.Model):
    """
    Модель пользователя Telegram Mini App.
    
    Хранит данные о пользователях, которые используют Mini App для прохождения квизов,
    просмотра профиля и статистики. Может быть связан с другими типами пользователей
    (TelegramUser, TelegramAdmin, DjangoAdmin) если один человек использует разные части системы.
    
    Особенности:
    - Уникальный telegram_id для каждого пользователя Mini App
    - Связи с другими таблицами пользователей (опциональные)
    - Отслеживание активности в Mini App
    """
    telegram_id = models.BigIntegerField(
        unique=True, 
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
            models.Index(fields=['telegram_id']),
            models.Index(fields=['username']),
            models.Index(fields=['created_at']),
            models.Index(fields=['last_seen']),
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
        main_stats = TaskStatistics.objects.filter(user__telegram_id=self.telegram_id).aggregate(
            main_total_attempts=Count('id'),
            main_successful_attempts=Count('id', filter=Q(successful=True))
        )
        
        # Статистика из мини-аппа
        mini_app_stats = MiniAppTaskStatistics.objects.filter(mini_app_user=self).aggregate(
            mini_app_total_attempts=Count('id'),
            mini_app_successful_attempts=Count('id', filter=Q(successful=True))
        )
        
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

