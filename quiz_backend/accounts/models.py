from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission, User
from django.core.cache import cache
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone





class CustomUser(AbstractUser):
    """
    Кастомная модель пользователя
    """
    subscription_status = models.CharField(max_length=20, default='inactive')  # Статус подписки
    created_at = models.DateTimeField(auto_now_add=True)  # Дата создания
    language = models.CharField(max_length=10, blank=True, null=True)  # Язык пользователя
    deactivated_at = models.DateTimeField(blank=True, null=True)  # Дата деактивации (если пользователь стал неактивным)
    photo = models.URLField(max_length=500, blank=True, null=True)
    telegram_id = models.BigIntegerField(blank=True, null=True)

    # Переопределяем поля, которые хотим сделать необязательными:
    email = models.EmailField(blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)

    groups = models.ManyToManyField(
        Group,
        related_name='customuser_set',
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='customuser_permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    class Meta:
        db_table = 'users'  # Имя таблицы в базе данных
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f"{self.username or 'User'}"

    def get_unread_messages_count(self):
        return self.received_messages.filter(is_read=False).count()

    def get_statistics(self):
        """Получение актуальной статистики без кэширования"""
        from tasks.models import TaskStatistics
        from django.db.models import Count
        
        stats = TaskStatistics.objects.filter(user=self).aggregate(
            solved_tasks=Count('id', filter=Q(successful=True)),
            rating=Count('id')
        )
        
        return {
            'solved_tasks': stats['solved_tasks'],
            'rating': stats['rating']
        }
    
    @property
    def statistics(self):
        """Получение статистики пользователя"""
        from tasks.models import TaskStatistics
        from django.db.models import Count
        
        # Получаем статистику
        stats = TaskStatistics.objects.filter(user=self).aggregate(
            solved_tasks=Count('id', filter=Q(successful=True)),
            rating=Count('id')  # Временно используем общее количество попыток как рейтинг
        )
        
        return {
            'solved_tasks': stats['solved_tasks'],
            'rating': stats['rating']
        }
    
    def calculate_rating(self):
        from tasks.models import TaskStatistics
        from django.db.models import Count

        # Получаем статистику по сложности
        difficulty_stats = TaskStatistics.objects.filter(
            user=self,
            successful=True
        ).values(
            'task__difficulty'
        ).annotate(
            count=Count('id')
        ).values('task__difficulty', 'count')
        
        # Рассчитываем рейтинг
        rating = 0
        for stat in difficulty_stats:
            # Множители для разных уровней сложности
            multipliers = {
                'easy': 1,
                'medium': 2,
                'hard': 3
            }
            difficulty = stat['task__difficulty']
            count = stat['count']
            rating += count * multipliers.get(difficulty, 1)
            
        return rating







class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


    linked_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                       help_text="Если телеграм пользователь привязан к пользователю сайта.")

    def __str__(self):
        return self.username or f"TelegramUser {self.telegram_id}"














class BaseAdmin(AbstractUser):
    """
    Базовая модель администратора.
    """
    phone_number = models.CharField(max_length=15, null=True, blank=True)  # Номер телефона
    language = models.CharField(max_length=10, default='ru', null=False)  # Язык интерфейса
    is_telegram_admin = models.BooleanField(default=False, null=True, blank=True, verbose_name="Telegram Admin")
    is_django_admin = models.BooleanField(default=False, verbose_name="Django Admin")
    is_super_admin = models.BooleanField(default=False, verbose_name="Super Admin")

    class Meta:
        abstract = True  # Делает модель абстрактной



class TelegramAdmin(BaseAdmin):
    """
    Модель Telegram администратора.
    """
    telegram_id = models.BigIntegerField(unique=True, null=False, db_index=True)  # Telegram ID администратора
    photo = models.CharField(max_length=500, null=True, blank=True)  # Ссылка на фото администратора

    groups = models.ManyToManyField(
        'platforms.TelegramChannel',  # Изменено с 'TelegramChannel' на 'platforms.TelegramChannel'
        related_name='admins',  # Поле для обратной связи
        blank=True,
        verbose_name='Группы Telegram',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='telegram_admin_permissions',
        blank=True,
    )

    class Meta:
        db_table = 'admins'
        verbose_name = 'Telegram Администратор'
        verbose_name_plural = 'Telegram Администраторы'

    def __str__(self):
        return f"{self.username or 'Admin'} (Telegram ID: {self.telegram_id})"

    @property
    def photo_url(self):
        return self.photo or "/static/images/default_avatar.png"



class DjangoAdmin(BaseAdmin):
    """
    Модель Django администратора.
    """

    groups = models.ManyToManyField(
        Group,
        related_name='django_admin_set',
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='django_admin_permissions',
        blank=True,
    )


    class Meta:
        db_table = 'django_admins'
        verbose_name = 'Django Администратор'
        verbose_name_plural = 'Django Администраторы'

    def __str__(self):
        return f"{self.username or 'DjangoAdmin'}"


class SuperAdmin(BaseAdmin):
    """
    Модель супер администратора.
    """
    class Meta:
        db_table = 'super_admins'
        verbose_name = 'Супер Администратор'
        verbose_name_plural = 'Супер Администраторы'

    def __str__(self):
        return f"{self.username or 'SuperAdmin'}"





class UserChannelSubscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Активна'),
        ('inactive', 'Неактивна'),
    ]

    class Meta:
        db_table = 'user_channel_subscriptions'
        verbose_name = 'Подписка на канал'
        verbose_name_plural = 'Подписки на каналы'
        unique_together = ['user', 'channel']
        indexes = [
            models.Index(fields=['subscription_status']),
            models.Index(fields=['subscribed_at']),
        ]

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='channel_subscriptions',
        help_text='Пользователь'
    )
    channel = models.ForeignKey(
        'platforms.TelegramChannel',
        to_field='group_id',
        db_column='channel_id',
        on_delete=models.CASCADE,
        related_name='user_subscriptions',
        help_text='Канал или группа'
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='inactive',
        help_text='Статус подписки'
    )
    subscribed_at = models.DateTimeField(
        null=True,
        help_text='Дата подписки'
    )
    unsubscribed_at = models.DateTimeField(
        null=True,
        help_text='Дата отписки'
    )

    def __str__(self):
        return f"Подписка {self.user} на {self.channel} ({self.subscription_status})"

    def subscribe(self):
        """Активировать подписку"""
        self.subscription_status = 'active'
        self.subscribed_at = timezone.now()
        self.unsubscribed_at = None
        self.save()

    def unsubscribe(self):
        """Деактивировать подписку"""
        self.subscription_status = 'inactive'
        self.unsubscribed_at = timezone.now()
        self.save()


class Profile(models.Model):
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='profile',
        primary_key=True  # Делаем user_id первичным ключом
    )
    avatar = models.ImageField(upload_to='avatar/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    website = models.URLField(max_length=200, blank=True)
    
    # Социальные сети
    telegram = models.CharField(max_length=100, blank=True)  # Оставляем только одно поле для телеграма
    github = models.URLField(blank=True, verbose_name='GitHub Profile')
    instagram = models.URLField(blank=True, verbose_name='Instagram Profile')
    facebook = models.URLField(blank=True, verbose_name='Facebook Profile')
    linkedin = models.URLField(blank=True, verbose_name='LinkedIn Profile')
    youtube = models.URLField(blank=True, verbose_name='YouTube Channel')
    
    # Статистика
    total_points = models.IntegerField(default=0)
    quizzes_completed = models.IntegerField(default=0)
    average_score = models.FloatField(default=0.0)
    favorite_category = models.CharField(max_length=100, blank=True)
    
    # Дополнительные поля для телеграм пользователей
    is_telegram_user = models.BooleanField(default=False)
    
    # Настройки
    email_notifications = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    theme_preference = models.CharField(
        max_length=20,
        choices=[('light', 'Light'), ('dark', 'Dark')],
        default='dark'
    )
    
    last_seen = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f'Профиль пользователя {self.user.username}'

    @property
    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return '/static/blog/images/avatar/default_avatar.png'

    @property
    def is_online(self):
        return timezone.now() - self.last_seen < timedelta(minutes=5)

    @property
    def member_since(self):
        return self.user.date_joined

    @property
    def favorite_topics(self):
        from tasks.models import TaskStatistics
        return TaskStatistics.objects.filter(user=self.user)\
            .values('task__topic__name')\
            .annotate(count=models.Count('id'))\
            .order_by('-count')[:3]

# Сигналы
@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    if not hasattr(instance, 'profile'):
        Profile.objects.create(user=instance)
    instance.profile.save()



@receiver(post_save, sender='tasks.TaskStatistics')
def clear_user_statistics_cache(sender, instance, **kwargs):
    """Очистка кэша при сохранении статистики"""
    cache_key = f'user_statistics_{instance.user_id}'
    cache.delete(cache_key)


