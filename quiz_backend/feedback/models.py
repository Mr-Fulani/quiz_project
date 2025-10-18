from django.db import models
from django.utils import timezone
from django.core.validators import MinLengthValidator
from django.conf import settings




class FeedbackMessage(models.Model):
    SOURCE_CHOICES = [
        ('bot', 'Telegram Bot'),
        ('mini_app', 'Mini App'),
    ]
    
    CATEGORY_CHOICES = [
        ('bug', 'Bug'),
        ('suggestion', 'Suggestion'),
        ('complaint', 'Complaint'),
        ('other', 'Other'),
    ]
    
    class Meta:
        db_table = 'feedback_messages'
        verbose_name = 'Сообщение обратной связи'
        verbose_name_plural = 'Сообщения обратной связи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['is_processed']),
            models.Index(fields=['source']),
            models.Index(fields=['category']),
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
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='bot',
        help_text='Источник сообщения (бот или мини-апп)'
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        null=True,
        blank=True,
        help_text='Категория обратной связи'
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

    @property
    def replies_count(self):
        """Возвращает количество ответов на сообщение"""
        return self.feedbackreply_set.count()

    @property
    def last_reply(self):
        """Возвращает последний ответ на сообщение"""
        return self.feedbackreply_set.order_by('-created_at').first()


class FeedbackReply(models.Model):
    """
    Модель для хранения ответов администраторов на сообщения поддержки.
    """
    class Meta:
        db_table = 'feedback_replies'
        verbose_name = 'Ответ на сообщение поддержки'
        verbose_name_plural = 'Ответы на сообщения поддержки'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['is_sent_to_user']),
        ]

    id = models.AutoField(primary_key=True)
    feedback = models.ForeignKey(
        FeedbackMessage,
        on_delete=models.CASCADE,
        verbose_name='Сообщение поддержки',
        help_text='Сообщение, на которое дан ответ'
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Администратор',
        help_text='Администратор, который дал ответ',
        null=True,
        blank=True
    )
    admin_telegram_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='Telegram ID администратора',
        help_text='Telegram ID администратора, который дал ответ'
    )
    admin_username = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Имя администратора в Telegram',
        help_text='Имя пользователя администратора в Telegram'
    )
    reply_text = models.TextField(
        validators=[MinLengthValidator(1)],
        verbose_name='Текст ответа',
        help_text='Текст ответа администратора'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания',
        help_text='Дата и время создания ответа'
    )
    is_sent_to_user = models.BooleanField(
        default=False,
        verbose_name='Отправлено пользователю',
        help_text='Было ли сообщение отправлено пользователю в Telegram'
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата отправки',
        help_text='Дата и время отправки ответа пользователю'
    )
    send_error = models.TextField(
        null=True,
        blank=True,
        verbose_name='Ошибка отправки',
        help_text='Описание ошибки при отправке сообщения'
    )

    def __str__(self):
        admin_name = self.admin_username or (self.admin.username if self.admin else 'Неизвестно')
        return f"Ответ от {admin_name} на сообщение #{self.feedback.id}"

    def mark_as_sent(self):
        """Отметить ответ как отправленный"""
        self.is_sent_to_user = True
        self.sent_at = timezone.now()
        self.save(update_fields=['is_sent_to_user', 'sent_at'])

    def mark_send_error(self, error_message):
        """Отметить ошибку отправки"""
        self.send_error = error_message
        self.save(update_fields=['send_error'])

    @property
    def short_reply(self):
        """Возвращает сокращенную версию ответа для отображения"""
        return (self.reply_text[:50] + '...') if len(self.reply_text) > 50 else self.reply_text
