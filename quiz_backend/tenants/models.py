# tenants/models.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class Tenant(models.Model):
    """
    Модель тенанта — отдельный инстанс платформы.
    
    Каждый тенант представляет собой независимую копию платформы
    со своим доменом, ботом, темами, вопросами и пользователями.
    
    Примеры:
        - slug='quiz-code', domain='quiz-code.com'     (программирование)
        - slug='quiz-islam', domain='quiz-islam.com'   (религия)
        - slug='quiz-med', domain='quiz-med.com'       (медицина)
    """

    class Meta:
        db_table = 'tenants'
        verbose_name = _('Тенант')
        verbose_name_plural = _('Тенанты')
        ordering = ['name']

    # ── Идентификация ──────────────────────────────────────────────────────────
    slug = models.SlugField(
        unique=True,
        max_length=100,
        help_text=_('Уникальный идентификатор тенанта (например: quiz-code, quiz-islam). '
                    'Используется в URL и в docker-compose переменных.')
    )
    name = models.CharField(
        max_length=255,
        help_text=_('Отображаемое название платформы (например: Quiz Code)')
    )

    # ── Домены ─────────────────────────────────────────────────────────────────
    domain = models.CharField(
        max_length=255,
        unique=True,
        help_text=_('Основной домен сайта (например: quiz-code.com). Без www и https.')
    )
    mini_app_domain = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        help_text=_('Домен мини-аппа (например: mini.quiz-code.com). Без https.')
    )

    # ── Telegram Бот ───────────────────────────────────────────────────────────
    bot_token = models.CharField(
        max_length=255,
        blank=True,
        help_text=_('Токен Telegram-бота этого тенанта (от @BotFather)')
    )
    bot_username = models.CharField(
        max_length=100,
        blank=True,
        help_text=_('Username бота без @ (например: mr_proger_bot)')
    )

    # ── Брендинг ───────────────────────────────────────────────────────────────
    site_name = models.CharField(
        max_length=255,
        help_text=_('Название сайта для отображения в шаблонах и SEO')
    )
    site_description = models.TextField(
        blank=True,
        help_text=_('Краткое SEO-описание платформы')
    )
    contact_email = models.EmailField(
        blank=True,
        help_text=_('Email для получения сообщений из формы "Свяжитесь со мной". '
                    'Если пусто — письма не отправляются.')
    )
    theme_color = models.CharField(
        max_length=20,
        default='#6C63FF',
        help_text=_('Основной цвет темы в HEX (например: #6C63FF)')
    )
    logo = models.ImageField(
        upload_to='tenants/logos/',
        blank=True,
        null=True,
        help_text=_('Логотип тенанта')
    )

    # ── SEO ────────────────────────────────────────────────────────────────────
    default_language = models.CharField(
        max_length=10,
        default='ru',
        help_text=_('Язык по умолчанию (ru, en, ar и т.д.)')
    )
    meta_keywords = models.TextField(
        blank=True,
        help_text=_('Ключевые слова для SEO через запятую')
    )

    # ── Статус ─────────────────────────────────────────────────────────────────
    is_active = models.BooleanField(
        default=True,
        help_text=_('Активен ли тенант. Неактивные тенанты не принимают запросы.')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} ({self.domain})'

    @property
    def site_url(self):
        """Полный URL сайта."""
        return f'https://{self.domain}'

    @property
    def mini_app_url(self):
        """Полный URL мини-аппа."""
        if self.mini_app_domain:
            return f'https://{self.mini_app_domain}'
        return None

    @property
    def bot_link(self):
        """Ссылка на бота в Telegram."""
        if self.bot_username:
            return f'https://t.me/{self.bot_username}'
        return None
