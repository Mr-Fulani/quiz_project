from django.db import models

class User(models.Model):
    """
    Модель для пользователей системы.
    """
    id = models.BigAutoField(primary_key=True)
    telegram_id = models.BigIntegerField(unique=True)  # Telegram ID пользователя
    username = models.CharField(max_length=255, null=True, blank=True)  # Имя пользователя
    is_active = models.BooleanField()
    language = models.CharField(max_length=10)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    photo = models.CharField(max_length=100, null=True, blank=True)
    avatar = models.CharField(max_length=100, null=True, blank=True)
    email = models.CharField(max_length=254, null=True, blank=True)
    subscription_status = models.CharField(max_length=20, default='inactive')
    created_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'admins'
        managed = False
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return f"{self.username or 'No username'} ({self.telegram_id})"





class Admin(models.Model):
    """
    Модель для администраторов
    """
    telegram_id = models.BigIntegerField(unique=True, db_index=True)  # Telegram ID
    username = models.CharField(max_length=255, blank=True, null=True)  # Имя пользователя
    photo = models.ImageField(upload_to='admin_photos/', blank=True, null=True)  # Фото администратора
    language = models.CharField(max_length=10, default='ru')  # Язык интерфейса Telegram
    phone_number = models.CharField(max_length=15, blank=True, null=True)  # Номер телефона
    is_active = models.BooleanField(default=True)  # Статус активности

    class Meta:
        db_table = 'admins'
        verbose_name = "Администратор"
        verbose_name_plural = "Администраторы"

    def __str__(self):
        return f"{self.username or 'Admin'} ({self.telegram_id})"

    def photo_url(self):
        """
        Возвращает ссылку на фото администратора или ссылку на фото по умолчанию.
        """
        if self.photo:
            return self.photo.url
        return "/static/images/default_avatar.png"




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