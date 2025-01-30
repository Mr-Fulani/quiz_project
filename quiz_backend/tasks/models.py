import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

class Task(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Легкий'),
        ('medium', 'Средний'),
        ('hard', 'Сложный'),
    ]

    class Meta:
        db_table = 'tasks'
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['-create_date']
        indexes = [
            models.Index(fields=['create_date']),
            models.Index(fields=['published']),
        ]

    id = models.AutoField(primary_key=True)
    topic = models.ForeignKey(
        'topics.Topic',
        on_delete=models.CASCADE,
        related_name='tasks',
        help_text='Тема, к которой относится задача'
    )
    subtopic = models.ForeignKey(
        'topics.Subtopic',
        on_delete=models.CASCADE,
        null=True,
        related_name='tasks',
        help_text='Подтема задачи'
    )
    difficulty = models.CharField(
        max_length=50,
        choices=DIFFICULTY_CHOICES,
        help_text='Уровень сложности задачи'
    )
    published = models.BooleanField(
        default=False,
        help_text='Опубликована ли задача'
    )
    create_date = models.DateTimeField(
        default=timezone.now,
        help_text='Дата создания задачи'
    )
    publish_date = models.DateTimeField(
        null=True,
        help_text='Дата публикации задачи'
    )
    image_url = models.URLField(
        max_length=255,
        null=True,
        help_text='URL изображения задачи'
    )
    external_link = models.URLField(
        max_length=255,
        null=True,
        help_text='Внешняя ссылка'
    )
    translation_group_id = models.UUIDField(
        default=uuid.uuid4,
        help_text='ID группы связанных переводов'
    )
    error = models.BooleanField(
        default=False,
        help_text='Содержит ли задача ошибки'
    )
    message_id = models.IntegerField(
        null=True,
        help_text='ID связанного сообщения'
    )
    group = models.ForeignKey(
        'platforms.TelegramChannel',
        on_delete=models.SET_NULL,
        null=True,
        related_name='tasks',
        help_text='Связанная группа'
    )

    def clean(self):
        if self.publish_date and self.publish_date < self.create_date:
            raise ValidationError("Дата публикации не может быть раньше даты создания")

    def save(self, *args, **kwargs):
        if self.published and not self.publish_date:
            self.publish_date = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Задача {self.id} ({self.get_difficulty_display()})"


class TaskTranslation(models.Model):
    class Meta:
        db_table = 'task_translations'
        verbose_name = 'Перевод задачи'
        verbose_name_plural = 'Переводы задач'
        indexes = [
            models.Index(fields=['language']),
        ]

    id = models.AutoField(primary_key=True)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='translations',
        help_text='Связанная задача'
    )
    language = models.CharField(
        max_length=10,
        help_text='Язык перевода'
    )
    question = models.TextField(
        help_text='Текст вопроса'
    )
    answers = models.JSONField(
        help_text='Варианты ответов в формате JSON'
    )
    correct_answer = models.CharField(
        max_length=255,
        help_text='Правильный ответ'
    )
    explanation = models.TextField(
        null=True,
        help_text='Объяснение ответа'
    )

    def __str__(self):
        return f"Перевод задачи {self.task_id} ({self.language})"


class TaskStatistics(models.Model):
    class Meta:
        db_table = 'task_statistics'
        verbose_name = 'Статистика задачи'
        verbose_name_plural = 'Статистика задач'
        indexes = [
            models.Index(fields=['last_attempt_date']),
        ]
        unique_together = ('user', 'task')

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='statistics',
        help_text='Пользователь'
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='statistics',
        help_text='Задача'
    )
    attempts = models.IntegerField(
        default=0,
        help_text='Количество попыток'
    )
    successful = models.BooleanField(
        default=False,
        help_text='Успешно ли решена задача'
    )
    last_attempt_date = models.DateTimeField(
        auto_now=True,
        help_text='Дата последней попытки'
    )

    def __str__(self):
        return f"Статистика: Задача {self.task_id}, Пользователь {self.user_id}"


class TaskPoll(models.Model):
    class Meta:
        db_table = 'task_polls'
        verbose_name = 'Опрос задачи'
        verbose_name_plural = 'Опросы задач'

    id = models.AutoField(primary_key=True)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='polls',
        help_text='Связанная задача'
    )
    translation = models.ForeignKey(
        TaskTranslation,
        on_delete=models.CASCADE,
        help_text='Связанный перевод'
    )
    poll_id = models.CharField(
        max_length=255,
        unique=True,
        help_text='ID опроса в Telegram'
    )
    poll_question = models.TextField(
        null=True,
        help_text='Вопрос опроса'
    )
    poll_options = models.JSONField(
        null=True,
        help_text='Варианты ответов в формате JSON'
    )
    is_anonymous = models.BooleanField(
        default=True,
        help_text='Анонимный ли опрос'
    )
    poll_type = models.CharField(
        max_length=50,
        null=True,
        help_text='Тип опроса'
    )
    allows_multiple_answers = models.BooleanField(
        default=False,
        help_text='Разрешены ли множественные ответы'
    )
    total_voter_count = models.IntegerField(
        default=0,
        help_text='Общее количество проголосовавших'
    )
    poll_link = models.CharField(
        max_length=255,
        null=True,
        help_text='Ссылка на опрос'
    )

    def __str__(self):
        return f"Опрос для задачи {self.task_id}"