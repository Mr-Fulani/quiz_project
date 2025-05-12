# from django.db import models
# from django.contrib.auth.models import AbstractUser, Group, Permission
# from django.conf import settings
# from django.utils import timezone
#
# class TelegramAdmin(models.Model):
#     """
#     Модель администратора Telegram-бота, синхронизированная с SQLAlchemy.
#     """
#     telegram_id = models.BigIntegerField(
#         unique=True, null=False, db_index=True, verbose_name="Telegram ID"
#     )
#     username = models.CharField(
#         max_length=255, null=True, blank=True, verbose_name="Username"
#     )
#     language = models.CharField(
#         max_length=10, default='ru', null=True, verbose_name="Язык"
#     )
#     is_active = models.BooleanField(
#         default=True, verbose_name="Активен"
#     )
#     photo = models.CharField(
#         max_length=500, null=True, blank=True, verbose_name="Фото"
#     )
#     groups = models.ManyToManyField(
#         'platforms.TelegramGroup',
#         related_name='telegram_admins',
#         blank=True,
#         verbose_name='Telegram Группа/Канал',
#         through='TelegramAdminGroup',
#     )
#
#     class Meta:
#         db_table = 'telegram_admins'
#         verbose_name = 'Telegram Администратор'
#         verbose_name_plural = 'Telegram Администраторы'
#
#     def __str__(self):
#         """Строковое представление."""
#         return f"{self.username or 'Admin'} (Telegram ID: {self.telegram_id})"
#
# class TelegramAdminGroup(models.Model):
#     """
#     Промежуточная модель для связи TelegramAdmin и TelegramGroup.
#     """
#     telegram_admin = models.ForeignKey(
#         'TelegramAdmin',
#         on_delete=models.CASCADE,
#         related_name='admin_groups'
#     )
#     telegram_group = models.ForeignKey(
#         'platforms.TelegramGroup',
#         to_field='group_id',
#         on_delete=models.CASCADE,
#         related_name='group_admins'
#     )
#
#     class Meta:
#         db_table = 'telegramadmin_groups'
#         unique_together = ('telegram_admin', 'telegram_group')
#         verbose_name = 'Связь Telegram Администратора и Группы'
#         verbose_name_plural = 'Связи Telegram Администраторов и Групп'
#
# class TelegramUser(models.Model):
#     """
#     Модель пользователя Telegram-бота с премиум-статусом.
#     """
#     STATUS_CHOICES = [
#         ('active', 'Активна'),
#         ('inactive', 'Неактивна'),
#     ]
#
#     telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
#     username = models.CharField(max_length=255, blank=True, null=True, verbose_name="@username")
#     first_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Имя")
#     last_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Фамилия")
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
#     subscription_status = models.CharField(
#         max_length=20, choices=STATUS_CHOICES, default='inactive', verbose_name="Статус подписки"
#     )
#     language = models.CharField(max_length=10, blank=True, null=True, verbose_name="Язык")
#     deactivated_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата деактивации")
#     is_premium = models.BooleanField(default=False, verbose_name="Премиум аккаунт")
#     linked_user = models.OneToOneField(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         help_text="Связанный пользователь сайта.",
#         verbose_name="Связанный пользователь"
#     )
#
#     class Meta:
#         db_table = 'telegram_users'
#         verbose_name = 'Telegram Пользователь'
#         verbose_name_plural = 'Telegram Пользователи'
#
#     def __str__(self):
#         """Строковое представление."""
#         return self.username or f"TelegramUser {self.telegram_id}"
#
# # Оставляем CustomUser, DjangoAdmin, UserChannelSubscription без изменений
# class CustomUser(AbstractUser):
#     """Кастомная модель пользователя."""
#     subscription_status = models.CharField(max_length=20, default='inactive', verbose_name="Статус подписки")
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
#     language = models.CharField(max_length=10, blank=True, null=True, verbose_name="Язык")
#     deactivated_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата деактивации")
#     telegram_id = models.BigIntegerField(blank=True, null=True, verbose_name="Telegram ID")
#     avatar = models.ImageField(upload_to='avatar/', blank=True, null=True, verbose_name="Аватар")
#     bio = models.TextField(max_length=500, blank=True, verbose_name="Биография")
#     location = models.CharField(max_length=100, blank=True, verbose_name="Местоположение")
#     birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
#     website = models.URLField(max_length=200, blank=True, verbose_name="Веб-сайт")
#     telegram = models.CharField(max_length=100, blank=True, verbose_name="Telegram")
#     github = models.URLField(blank=True, verbose_name="GitHub")
#     instagram = models.URLField(blank=True, verbose_name="Instagram")
#     facebook = models.URLField(blank=True, verbose_name="Facebook")
#     linkedin = models.URLField(blank=True, verbose_name="LinkedIn")
#     youtube = models.URLField(blank=True, verbose_name="YouTube")
#     total_points = models.IntegerField(default=0, verbose_name="Всего баллов")
#     quizzes_completed = models.IntegerField(default=0, verbose_name="Завершено квизов")
#     average_score = models.FloatField(default=0.0, verbose_name="Средний балл")
#     favorite_category = models.CharField(max_length=100, blank=True, verbose_name="Любимая категория")
#     is_telegram_user = models.BooleanField(default=False, verbose_name="Пользователь Telegram")
#     email_notifications = models.BooleanField(default=True, verbose_name="Уведомления по email")
#     is_public = models.BooleanField(default=True, verbose_name="Публичный профиль")
#     theme_preference = models.CharField(
#         max_length=20, choices=[('light', 'Light'), ('dark', 'Dark')], default='dark', verbose_name="Тема интерфейса"
#     )
#     last_seen = models.DateTimeField(default=timezone.now, verbose_name="Последний визит")
#
#     class Meta:
#         db_table = 'users'
#         verbose_name = 'Пользователь'
#         verbose_name_plural = 'Пользователи'
#
#     def __str__(self):
#         """Строковое представление."""
#         return f"{self.username or 'User'}"
#
# class DjangoAdmin(AbstractUser):
#     """
#     Модель администратора Django-админки.
#     """
#     phone_number = models.CharField(max_length=15, null=True, blank=True, verbose_name="Номер телефона")
#     language = models.CharField(max_length=10, default='ru', verbose_name="Язык")
#     is_django_admin = models.BooleanField(default=True, verbose_name="Django Admin")
#
#     class Meta:
#         db_table = 'django_admins'
#         verbose_name = 'Django Администратор'
#         verbose_name_plural = 'Django Администраторы'
#
#     def __str__(self):
#         """Строковое представление."""
#         return f"{self.username or 'DjangoAdmin'}"
#
# class UserChannelSubscription(models.Model):
#     """Модель подписки пользователя на Telegram-канал."""
#     STATUS_CHOICES = [('active', 'Активна'), ('inactive', 'Неактивна')]
#
#     id = models.AutoField(primary_key=True)
#     user = models.ForeignKey(
#         'accounts.CustomUser', on_delete=models.CASCADE, related_name='channel_subscriptions', verbose_name="Пользователь сайта"
#     )
#     telegram_user = models.ForeignKey(
#         'accounts.TelegramUser', on_delete=models.CASCADE, related_name='channel_subscriptions', verbose_name="Telegram пользователь", null=True, blank=True
#     )
#     channel = models.ForeignKey(
#         'platforms.TelegramGroup', to_field='group_id', db_column='channel_id', on_delete=models.CASCADE, related_name='channel_subscriptions', verbose_name="Группа/Канал"
#     )
#     subscription_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive', verbose_name="Статус подписки")
#     subscribed_at = models.DateTimeField(null=True, verbose_name="Дата подписки")
#     unsubscribed_at = models.DateTimeField(null=True, verbose_name="Дата отписки")
#
#     class Meta:
#         db_table = 'user_channel_subscriptions'
#         verbose_name = 'Подписка на канал'
#         verbose_name_plural = 'Подписки на каналы'
#         constraints = [models.UniqueConstraint(fields=['user', 'channel'], name='unique_user_channel')]
#         indexes = [models.Index(fields=['subscription_status']), models.Index(fields=['subscribed_at'])]
#
#     def __str__(self):
#         """Строковое представление."""
#         return f"Подписка {self.user} на {self.channel} ({self.subscription_status})"