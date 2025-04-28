# accounts/models.py
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.cache import cache
from django.db import models
from django.db.models import Q, Count
from django.utils import timezone


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
        related_name='customuser_set',
        blank=True,
        help_text="Группы, к которым принадлежит пользователь.",
        verbose_name="Группы"
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='customuser_permissions',
        blank=True,
        help_text="Индивидуальные разрешения пользователя.",
        verbose_name="Разрешения"
    )

    class Meta:
        db_table = 'users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

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
            rating=Count('id')
        )
        return {
            'solved_tasks': stats['solved_tasks'],
            'rating': stats['rating']
        }

    def calculate_rating(self):
        """Расчёт рейтинга на основе сложности решённых задач."""
        from tasks.models import TaskStatistics
        difficulty_stats = TaskStatistics.objects.filter(
            user=self,
            successful=True
        ).values(
            'task__difficulty'
        ).annotate(
            count=Count('id')
        ).values('task__difficulty', 'count')

        rating = 0
        multipliers = {'easy': 1, 'medium': 2, 'hard': 3}
        for stat in difficulty_stats:
            difficulty = stat['task__difficulty']
            count = stat['count']
            rating += count * multipliers.get(difficulty, 1)
        return rating

    @property
    def get_avatar_url(self):
        """Возвращает URL аватара или дефолтное изображение."""
        if self.avatar:
            return self.avatar.url
        return '/static/blog/images/avatar/default_avatar.png'

    @property
    def is_online(self):
        """Проверяет, онлайн ли пользователь (активен в последние 5 минут)."""
        return timezone.now() - self.last_seen < timedelta(minutes=5)

    @property
    def member_since(self):
        """Возвращает дату регистрации."""
        return self.date_joined

    @property
    def favorite_topics(self):
        """Возвращает топ-3 любимых темы пользователя."""
        from tasks.models import TaskStatistics
        return TaskStatistics.objects.filter(user=self) \
                   .values('task__topic__name') \
                   .annotate(count=Count('id')) \
                   .order_by('-count')[:3]


class TelegramUser(models.Model):
    """
    Модель для пользователей Telegram-бота.
    """
    telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
    username = models.CharField(max_length=255, blank=True, null=True, verbose_name="Имя пользователя")
    first_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Имя")
    last_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Фамилия")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    linked_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Связанный пользователь сайта.",
        verbose_name="Связанный пользователь"
    )

    def __str__(self):
        """Строковое представление Telegram-пользователя."""
        return self.username or f"TelegramUser {self.telegram_id}"


class BaseAdmin(AbstractUser):
    """
    Базовая модель администратора.
    """
    phone_number = models.CharField(max_length=15, null=True, blank=True, verbose_name="Номер телефона")
    language = models.CharField(max_length=10, default='ru', verbose_name="Язык")
    is_telegram_admin = models.BooleanField(default=False, verbose_name="Telegram Admin")
    is_django_admin = models.BooleanField(default=False, verbose_name="Django Admin")
    is_super_admin = models.BooleanField(default=False, verbose_name="Super Admin")

    class Meta:
        abstract = True


class TelegramAdmin(BaseAdmin):
    """
    Модель Telegram-администратора.
    """
    telegram_id = models.BigIntegerField(unique=True, null=False, db_index=True, verbose_name="Telegram ID")
    photo = models.CharField(max_length=500, null=True, blank=True, verbose_name="Фото")

    groups = models.ManyToManyField(
        'platforms.TelegramChannel',
        related_name='admins',
        blank=True,
        verbose_name='Группы Telegram'
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='telegram_admin_permissions',
        blank=True
    )

    class Meta:
        db_table = 'admins'
        verbose_name = 'Telegram Администратор'
        verbose_name_plural = 'Telegram Администраторы'

    def __str__(self):
        """Строковое представление Telegram-администратора."""
        return f"{self.username or 'Admin'} (Telegram ID: {self.telegram_id})"

    @property
    def photo_url(self):
        """Возвращает URL фото или дефолтное изображение."""
        return self.photo or "/static/images/default_avatar.png"


class DjangoAdmin(BaseAdmin):
    """
    Модель Django-администратора.
    """
    groups = models.ManyToManyField(
        Group,
        related_name='django_admin_set',
        blank=True
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='django_admin_permissions',
        blank=True
    )

    class Meta:
        db_table = 'django_admins'
        verbose_name = 'Django Администратор'
        verbose_name_plural = 'Django Администраторы'

    def __str__(self):
        """Строковое представление Django-администратора."""
        return f"{self.username or 'DjangoAdmin'}"


class SuperAdmin(BaseAdmin):
    """
    Модель супер-администратора.
    """

    class Meta:
        db_table = 'super_admins'
        verbose_name = 'Супер Администратор'
        verbose_name_plural = 'Супер Администраторы'

    def __str__(self):
        """Строковое представление супер-администратора."""
        return f"{self.username or 'SuperAdmin'}"


class UserChannelSubscription(models.Model):
    """
    Модель подписки пользователя на Telegram-канал.
    """
    STATUS_CHOICES = [
        ('active', 'Активна'),
        ('inactive', 'Неактивна'),
    ]

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='channel_subscriptions',
        verbose_name="Пользователь"
    )
    channel = models.ForeignKey(
        'platforms.TelegramChannel',
        to_field='group_id',
        db_column='channel_id',
        on_delete=models.CASCADE,
        related_name='user_subscriptions',
        verbose_name="Канал"
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

    class Meta:
        db_table = 'user_channel_subscriptions'
        verbose_name = 'Подписка на канал'
        verbose_name_plural = 'Подписки на каналы'
        unique_together = ['user', 'channel']
        indexes = [
            models.Index(fields=['subscription_status']),
            models.Index(fields=['subscribed_at']),
        ]

    def __str__(self):
        """Строковое представление подписки."""
        return f"Подписка {self.user} на {self.channel} ({self.subscription_status})"

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

