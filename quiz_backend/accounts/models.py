from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils import timezone
from django.core.validators import MinLengthValidator, RegexValidator





class CustomUser(AbstractUser):
    """
    Кастомная модель пользователя
    """
    subscription_status = models.CharField(max_length=20, default='inactive')  # Статус подписки
    created_at = models.DateTimeField(auto_now_add=True)  # Дата создания
    language = models.CharField(max_length=10, blank=True, null=True)  # Язык пользователя
    deactivated_at = models.DateTimeField(blank=True, null=True)  # Дата деактивации (если пользователь стал неактивным)

    groups = models.ManyToManyField(
        Group,
        related_name='customuser_set',
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='customuser_permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    class Meta:
        db_table = 'users'  # Имя таблицы в базе данных
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f"{self.username or 'User'}"










class BaseAdmin(AbstractUser):
    """
    Базовая модель администратора.
    """
    phone_number = models.CharField(max_length=15, null=True, blank=True)  # Номер телефона
    language = models.CharField(max_length=10, default='ru', null=False)  # Язык интерфейса
    is_telegram_admin = models.BooleanField(default=False, verbose_name="Telegram Admin")  # Флаг для Telegram администраторов
    is_django_admin = models.BooleanField(default=False, verbose_name="Django Admin")  # Флаг для Django администраторов
    is_super_admin = models.BooleanField(default=False, verbose_name="Super Admin")  # Флаг для супер администраторов

    class Meta:
        abstract = True  # Делает модель абстрактной


class TelegramAdmin(BaseAdmin):
    """
    Модель Telegram администратора.
    """
    telegram_id = models.BigIntegerField(unique=True, null=False, db_index=True)  # Telegram ID администратора
    photo = models.CharField(max_length=500, null=True, blank=True)  # Ссылка на фото администратора

    groups = models.ManyToManyField(
        'platforms.TelegramChannel',  # Изменено с 'TelegramChannel' на 'platforms.TelegramChannel'
        related_name='admins',  # Поле для обратной связи
        blank=True,
        verbose_name='Группы Telegram',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='telegram_admin_permissions',
        blank=True,
    )

    class Meta:
        db_table = 'admins'
        verbose_name = 'Telegram Администратор'
        verbose_name_plural = 'Telegram Администраторы'

    def __str__(self):
        return f"{self.username or 'Admin'} (Telegram ID: {self.telegram_id})"

    @property
    def photo_url(self):
        return self.photo or "/static/images/default_avatar.png"



class DjangoAdmin(BaseAdmin):
    """
    Модель Django администратора.
    """

    groups = models.ManyToManyField(
        Group,
        related_name='django_admin_set',
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='django_admin_permissions',
        blank=True,
    )


    class Meta:
        db_table = 'django_admins'
        verbose_name = 'Django Администратор'
        verbose_name_plural = 'Django Администраторы'

    def __str__(self):
        return f"{self.username or 'DjangoAdmin'}"


class SuperAdmin(BaseAdmin):
    """
    Модель супер администратора.
    """
    class Meta:
        db_table = 'super_admins'
        verbose_name = 'Супер Администратор'
        verbose_name_plural = 'Супер Администраторы'

    def __str__(self):
        return f"{self.username or 'SuperAdmin'}"


class UserChannelSubscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Активна'),
        ('inactive', 'Неактивна'),
    ]

    class Meta:
        db_table = 'user_channel_subscriptions'
        verbose_name = 'Подписка на канал'
        verbose_name_plural = 'Подписки на каналы'
        unique_together = ['user', 'channel']
        indexes = [
            models.Index(fields=['subscription_status']),
            models.Index(fields=['subscribed_at']),
        ]

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='channel_subscriptions',
        help_text='Пользователь'
    )
    channel = models.ForeignKey(
        'platforms.TelegramChannel',
        to_field='group_id',
        db_column='channel_id',
        on_delete=models.CASCADE,
        related_name='user_subscriptions',
        help_text='Канал или группа'
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='inactive',
        help_text='Статус подписки'
    )
    subscribed_at = models.DateTimeField(
        null=True,
        help_text='Дата подписки'
    )
    unsubscribed_at = models.DateTimeField(
        null=True,
        help_text='Дата отписки'
    )

    def __str__(self):
        return f"Подписка {self.user} на {self.channel} ({self.get_subscription_status_display()})"

    def subscribe(self):
        """Активировать подписку"""
        self.subscription_status = 'active'
        self.subscribed_at = timezone.now()
        self.unsubscribed_at = None
        self.save()

    def unsubscribe(self):
        """Деактивировать подписку"""
        self.subscription_status = 'inactive'
        self.unsubscribed_at = timezone.now()
        self.save()


