from django.db import models
from django.utils.timezone import now

class FeedbackMessage(models.Model):
    """
    Модель для сообщений обратной связи от пользователей.
    """
    user_id = models.BigIntegerField()  # Telegram ID пользователя
    username = models.CharField(max_length=255, blank=True, null=True)  # Имя пользователя (опционально)
    message = models.TextField()  # Текст сообщения
    created_at = models.DateTimeField(default=now)  # Дата создания сообщения
    is_processed = models.BooleanField(default=False)  # Статус обработки сообщения

    class Meta:
        db_table = 'feedback_messages'
        verbose_name = "Сообщение обратной связи"
        verbose_name_plural = "Сообщения обратной связи"

    def __str__(self):
        return f"Сообщение от {self.username or self.user_id}: {self.message[:20]}"