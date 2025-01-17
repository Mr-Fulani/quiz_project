from django.db import models

class User(models.Model):
    """
    Модель для пользователей системы.
    """
    telegram_id = models.BigIntegerField(unique=True)  # Telegram ID пользователя
    username = models.CharField(max_length=150, blank=True, null=True)  # Имя пользователя
    subscription_status = models.CharField(max_length=50, default='inactive')  # Статус подписки
    created_at = models.DateTimeField(auto_now_add=True)  # Дата создания пользователя
    language = models.CharField(max_length=10, blank=True, null=True)  # Язык пользователя
    deactivated_at = models.DateTimeField(blank=True, null=True)  # Дата отключения

    class Meta:
        db_table = 'users'
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.username or f"Пользователь {self.telegram_id}"


class Group(models.Model):
    """
    Модель для групп или каналов.
    """
    group_name = models.CharField(max_length=255)  # Название группы
    group_id = models.BigIntegerField(unique=True)  # Telegram ID группы
    topic = models.ForeignKey('tasks.Topic', on_delete=models.CASCADE, related_name='groups')  # Связь с темой
    language = models.CharField(max_length=10)  # Язык группы
    location_type = models.CharField(max_length=50, default="group")  # Тип (группа или канал)
    username = models.CharField(max_length=150, blank=True, null=True)  # Telegram username

    class Meta:
        db_table = 'groups'
        verbose_name = "Группа"
        verbose_name_plural = "Группы"

    def __str__(self):
        return self.group_name


class UserChannelSubscription(models.Model):
    """
    Модель подписки пользователя на каналы/группы.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_subscriptions')  # Пользователь
    channel = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='user_subscriptions', to_field='group_id')  # Канал/группа
    subscription_status = models.CharField(max_length=50)  # Статус подписки
    subscribed_at = models.DateTimeField(blank=True, null=True)  # Дата подписки
    unsubscribed_at = models.DateTimeField(blank=True, null=True)  # Дата отписки

    class Meta:
        db_table = 'user_channel_subscriptions'
        verbose_name = "Подписка пользователя"
        verbose_name_plural = "Подписки пользователей"

    def __str__(self):
        return f"Подписка: Пользователь {self.user.id} -> Группа {self.channel.group_id}"