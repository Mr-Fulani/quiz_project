from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SocialAccount(models.Model):
    """
    Модель для хранения социальных аккаунтов пользователей.
    
    Связывает внешние социальные аккаунты с пользователями Django.
    Поддерживает различные провайдеры: Telegram, GitHub, Google, VK и др.
    
    Интеграция с другими системами:
    - Связь с TelegramUser (пользователи бота)
    - Связь с MiniAppUser (пользователи Mini App)
    - Связь с TelegramAdmin (админы бота)
    - Связь с DjangoAdmin (админы Django)
    """


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
    
    # Связи с другими системами пользователей
    telegram_user = models.OneToOneField(
        'accounts.TelegramUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='social_account',
        verbose_name=_('Пользователь бота'),
        help_text=_('Связь с пользователем Telegram бота, если он также использует бота')
    )
    mini_app_user = models.OneToOneField(
        'accounts.MiniAppUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='social_account',
        verbose_name=_('Mini App пользователь'),
        help_text=_('Связь с пользователем Mini App, если он также использует Mini App')
    )
    telegram_admin = models.OneToOneField(
        'accounts.TelegramAdmin',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='social_account',
        verbose_name=_('Админ бота'),
        help_text=_('Связь с админом Telegram бота, если он также является админом')
    )
    django_admin = models.OneToOneField(
        'accounts.DjangoAdmin',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='social_account',
        verbose_name=_('Django админ'),
        help_text=_('Связь с Django админом, если он также управляет сайтом')
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

    @property
    def auth_methods(self):
        """
        Возвращает список методов авторизации пользователя.
        
        Returns:
            list: Список методов авторизации
        """
        methods = [self.provider]
        if self.telegram_user:
            methods.append('bot')
        if self.mini_app_user:
            methods.append('mini_app')
        return methods

    def link_to_telegram_user(self, telegram_user):
        """
        Связывает SocialAccount с TelegramUser.
        
        Args:
            telegram_user: Объект TelegramUser для связи
        """
        if telegram_user.telegram_id != int(self.provider_user_id):
            raise ValueError("Telegram ID не совпадает")
        
        self.telegram_user = telegram_user
        self.save(update_fields=['telegram_user'])

    def link_to_mini_app_user(self, mini_app_user):
        """
        Связывает SocialAccount с MiniAppUser.
        
        Args:
            mini_app_user: Объект MiniAppUser для связи
        """
        if mini_app_user.telegram_id != int(self.provider_user_id):
            raise ValueError("Telegram ID не совпадает")
        
        self.mini_app_user = mini_app_user
        self.save(update_fields=['mini_app_user'])

    def link_to_telegram_admin(self, telegram_admin):
        """
        Связывает SocialAccount с TelegramAdmin.
        
        Args:
            telegram_admin: Объект TelegramAdmin для связи
        """
        if telegram_admin.telegram_id != int(self.provider_user_id):
            raise ValueError("Telegram ID не совпадает")
        
        self.telegram_admin = telegram_admin
        self.save(update_fields=['telegram_admin'])

    def link_to_django_admin(self, django_admin):
        """
        Связывает SocialAccount с DjangoAdmin.
        
        Args:
            django_admin: Объект DjangoAdmin для связи
        """
        # Для DjangoAdmin нет telegram_id, поэтому проверяем username
        if django_admin.username != self.username:
            raise ValueError("Username не совпадает")
        
        self.django_admin = django_admin
        self.save(update_fields=['django_admin'])

    def auto_link_existing_users(self):
        """
        Автоматически связывает SocialAccount с существующими пользователями.
        
        Returns:
            int: Количество созданных связей
        """
        linked_count = 0
        
        try:
            # Связываем с TelegramUser
            from accounts.models import TelegramUser
            telegram_user = TelegramUser.objects.filter(
                telegram_id=int(self.provider_user_id)
            ).first()
            if telegram_user and not self.telegram_user:
                self.link_to_telegram_user(telegram_user)
                linked_count += 1
            
            # Связываем с MiniAppUser
            from accounts.models import MiniAppUser
            mini_app_user = MiniAppUser.objects.filter(
                telegram_id=int(self.provider_user_id)
            ).first()
            if mini_app_user and not self.mini_app_user:
                self.link_to_mini_app_user(mini_app_user)
                linked_count += 1
            
            # Связываем с TelegramAdmin
            from accounts.models import TelegramAdmin
            telegram_admin = TelegramAdmin.objects.filter(
                telegram_id=int(self.provider_user_id)
            ).first()
            if telegram_admin and not self.telegram_admin:
                self.link_to_telegram_admin(telegram_admin)
                linked_count += 1
            
            # Связываем с DjangoAdmin (по username)
            if self.username:
                from accounts.models import DjangoAdmin
                django_admin = DjangoAdmin.objects.filter(
                    username=self.username
                ).first()
                if django_admin and not self.django_admin:
                    self.link_to_django_admin(django_admin)
                    linked_count += 1
                    
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Ошибка при автоматическом связывании SocialAccount {self.provider_user_id}: {e}")
        
        return linked_count


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
