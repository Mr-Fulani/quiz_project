from rest_framework import serializers
from .models import Topic, Subtopic
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

class SubtopicWithTasksSerializer(serializers.ModelSerializer):
    """
    Сериализатор для подтем с количеством задач (для мини-приложения).
    """
    questions_count = serializers.SerializerMethodField()
    topic_id = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    difficulty_counts = serializers.SerializerMethodField()
    solved_counts = serializers.SerializerMethodField()

    class Meta:
        model = Subtopic
        fields = [
            'id', 
            'name',
            'description',
            'questions_count',
            'topic_id',
            'difficulty_counts',
            'solved_counts'
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
        """Количество решённых (имеющих запись статистики mini_app) задач по уровням сложности для конкретного пользователя Telegram."""
        request = self.context.get('request')
        language = 'en'
        telegram_id = None
        if request:
            language = request.query_params.get('language', 'en')
            telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return {'easy': 0, 'medium': 0, 'hard': 0}

        base_qs = Task.objects.filter(
            subtopic=obj,
            published=True,
            translations__language=language,
            mini_app_statistics__mini_app_user__telegram_id=telegram_id
        ).values('id', 'difficulty').distinct()

        # Подсчёт по уровням
        easy = base_qs.filter(difficulty='easy').count()
        medium = base_qs.filter(difficulty='medium').count()
        hard = base_qs.filter(difficulty='hard').count()
        return {'easy': easy, 'medium': medium, 'hard': hard}

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
            'image_url'
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
        # Используем иконку темы или fallback на случайное изображение
        if obj.icon and obj.icon != '/static/blog/images/icons/default-icon.png':
            return obj.icon
        else:
            # Fallback на красивые изображения
            return f"https://picsum.photos/400/400?{obj.id}" 