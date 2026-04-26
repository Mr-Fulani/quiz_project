import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db.models import Count, Q
import logging
from django.db.models.functions import TruncDate
from django.core.validators import FileExtensionValidator
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import mimetypes
import os

logger = logging.getLogger(__name__)


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
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='tasks',
        null=True,
        blank=True,
        verbose_name=_('Тенант'),
        help_text=_('Тенант, которому принадлежит эта задача')
    )
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
    group = models.ForeignKey(
        'platforms.TelegramGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks',
        db_column='group_id',
        help_text='Связанная группа/канал'
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
        auto_now_add=True,
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
    video_url = models.URLField(
        max_length=255,
        null=True,
        blank=True,
        help_text='URL видео задачи (для совместимости, основное видео)'
    )
    video_urls = models.JSONField(
        default=dict,
        blank=True,
        help_text='URL видео по языкам: {"ru": "url1", "en": "url2"}'
    )
    # Позволяет привязать конкретную фон. музыку к задаче (переопределяет автоматический выбор)
    background_music = models.ForeignKey(
        'BackgroundMusic',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tasks',
        help_text='Выбрать фоновую музыку для этой задачи (переопределяет автоматический выбор)'
    )
    video_generation_progress = models.JSONField(
        default=dict,
        blank=True,
        help_text='Прогресс генерации видео: {"ru": true, "en": false}'
    )
    video_question_texts = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text='Кастомный текст вопроса для видео по языкам: {"ru": "Ваш текст", "en": "Your text"}. Если не указан, используется дефолтный текст.'
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
    description = models.TextField(
        null=True,
        blank=True,
        help_text='Описание задачи (из JSON)'
    )
    video_generation_logs = models.TextField(
        null=True,
        blank=True,
        help_text='Логи процесса генерации видео (обновляется автоматически)'
    )

    # ── Статусы публикации по платформам ───────────────────────────────────
    published_telegram = models.BooleanField(
        default=False,
        verbose_name=_('Опубликовано в Telegram'),
        help_text=_('Задача опубликована в Telegram-канале/группе')
    )
    published_website = models.BooleanField(
        default=False,
        verbose_name=_('Опубликовано на сайте'),
        help_text=_('Задача доступна на сайте')
    )
    published_mini_app = models.BooleanField(
        default=False,
        verbose_name=_('Опубликовано в Mini App'),
        help_text=_('Задача доступна в Telegram Mini App')
    )


    def clean(self):
        super().clean()
        if self.publish_date and self.publish_date < self.create_date:
            raise ValidationError("Дата публикации не может быть раньше даты создания")
            
        # Проверка соответствия темы группы и темы задачи
        if self.group and self.topic:
            if self.group.topic_id != self.topic:
                raise ValidationError({
                    'group': f"Telegram-канал '{self.group.group_name}' привязан к теме '{self.group.topic_id.name}', "
                             f"а задача имеет тему '{self.topic.name}'. Темы должны совпадать."
                })

    def save(self, *args, **kwargs):
        if self.published and not self.publish_date:
            self.publish_date = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Задача {self.id} ({self.get_difficulty_display()})"
    
    def delete_with_related(self):
        """
        Удаляет задачу вместе со всеми связанными задачами по translation_group_id
        и их изображениями из S3.
        
        Использует сигналы для автоматической очистки.
        """
        # Сигналы автоматически обработают удаление связанных задач и изображений
        self.delete()
    
    def publish_to_telegram(self):
        """
        Публикует задачу в Telegram канал.
        
        Returns:
            dict: Результаты публикации
        """
        from tasks.services.telegram_service import publish_task_to_telegram
        
        if not self.image_url:
            return {'success': False, 'errors': ['Отсутствует изображение']}
        
        # Получаем первый перевод
        translation = self.translations.first()
        if not translation:
            return {'success': False, 'errors': ['Отсутствуют переводы']}
        
        # Получаем группу
        if not self.group:
            return {'success': False, 'errors': ['Не указана группа для публикации']}
        
        result = publish_task_to_telegram(
            task=self,
            translation=translation,
            telegram_group=self.group,
            external_link=self.external_link
        )
        
        if result['success']:
            self.published = True
            self.published_telegram = True
            self.save(update_fields=['published', 'published_telegram'])
        
        return result


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
        help_text='Объяснение ответа (короткое, до 200 символов для Telegram)'
    )
    long_explanation = models.TextField(
        null=True,
        blank=True,
        help_text='Подробное пошаговое объяснение для сайта'
    )
    source_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='Название источника объяснения (например, Wikipedia)'
    )
    source_link = models.TextField(
        null=True,
        blank=True,
        help_text='Ссылка(и) на источник объяснения. Для нескольких ссылок используйте разделитель ";"'
    )
    publish_date = models.DateTimeField(
        null=True, blank=True)

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
        'tasks.Task',
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
    selected_answer = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Статистика: Задача {self.task_id}, Пользователь {self.user_id}"




    @classmethod
    def get_stats_for_mini_app(cls, user):
        """
        Возвращает полную статистику для профиля пользователя в мини-приложении.
        """
        try:
            # Основная статистика пользователя
            user_stats = cls.objects.filter(user=user).aggregate(
                total_attempts=Count('id'),
                successful_attempts=Count('id', filter=Q(successful=True)),
                rating=Count('id')
            )
            
            success_rate = (
                round((user_stats['successful_attempts'] / user_stats['total_attempts']) * 100, 1)
                if user_stats['total_attempts'] > 0 else 0
            )
            
            # Прогресс по темам (топ 5)
            topic_progress = []
            user_category_stats = cls.objects.filter(user=user).values(
                'task__topic__name',
                'task__topic__id'
            ).annotate(
                completed=Count('id', filter=Q(successful=True)),
                total=Count('id')
            ).order_by('-total')[:5]
            
            for stat in user_category_stats:
                topic_name = stat['task__topic__name'] or 'Unknown'
                completed = stat['completed']
                total = stat['total']
                percentage = round((completed / total * 100), 0) if total > 0 else 0
                
                topic_progress.append({
                    'name': topic_name,
                    'completed': completed,
                    'total': total,
                    'percentage': percentage
                })
            
            # Подсчет очков
            total_points = user_stats['successful_attempts'] * 10
            
            # Серия (streak)
            recent_attempts = cls.objects.filter(user=user).order_by('-last_attempt_date')[:10]
            current_streak = 0
            best_streak = 0
            temp_streak = 0
            
            for attempt in recent_attempts:
                if attempt.successful:
                    temp_streak += 1
                    if current_streak == 0:
                        current_streak = temp_streak
                else:
                    if temp_streak > best_streak:
                        best_streak = temp_streak
                    temp_streak = 0
            
            if temp_streak > best_streak:
                best_streak = temp_streak
                
            # Информация о пользователе
            user_info = {
                'telegram_id': getattr(user, 'telegram_id', None) or user.id,
                'username': user.username,
                'first_name': user.first_name or user.username,
                'last_name': user.last_name or '',
                'avatar_url': None
            }
            
            # Моковые достижения
            achievements = [
                {'id': 1, 'name': 'Первый шаг', 'icon': '🏆', 'unlocked': user_stats['total_attempts'] > 0},
                {'id': 2, 'name': 'Знаток Python', 'icon': '🐍', 'unlocked': success_rate > 60},
                {'id': 3, 'name': 'Веб-мастер', 'icon': '🌐', 'unlocked': False},
                {'id': 4, 'name': 'Серия', 'icon': '🔥', 'unlocked': current_streak >= 3},
                {'id': 5, 'name': 'Эксперт', 'icon': '⭐', 'unlocked': success_rate > 90},
                {'id': 6, 'name': 'Скорость', 'icon': '⚡', 'unlocked': False}
            ]
            
            return {
                'user': user_info,
                'stats': {
                    'total_quizzes': user_stats['total_attempts'],
                    'completed_quizzes': user_stats['successful_attempts'],
                    'success_rate': int(success_rate),
                    'total_points': total_points,
                    'current_streak': current_streak,
                    'best_streak': best_streak
                },
                'topic_progress': topic_progress,
                'achievements': achievements
            }
            
        except Exception as e:
            logger.error(f"Ошибка в get_stats_for_mini_app для пользователя {user.id}: {e}")
            return {'error': 'Не удалось сгенерировать статистику'}

    @classmethod
    def get_stats_for_dashboard(cls, user):
        """
        Возвращает статистику для веб-профиля (dashboard).
        """
        try:
            # Общая статистика попыток
            stats = cls.objects.filter(user=user).aggregate(
                total_attempts=Count('id'),
                successful_attempts=Count('id', filter=Q(successful=True))
            )
            stats['success_rate'] = round(
                (stats['successful_attempts'] / stats['total_attempts']) * 100, 1
            ) if stats['total_attempts'] > 0 else 0

            # Статистика активности для графика
            activity_stats = cls.objects.filter(
                user=user,
                last_attempt_date__isnull=False
            ).annotate(
                date=TruncDate('last_attempt_date')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')

            activity_dates = [stat['date'].strftime('%d.%m') for stat in activity_stats] or ['No data']
            activity_data = [stat['count'] for stat in activity_stats] or [0]
            
            # Статистика по категориям для графика
            category_stats = cls.objects.filter(user=user).values(
                'task__topic__name'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            categories_labels = [stat['task__topic__name'] if stat['task__topic__name'] else 'Unknown' for stat in category_stats] or ['No data']
            categories_data = [stat['count'] for stat in category_stats] or [0]

            # Распределение попыток
            attempts = cls.objects.filter(user=user).values('attempts').annotate(count=Count('id'))
            attempts_distribution = [0] * 5
            for attempt in attempts:
                attempts_value = int(attempt['attempts']) if attempt['attempts'] is not None else 0
                if attempts_value > 0:
                    bin_index = min((attempts_value - 1) // 5, 4)
                    attempts_distribution[bin_index] += attempt['count']
                elif attempts_value == 0:
                    attempts_distribution[0] += attempt['count']
            
            return {
                'stats': stats,
                'activity_dates': activity_dates,
                'activity_data': activity_data,
                'has_activity_data': len(activity_data) > 1 or (len(activity_data) == 1 and activity_data[0] != 0),
                'categories_labels': categories_labels,
                'categories_data': categories_data,
                'has_categories_data': len(categories_data) > 1 or (len(categories_data) == 1 and categories_data[0] != 0),
                'attempts_distribution': attempts_distribution,
                'has_attempts_data': any(attempts_distribution),
            }
        except Exception as e:
            logger.error(f"Ошибка в get_stats_for_dashboard для пользователя {user.id}: {e}")
            return {}

    @classmethod
    def get_user_statistics(cls, user):
        """Получение полной статистики пользователя"""
        # Считаем уникальные translation_group_id вместо количества записей
        # чтобы не учитывать дубликаты от синхронизации статистики между языками
        total_attempts = cls.objects.filter(user=user).values('task__translation_group_id').distinct().count()
        successful_attempts = cls.objects.filter(user=user, successful=True).values('task__translation_group_id').distinct().count()
        
        stats = {
            'total_attempts': total_attempts,
            'successful_attempts': successful_attempts,
            
            # Статистика по сложности
            'difficulty_stats': cls.get_difficulty_stats(user),
            
            # Статистика по темам
            'topic_stats': cls.get_topic_stats(user),
            
            # Активность по дням
            'activity_stats': cls.get_activity_stats(user),
            
            # Любимая категория
            'favorite_topic': cls.get_favorite_topic(user),
        }
        
        # Вычисляем процент успешности
        if stats['total_attempts'] > 0:
            stats['success_rate'] = (stats['successful_attempts'] / stats['total_attempts']) * 100
        else:
            stats['success_rate'] = 0
            
        return stats

    @classmethod
    def get_difficulty_stats(cls, user):
        """Статистика по уровням сложности"""
        return cls.objects.filter(user=user).values(
            'task__difficulty'
        ).annotate(
            total=models.Count('id'),
            successful=models.Count('id', filter=models.Q(successful=True)),
            success_rate=models.ExpressionWrapper(
                models.F('successful') * 100.0 / models.F('total'),
                output_field=models.FloatField()
            )
        ).order_by('task__difficulty')

    @classmethod
    def get_topic_stats(cls, user):
        """Статистика по темам"""
        return cls.objects.filter(user=user).values(
            'task__topic__name'
        ).annotate(
            total=models.Count('id'),
            successful=models.Count('id', filter=models.Q(successful=True)),
            success_rate=models.ExpressionWrapper(
                models.F('successful') * 100.0 / models.F('total'),
                output_field=models.FloatField()
            )
        ).order_by('-total')

    @classmethod
    def get_global_topic_stats(cls, limit=10):
        """
        Получает глобальную статистику по популярным темам на основе количества попыток всех пользователей.
        Возвращает топ тем с процентом популярности.
        """
        from django.db.models import Count, Q
        
        # Получаем статистику по темам для всех пользователей
        topic_stats = cls.objects.values('task__topic__name').annotate(
            total_attempts=Count('id'),
            successful_attempts=Count('id', filter=Q(successful=True)),
            unique_users=Count('user', distinct=True)
        ).filter(
            task__topic__isnull=False
        ).order_by('-total_attempts')[:limit]
        
        # Вычисляем максимальное количество попыток для нормализации процентов
        max_attempts = topic_stats[0]['total_attempts'] if topic_stats else 0
        
        # Добавляем процент популярности
        for stat in topic_stats:
            if max_attempts > 0:
                stat['popularity_percentage'] = round((stat['total_attempts'] / max_attempts) * 100)
            else:
                stat['popularity_percentage'] = 0
            stat['name'] = stat['task__topic__name']
        
        return topic_stats

    @classmethod
    def get_activity_stats(cls, user):
        """Статистика активности по дням"""
        last_30_days = timezone.now() - timezone.timedelta(days=30)
        return cls.objects.filter(
            user=user,
            attempt_date__gte=last_30_days
        ).annotate(
            date=models.functions.TruncDate('attempt_date')
        ).values('date').annotate(
            attempts=models.Count('id'),
            successful=models.Count('id', filter=models.Q(successful=True))
        ).order_by('date')

    @classmethod
    def get_favorite_topic(cls, user):
        """Определение любимой темы пользователя"""
        return cls.objects.filter(
            user=user,
            successful=True
        ).values(
            'task__topic__name'
        ).annotate(
            count=models.Count('id')
        ).order_by('-count').first()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Очищаем кэш статистики пользователя
        from django.core.cache import cache
        from django.utils.translation import get_language
        cache_key = f'user_stats_{self.user_id}'
        cache.delete(cache_key)
        # Также вызываем метод инвалидации кэша у пользователя
        if self.user:
            self.user.invalidate_statistics_cache()
        
        # Инвалидируем кэш прогресса для тем, подтем и уровней сложности
        # Инвалидируем для всех языков, чтобы кэш обновлялся независимо от текущего языка
        if self.user and self.task:
            from django.conf import settings
            languages = [lang[0] for lang in getattr(settings, 'LANGUAGES', [('en', 'English'), ('ru', 'Russian')])]
            
            # Инвалидация кэша для тем (для всех языков)
            if hasattr(self.task, 'topic') and self.task.topic:
                for lang in languages:
                    topic_cache_key = f'topics_progress_{self.task.topic.id}_{self.user.id}_{lang}'
                    cache.delete(topic_cache_key)
            
            # Инвалидация кэша для подтем (для всех языков)
            if hasattr(self.task, 'subtopic') and self.task.subtopic:
                for lang in languages:
                    subtopic_cache_key = f'subtopics_progress_{self.task.subtopic.id}_{self.user.id}_{lang}'
                    cache.delete(subtopic_cache_key)
                    
                    # Инвалидация кэша для уровней сложности (для всех языков)
                    if hasattr(self.task, 'difficulty') and self.task.difficulty:
                        difficulty_cache_key = f'difficulties_progress_{self.task.subtopic.id}_{self.user.id}_{lang}'
                        cache.delete(difficulty_cache_key)


class MiniAppTaskStatistics(models.Model):
    """
    Статистика решения задач пользователями Mini App.
    
    Отдельная модель для хранения статистики из мини-аппа,
    которая может быть связана с основной статистикой при объединении пользователей.
    """
    class Meta:
        db_table = 'mini_app_task_statistics'
        verbose_name = 'Статистика Mini App'
        verbose_name_plural = 'Статистика Mini App'
        indexes = [
            models.Index(fields=['last_attempt_date']),
        ]
        unique_together = ('mini_app_user', 'task')

    id = models.AutoField(primary_key=True)
    mini_app_user = models.ForeignKey(
        'accounts.MiniAppUser',
        on_delete=models.CASCADE,
        related_name='task_statistics',
        help_text='Пользователь Mini App'
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='mini_app_statistics',
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
    selected_answer = models.CharField(max_length=255, blank=True, null=True)
    
    # Связь с основной статистикой (если пользователь объединен)
    linked_statistics = models.OneToOneField(
        'TaskStatistics',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mini_app_statistics_link',
        help_text='Связь с основной статистикой после объединения пользователей'
    )

    def __str__(self):
        return f"Mini App Статистика: Задача {self.task_id}, Пользователь {self.mini_app_user.telegram_id}"

    def merge_to_main_statistics(self, custom_user):
        """
        Объединяет статистику мини-аппа с основной статистикой пользователя.
        
        Args:
            custom_user: Объект CustomUser для объединения
        """
        from django.db import transaction
        
        with transaction.atomic():
            # Получаем или создаем основную статистику
            main_stats, created = TaskStatistics.objects.get_or_create(
                user=custom_user,
                task=self.task,
                defaults={
                    'attempts': self.attempts,
                    'successful': self.successful,
                    'selected_answer': self.selected_answer
                }
            )
            
            if not created:
                # Если статистика уже существует, объединяем данные
                main_stats.attempts += self.attempts
                # Если в мини-аппе задача была решена успешно, отмечаем как успешную
                if self.successful:
                    main_stats.successful = True
                # Обновляем последнюю попытку, если она новее
                if self.last_attempt_date > main_stats.last_attempt_date:
                    main_stats.last_attempt_date = self.last_attempt_date
                main_stats.save()
            
            # Связываем статистики
            self.linked_statistics = main_stats
            self.save()
            
            return main_stats


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


class TaskComment(models.Model):
    """
    Модель комментария к переводу задачи.
    Поддерживает древовидную структуру (комментарии и ответы на них).
    """
    class Meta:
        db_table = 'task_comments'
        verbose_name = 'Комментарий к задаче'
        verbose_name_plural = 'Комментарии к задачам'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task_translation', 'parent_comment']),
            models.Index(fields=['author_telegram_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_deleted']),
        ]

    id = models.AutoField(primary_key=True)
    task_translation = models.ForeignKey(
        TaskTranslation,
        on_delete=models.CASCADE,
        related_name='comments',
        help_text='Перевод задачи, к которому относится комментарий'
    )
    author_telegram_id = models.BigIntegerField(
        help_text='Telegram ID автора комментария'
    )
    author_username = models.CharField(
        max_length=255,
        help_text='Имя пользователя для отображения'
    )
    text = models.TextField(
        help_text='Текст комментария'
    )
    parent_comment = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        help_text='Родительский комментарий для древовидной структуры'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Дата и время создания комментария'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='Дата и время последнего обновления'
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text='Мягкое удаление комментария'
    )
    reports_count = models.IntegerField(
        default=0,
        help_text='Количество жалоб на комментарий'
    )

    def __str__(self):
        return f"Комментарий {self.id} от {self.author_username}"
    
    def get_replies_count(self):
        """Возвращает количество ответов на комментарий"""
        return self.replies.filter(is_deleted=False).count()
    
    def get_depth(self):
        """Возвращает глубину вложенности комментария"""
        depth = 0
        current = self.parent_comment
        while current is not None:
            depth += 1
            current = current.parent_comment
        return depth


class TaskCommentImage(models.Model):
    """
    Модель для хранения изображений, прикрепленных к комментариям.
    """
    class Meta:
        db_table = 'task_comment_images'
        verbose_name = 'Изображение комментария'
        verbose_name_plural = 'Изображения комментариев'
        ordering = ['id']

    id = models.AutoField(primary_key=True)
    comment = models.ForeignKey(
        TaskComment,
        on_delete=models.CASCADE,
        related_name='images',
        help_text='Комментарий, к которому относится изображение'
    )
    image = models.ImageField(
        upload_to='task_comments/',
        help_text='Изображение комментария'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Дата и время загрузки изображения'
    )

    def __str__(self):
        return f"Изображение для комментария {self.comment_id}"


class TaskCommentReport(models.Model):
    """
    Модель для хранения жалоб на комментарии.
    Используется для модерации контента.
    """
    
    REASON_CHOICES = [
        ('spam', 'Спам'),
        ('offensive', 'Оскорбительный контент'),
        ('inappropriate', 'Неуместный контент'),
        ('other', 'Другое'),
    ]
    
    class Meta:
        db_table = 'task_comment_reports'
        verbose_name = 'Жалоба на комментарий'
        verbose_name_plural = 'Жалобы на комментарии'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['comment', 'is_reviewed']),
            models.Index(fields=['reporter_telegram_id']),
            models.Index(fields=['created_at']),
        ]
        unique_together = ('comment', 'reporter_telegram_id')  # Один пользователь - одна жалоба

    id = models.AutoField(primary_key=True)
    comment = models.ForeignKey(
        TaskComment,
        on_delete=models.CASCADE,
        related_name='reports',
        help_text='Комментарий, на который подана жалоба'
    )
    reporter_telegram_id = models.BigIntegerField(
        help_text='Telegram ID пользователя, подавшего жалобу'
    )
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        help_text='Причина жалобы'
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text='Дополнительное описание жалобы'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Дата и время подачи жалобы'
    )
    is_reviewed = models.BooleanField(
        default=False,
        help_text='Проверена ли жалоба модератором'
    )

    def __str__(self):
        return f"Жалоба на комментарий {self.comment_id} от пользователя {self.reporter_telegram_id}"
    
    def save(self, *args, **kwargs):
        """При сохранении жалобы увеличиваем счётчик в комментарии"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Увеличиваем счётчик жалоб
            self.comment.reports_count = self.comment.reports.count()
            self.comment.save(update_fields=['reports_count'])


class SocialMediaPost(models.Model):
    """
    Отслеживание публикаций задач в социальных сетях.
    Поддерживает как прямую интеграцию через API, так и webhook.
    """
    
    PLATFORM_CHOICES = [
        ('pinterest', 'Pinterest'),
        ('instagram', 'Instagram'),
        ('tiktok', 'TikTok'),
        ('yandex_dzen', 'Яндекс Дзен'),
        ('youtube_shorts', 'YouTube Shorts'),
        ('facebook', 'Facebook'),
    ]
    
    METHOD_CHOICES = [
        ('api', 'Прямое API'),
        ('webhook', 'Webhook'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('processing', 'Обрабатывается'),
        ('published', 'Опубликовано'),
        ('failed', 'Ошибка'),
    ]
    
    class Meta:
        db_table = 'social_media_posts'
        verbose_name = 'Публикация в соцсетях'
        verbose_name_plural = 'Публикации в соцсетях'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', 'platform']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
        unique_together = [('task', 'platform')]

    id = models.AutoField(primary_key=True)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='social_media_posts',
        help_text='Связанная задача'
    )
    platform = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES,
        help_text='Платформа социальной сети'
    )
    method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES,
        default='api',
        help_text='Метод публикации (API или webhook)'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text='Статус публикации'
    )
    post_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='ID поста в соцсети'
    )
    post_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text='Ссылка на пост'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Дата создания записи'
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Дата фактической публикации'
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text='Сообщение об ошибке'
    )
    retry_count = models.IntegerField(
        default=0,
        help_text='Количество попыток публикации'
    )

    def __str__(self):
        return f"{self.get_platform_display()} - Задача {self.task_id} ({self.get_status_display()})"


class BackgroundMusic(models.Model):
    """Фоновая музыка для видео.

    Поддерживаемая загрузка через стандартный FileField. Модель хранит метаданные
    (размер, длительность в секундах) и флаг активности для выбора в генераторе видео.
    """

    class Meta:
        db_table = 'background_music'
        verbose_name = 'Фоновая музыка'
        verbose_name_plural = 'Фоновая музыка'
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['name']),
        ]

    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Тенант')
    name = models.CharField(max_length=255, help_text='Название трека')
    audio_file = models.FileField(
        upload_to='background_music/',
        validators=[FileExtensionValidator(allowed_extensions=['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac'])],
        help_text='Аудиофайл (поддерживается: mp3, wav, m4a, aac, ogg, flac)'
    )
    size = models.BigIntegerField(null=True, blank=True, help_text='Размер файла в байтах')
    content_type = models.CharField(max_length=100, blank=True, null=True)
    duration_seconds = models.IntegerField(null=True, blank=True, help_text='Длительность в секундах (вычисляется автоматически если возможно)')
    is_active = models.BooleanField(default=True, help_text='Включен ли трек для автоматического выбора')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.id})"

    def clean(self):
        # Проверка размера
        max_bytes = getattr(settings, 'BG_MUSIC_MAX_BYTES', 50 * 1024 * 1024)  # 50MB по умолчанию
        try:
            f = self.audio_file
            if f and hasattr(f, 'size') and f.size is not None:
                if f.size > max_bytes:
                    raise ValidationError({'audio_file': f'Максимальный размер файла — {max_bytes} байт'})
        except Exception:
            # Если файл недоступен на этапе валидации — пропускаем проверку размера
            pass

        # Проверка расширения (FileExtensionValidator уже делает часть работы)
        if self.audio_file:
            ext = os.path.splitext(self.audio_file.name)[1].lower().lstrip('.')
            allowed = ['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac']
            if ext not in allowed:
                raise ValidationError({'audio_file': 'Неподдерживаемый формат файла'})

    def save(self, *args, **kwargs):
        # При сохранении заполняем размер и content_type, пытаемся вычислить длительность
        try:
            f = self.audio_file
            if f and hasattr(f, 'size'):
                self.size = f.size
            if f and hasattr(f, 'name'):
                ctype, _ = mimetypes.guess_type(f.name)
                self.content_type = ctype or ''

            # Сохраняем сначала, чтобы файл был доступен в storage
            super().save(*args, **kwargs)

            # Попытка вычислить длительность через mutagen/pydub
            try:
                from mutagen import File as MutagenFile
                mf = MutagenFile(self.audio_file.path if hasattr(self.audio_file, 'path') else self.audio_file.file)
                if mf is not None and hasattr(mf, 'info') and getattr(mf.info, 'length', None) is not None:
                    self.duration_seconds = int(getattr(mf.info, 'length'))
                    # Обновляем только поле длительности
                    BackgroundMusic.objects.filter(pk=self.pk).update(duration_seconds=self.duration_seconds)
            except Exception:
                # Если mutagen недоступен или не смог прочитать, игнорируем — длительность может быть заполнена позже
                pass

        except Exception:
            # На случай неожиданных ошибок — всё равно вызываем базовый save(), чтобы не сломать поток
            super().save(*args, **kwargs)
