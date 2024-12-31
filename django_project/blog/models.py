from django.db import models
import uuid


class Admin(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        verbose_name = "Администратор"
        verbose_name_plural = "Администраторы"
        db_table = 'admins'

    def __str__(self):
        return self.username or f"Admin {self.telegram_id}"


class Task(models.Model):
    topic = models.ForeignKey('Topic', on_delete=models.CASCADE, related_name='tasks')
    subtopic = models.ForeignKey('Subtopic', on_delete=models.SET_NULL, blank=True, null=True, related_name='tasks')
    difficulty = models.CharField(max_length=50)
    published = models.BooleanField(default=False)
    create_date = models.DateTimeField(auto_now_add=True)
    publish_date = models.DateTimeField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    external_link = models.URLField(blank=True, null=True)
    translation_group_id = models.UUIDField(default=uuid.uuid4, unique=True)
    error = models.BooleanField(default=False, blank=True)
    message_id = models.IntegerField(blank=True, null=True)
    group = models.ForeignKey('Group', on_delete=models.SET_NULL, blank=True, null=True, related_name='tasks')

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        db_table = 'tasks'

    def __str__(self):
        return f"Task {self.id} ({self.difficulty})"


class TaskTranslation(models.Model):
    task = models.ForeignKey('Task', on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=10)
    question = models.TextField()
    answers = models.JSONField()
    correct_answer = models.CharField(max_length=255)
    explanation = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Перевод задачи"
        verbose_name_plural = "Переводы задач"
        db_table = 'task_translations'

    def __str__(self):
        return f"Translation for Task {self.task_id} ({self.language})"


class User(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=150, blank=True, null=True)
    subscription_status = models.CharField(max_length=50, default='inactive')
    created_at = models.DateTimeField(auto_now_add=True)
    language = models.CharField(max_length=10, blank=True, null=True)
    deactivated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        db_table = 'users'

    def __str__(self):
        return self.username or f"User {self.telegram_id}"


class TaskStatistics(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='statistics')
    task = models.ForeignKey('Task', on_delete=models.CASCADE, related_name='statistics')
    attempts = models.PositiveIntegerField(default=0)
    successful = models.BooleanField(default=False)
    last_attempt_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Статистика задачи"
        verbose_name_plural = "Статистика задач"
        db_table = 'task_statistics'

    def __str__(self):
        return f"Statistics for User {self.user_id}, Task {self.task_id}"


class Group(models.Model):
    group_name = models.CharField(max_length=255)
    group_id = models.BigIntegerField(unique=True)
    topic = models.ForeignKey('Topic', on_delete=models.CASCADE, related_name='groups')
    language = models.CharField(max_length=10)
    location_type = models.CharField(max_length=50, default="group")
    username = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        verbose_name = "Группа"
        verbose_name_plural = "Группы"
        db_table = 'groups'

    def __str__(self):
        return self.group_name


class Topic(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Тема"
        verbose_name_plural = "Темы"
        db_table = 'topics'

    def __str__(self):
        return self.name


class Subtopic(models.Model):
    name = models.CharField(max_length=255)
    topic = models.ForeignKey('Topic', on_delete=models.CASCADE, related_name='subtopics')

    class Meta:
        verbose_name = "Подтема"
        verbose_name_plural = "Подтемы"
        db_table = 'subtopics'

    def __str__(self):
        return self.name


class UserChannelSubscription(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='channel_subscriptions')
    channel = models.ForeignKey('Group', on_delete=models.CASCADE, related_name='user_subscriptions', to_field='group_id')
    subscription_status = models.CharField(max_length=50)
    subscribed_at = models.DateTimeField(blank=True, null=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Подписка пользователя"
        verbose_name_plural = "Подписки пользователей"
        db_table = 'user_channel_subscriptions'

    def __str__(self):
        return f"Subscription: User {self.user_id} -> Channel {self.channel_id}"


class Webhook(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    url = models.URLField(unique=True)
    service_name = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Вебхук"
        verbose_name_plural = "Вебхуки"
        db_table = 'webhooks'

    def __str__(self):
        return self.service_name or "Webhook"

