from django.db import models
from django.utils import timezone
from django.core.validators import MinLengthValidator




class FeedbackMessage(models.Model):
    class Meta:
        db_table = 'feedback_messages'
        verbose_name = 'Сообщение обратной связи'
        verbose_name_plural = 'Сообщения обратной связи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['is_processed']),
        ]

    id = models.AutoField(primary_key=True)
    user_id = models.BigIntegerField(
        help_text='Telegram ID пользователя'
    )
    username = models.CharField(
        max_length=255,
        null=True,
        help_text='Имя пользователя в Telegram'
    )
    message = models.TextField(
        validators=[MinLengthValidator(3)],
        help_text='Текст сообщения обратной связи'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        help_text='Дата и время создания сообщения'
    )
    is_processed = models.BooleanField(
        default=False,
        help_text='Статус обработки сообщения'
    )

    def __str__(self):
        return f"Сообщение от {self.username or self.user_id} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

    def mark_as_processed(self):
        """Отметить сообщение как обработанное"""
        self.is_processed = True
        self.save(update_fields=['is_processed'])

    @property
    def short_message(self):
        """Возвращает сокращенную версию сообщения для отображения"""
        return (self.message[:50] + '...') if len(self.message) > 50 else self.message
