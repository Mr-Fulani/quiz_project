from rest_framework import serializers
from .models import Topic, Subtopic
from .utils import normalize_subtopic_name
from tasks.models import MiniAppTaskStatistics, Task
import random

class SubtopicSerializer(serializers.ModelSerializer):
    """
    Сериализатор для подтем.
    """
    class Meta:
        model = Subtopic
        fields = [
            'id', 
            'name',
            'topic'
        ]

    def validate_name(self, value):
        """
        Нормализует имя подтемы перед сохранением.
        """
        return normalize_subtopic_name(value)

class SubtopicWithTasksSerializer(serializers.ModelSerializer):
    """
    Сериализатор для подтем с количеством задач (для мини-приложения).
    """
    questions_count = serializers.SerializerMethodField()
    topic_id = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    difficulty_counts = serializers.SerializerMethodField()
    solved_counts = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = Subtopic
        fields = [
            'id', 
            'name',
            'description',
            'questions_count',
            'topic_id',
            'difficulty_counts',
            'solved_counts',
            'is_completed'
        ]

    def get_questions_count(self, obj):
        # Получаем язык из контекста запроса
        request = self.context.get('request')
        language = 'en'  # По умолчанию английский
        
        if request:
            language = request.query_params.get('language', 'en')
        
        return obj.tasks.filter(
            published=True,
            translations__language=language
        ).distinct().count()
    
    def get_topic_id(self, obj):
        return obj.topic.id
    
    def get_description(self, obj):
        return f'Подтема: {obj.name}'

    def get_difficulty_counts(self, obj):
        """Возвращает количество задач по уровням сложности на активном языке."""
        request = self.context.get('request')
        language = 'en'
        if request:
            language = request.query_params.get('language', 'en')
        qs = obj.tasks.filter(published=True, translations__language=language)
        return {
            'easy': qs.filter(difficulty='easy').values('id').distinct().count(),
            'medium': qs.filter(difficulty='medium').values('id').distinct().count(),
            'hard': qs.filter(difficulty='hard').values('id').distinct().count(),
        }

    def get_solved_counts(self, obj):
        """Количество решённых (имеющих запись статистики mini_app) задач по уровням сложности для конкретного пользователя Telegram.
        Группирует по translation_group_id, чтобы учитывать задачи на всех языках как одну.
        """
        request = self.context.get('request')
        language = 'en'
        telegram_id = None
        if request:
            language = request.query_params.get('language', 'en')
            telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return {'easy': 0, 'medium': 0, 'hard': 0}

        # Получаем задачи с попытками, группируя по translation_group_id
        base_qs = Task.objects.filter(
            subtopic=obj,
            published=True,
            translations__language=language,
            mini_app_statistics__mini_app_user__telegram_id=telegram_id
        ).values('translation_group_id', 'difficulty').distinct()

        # Подсчёт по уровням (уникальные translation_group_id)
        easy = base_qs.filter(difficulty='easy').count()
        medium = base_qs.filter(difficulty='medium').count()
        hard = base_qs.filter(difficulty='hard').count()
        return {'easy': easy, 'medium': medium, 'hard': hard}

    def get_is_completed(self, obj):
        """Определяет, пройдена ли подтема (все задачи решены)."""
        difficulty_counts = self.get_difficulty_counts(obj)
        solved_counts = self.get_solved_counts(obj)
        
        # Подтема считается пройденной, если все задачи решены
        total_tasks = difficulty_counts['easy'] + difficulty_counts['medium'] + difficulty_counts['hard']
        total_solved = solved_counts['easy'] + solved_counts['medium'] + solved_counts['hard']
        
        # Если нет задач, считаем непройденной
        if total_tasks == 0:
            return False
        
        return total_solved >= total_tasks

class TopicSerializer(serializers.ModelSerializer):
    """
    Сериализатор для тем с вложенными подтемами.
    """
    subtopics = SubtopicSerializer(many=True, read_only=True)
    subtopics_count = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = [
            'id',
            'name',
            'description',
            'icon',
            'subtopics',
            'subtopics_count'
        ]
        read_only_fields = ['id']

    def get_subtopics_count(self, obj):
        return obj.subtopics.count()

class TopicMiniAppSerializer(serializers.ModelSerializer):
    """
    Сериализатор для тем в мини-приложении с дополнительными полями для UI.
    """
    subtopics_count = serializers.SerializerMethodField()
    difficulty = serializers.SerializerMethodField()
    questions_count = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    video_poster_url = serializers.SerializerMethodField()
    media_type = serializers.CharField()

    class Meta:
        model = Topic
        fields = [
            'id',
            'name',
            'description',
            'icon',
            'difficulty',
            'questions_count',
            'subtopics_count',
            'image_url',
            'video_poster_url',
            'media_type'
        ]

    def get_subtopics_count(self, obj):
        return obj.subtopics.count()
    
    def get_difficulty(self, obj):
        # Временно генерируем случайную сложность
        # TODO: добавить поле difficulty в модель Topic
        difficulties = ['Легкий', 'Средний', 'Сложный']
        random.seed(obj.id)  # Фиксированная сложность для каждой темы
        return random.choice(difficulties)
    
    def get_questions_count(self, obj):
        # Получаем язык из контекста запроса
        request = self.context.get('request')
        language = 'en'  # По умолчанию английский
        
        if request:
            language = request.query_params.get('language', 'en')
        
        # Подсчитываем реальное количество задач с переводами на указанном языке
        return obj.tasks.filter(
            published=True,
            translations__language=language
        ).distinct().count()
    
    def get_image_url(self, obj):
        """
        Возвращает URL медиа для карточки темы с учетом приоритета:
        1. Загруженное изображение (если media_type='image')
        2. Загруженное видео (если media_type='video')
        3. Иконка темы (если не default)
        4. Fallback на picsum.photos
        """
        from django.conf import settings
        
        # Для типа "По умолчанию" всегда используем picsum.photos
        if obj.media_type == 'default':
            return f"https://picsum.photos/800/800?{obj.id}"
        
        # Приоритет 1: Загруженное изображение
        if obj.media_type == 'image' and obj.card_image:
            return f"{settings.MEDIA_URL}{obj.card_image.name}"
        
        # Приоритет 2: Загруженное видео
        if obj.media_type == 'video' and obj.card_video:
            return f"{settings.MEDIA_URL}{obj.card_video.name}"
        
        # Fallback на красивые изображения (увеличено для Retina-дисплеев)
        return f"https://picsum.photos/800/800?{obj.id}"
    
    def get_video_poster_url(self, obj):
        """
        Возвращает URL постера для видео (если есть)
        """
        from django.conf import settings
        
        if obj.media_type == 'video' and obj.video_poster:
            return f"{settings.MEDIA_URL}{obj.video_poster.name}"
        
        return None 