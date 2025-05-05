import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import URLValidator




class Webhook(models.Model):
    class Meta:
        db_table = 'webhooks'
        verbose_name = 'Вебхук'
        verbose_name_plural = 'Вебхуки'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['is_active']),
        ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        help_text='Уникальный идентификатор вебхука'
    )
    url = models.CharField(
        max_length=255,
        unique=True,
        help_text='URL вебхука'
    )
    service_name = models.CharField(
        max_length=100,
        null=True,
        help_text='Название сервиса (например, make.com, Zapier)'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Активен ли вебхук'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        help_text='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='Дата последнего обновления'
    )

    def clean(self):
        """Резервная проверка: добавляет https://, если протокол отсутствует."""
        if self.url and not self.url.startswith(('http://', 'https://')):
            self.url = f"https://{self.url}"

    def __str__(self):
        return f"{self.service_name or 'Неизвестный сервис'}: {self.url}"

    def __str__(self):
        return f"{self.service_name or 'Неизвестный сервис'}: {self.url}"


class DefaultLink(models.Model):
    class Meta:
        db_table = 'default_links'
        verbose_name = 'Ссылка по умолчанию'
        verbose_name_plural = 'Ссылки по умолчанию'
        unique_together = ['language', 'topic']
        indexes = [
            models.Index(fields=['language', 'topic']),
        ]

    id = models.AutoField(primary_key=True)
    language = models.CharField(
        max_length=10,
        help_text='Язык'
    )
    topic = models.CharField(
        max_length=100,
        help_text='Тема'
    )
    link = models.CharField(
        max_length=255,
        validators=[URLValidator()],
        help_text='URL ссылки'
    )

    def __str__(self):
        return f"{self.language} - {self.topic}: {self.link}"


class MainFallbackLink(models.Model):
    class Meta:
        db_table = 'main_fallback_links'
        verbose_name = 'Основная резервная ссылка'
        verbose_name_plural = 'Основные резервные ссылки'
        indexes = [
            models.Index(fields=['language']),
        ]

    id = models.AutoField(primary_key=True)
    language = models.CharField(
        max_length=10,
        unique=True,
        help_text='Язык'
    )
    link = models.CharField(
        max_length=255,
        validators=[URLValidator()],
        help_text='URL резервной ссылки'
    )

    def clean(self):
        # Приводим язык к нижнему регистру перед сохранением
        self.language = self.language.lower()

    def __str__(self):
        return f"Резервная ссылка для {self.language}: {self.link}"
