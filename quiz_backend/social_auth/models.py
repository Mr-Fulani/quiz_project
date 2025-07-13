from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SocialAccount(models.Model):
    """
    Модель для хранения социальных аккаунтов пользователей.
    
    Связывает внешние социальные аккаунты с пользователями Django.
    Поддерживает различные провайдеры: Telegram, GitHub, Google, VK и др.
    """
    PROVIDER_CHOICES = [
        ('telegram', 'Telegram'),
        ('github', 'GitHub'),
        ('google', 'Google'),
        ('vk', 'VKontakte'),
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='social_accounts',
        verbose_name=_('Пользователь')
    )
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        verbose_name=_('Провайдер')
    )
    provider_user_id = models.CharField(
        max_length=255,
        verbose_name=_('ID пользователя в провайдере')
    )
    username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Username в провайдере')
    )
    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_('Email в провайдере')
    )
    first_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Имя')
    )
    last_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Фамилия')
    )
    avatar_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('URL аватара')
    )
    access_token = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Access token')
    )
    refresh_token = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Refresh token')
    )
    token_expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Время истечения токена')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Активен')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Дата обновления')
    )
    last_login_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Последний вход')
    )

    class Meta:
        db_table = 'social_accounts'
        verbose_name = _('Социальный аккаунт')
        verbose_name_plural = _('Социальные аккаунты')
        unique_together = ('provider', 'provider_user_id')
        indexes = [
            models.Index(fields=['provider', 'provider_user_id']),
            models.Index(fields=['user', 'provider']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_provider_display()}"

    def update_last_login(self):
        """Обновляет время последнего входа."""
        self.last_login_at = timezone.now()
        self.save(update_fields=['last_login_at'])

    def is_token_expired(self):
        """Проверяет, истек ли токен."""
        if not self.token_expires_at:
            return True
        return timezone.now() > self.token_expires_at

    @property
    def display_name(self):
        """Возвращает отображаемое имя пользователя."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return self.username
        return str(self.provider_user_id)


class SocialLoginSession(models.Model):
    """
    Модель для отслеживания сессий социальной аутентификации.
    
    Хранит информацию о попытках входа через социальные сети
    для безопасности и аналитики.
    """
    session_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_('ID сессии')
    )
    social_account = models.ForeignKey(
        SocialAccount,
        on_delete=models.CASCADE,
        related_name='login_sessions',
        verbose_name=_('Социальный аккаунт')
    )
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name=_('IP адрес')
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('User Agent')
    )
    is_successful = models.BooleanField(
        default=False,
        verbose_name=_('Успешный вход')
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Сообщение об ошибке')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )

    class Meta:
        db_table = 'social_login_sessions'
        verbose_name = _('Сессия социальной аутентификации')
        verbose_name_plural = _('Сессии социальной аутентификации')
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['social_account', 'created_at']),
            models.Index(fields=['is_successful']),
        ]

    def __str__(self):
        return f"{self.social_account} - {self.created_at}"


class SocialAuthSettings(models.Model):
    """
    Модель для настроек социальной аутентификации.
    
    Хранит конфигурацию для различных провайдеров.
    """
    provider = models.CharField(
        max_length=20,
        choices=SocialAccount.PROVIDER_CHOICES,
        unique=True,
        verbose_name=_('Провайдер')
    )
    client_id = models.CharField(
        max_length=255,
        verbose_name=_('Client ID')
    )
    client_secret = models.CharField(
        max_length=255,
        verbose_name=_('Client Secret')
    )
    is_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Включен')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Дата обновления')
    )

    class Meta:
        db_table = 'social_auth_settings'
        verbose_name = _('Настройка социальной аутентификации')
        verbose_name_plural = _('Настройки социальной аутентификации')

    def __str__(self):
        return f"{self.get_provider_display()} - {'Включен' if self.is_enabled else 'Отключен'}"
