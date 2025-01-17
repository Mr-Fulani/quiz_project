from django.db import models
import uuid


class Topic(models.Model):
    """
    Модель для тем задач.
    """
    name = models.CharField(max_length=255, unique=True)  # Название темы
    description = models.TextField(blank=True, null=True)  # Описание темы

    class Meta:
        db_table = 'topics'
        verbose_name = "Тема"
        verbose_name_plural = "Темы"

    def __str__(self):
        return self.name


class Subtopic(models.Model):
    """
    Модель для подтем, связанных с конкретной темой.
    """
    name = models.CharField(max_length=255)  # Название подтемы
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics')  # Связь с темой

    class Meta:
        db_table = 'subtopics'
        verbose_name = "Подтема"
        verbose_name_plural = "Подтемы"

    def __str__(self):
        return self.name


class Task(models.Model):
    """
    Модель для задач.
    """
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='tasks')  # Связь с темой
    subtopic = models.ForeignKey(Subtopic, on_delete=models.SET_NULL, blank=True, null=True, related_name='tasks')  # Связь с подтемой
    difficulty = models.CharField(max_length=50)  # Уровень сложности задачи
    published = models.BooleanField(default=False)  # Статус публикации задачи
    create_date = models.DateTimeField(auto_now_add=True)  # Дата создания задачи
    publish_date = models.DateTimeField(blank=True, null=True)  # Дата публикации
    image_url = models.URLField(blank=True, null=True)  # Ссылка на изображение
    external_link = models.URLField(blank=True, null=True)  # Ссылка на сторонний ресурс
    translation_group_id = models.UUIDField(default=uuid.uuid4, unique=True)  # Уникальный ID группы переводов
    error = models.BooleanField(default=False, blank=True)  # Ошибка в задаче
    message_id = models.IntegerField(blank=True, null=True)  # ID сообщения Telegram
    group = models.ForeignKey('users.Group', on_delete=models.SET_NULL, blank=True, null=True, related_name='tasks')  # Связь с группой

    class Meta:
        db_table = 'tasks'
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"

    def __str__(self):
        return f"Задача {self.id} ({self.difficulty})"


class TaskTranslation(models.Model):
    """
    Модель для переводов задач.
    """
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='translations')  # Связь с задачей
    language = models.CharField(max_length=10)  # Язык перевода
    question = models.TextField()  # Текст вопроса
    answers = models.JSONField()  # Варианты ответов
    correct_answer = models.CharField(max_length=255)  # Правильный ответ
    explanation = models.TextField(blank=True, null=True)  # Объяснение ответа

    class Meta:
        db_table = 'task_translations'
        verbose_name = "Перевод задачи"
        verbose_name_plural = "Переводы задач"

    def __str__(self):
        return f"Перевод задачи {self.task.id} на {self.language}"


class TaskStatistics(models.Model):
    """
    Модель для статистики задач.
    """
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='statistics')  # Пользователь
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='statistics')  # Задача
    attempts = models.PositiveIntegerField(default=0)  # Количество попыток
    successful = models.BooleanField(default=False)  # Успешность
    last_attempt_date = models.DateTimeField(blank=True, null=True)  # Последняя попытка

    class Meta:
        db_table = 'task_statistics'
        verbose_name = "Статистика задачи"
        verbose_name_plural = "Статистика задач"

    def __str__(self):
        return f"Статистика задачи {self.task.id} для пользователя {self.user.id}"