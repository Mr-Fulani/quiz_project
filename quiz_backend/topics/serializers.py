from rest_framework import serializers
from .models import Topic, Subtopic
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

    class Meta:
        model = Subtopic
        fields = [
            'id', 
            'name',
            'description',
            'questions_count',
            'topic_id'
        ]

    def get_questions_count(self, obj):
        # Подсчитываем количество задач для подтемы с переводами на русском (пока hardcode)
        # TODO: добавить поддержку динамического языка из запроса
        language = 'ru'
        return obj.tasks.filter(
            published=True,
            translations__language=language
        ).distinct().count()
    
    def get_topic_id(self, obj):
        return obj.topic.id
    
    def get_description(self, obj):
        return f'Подтема: {obj.name}'

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
        # Временно генерируем случайное количество вопросов
        # TODO: подсчитывать реальное количество вопросов из связанных моделей
        random.seed(obj.id * 2)  # Фиксированное количество для каждой темы
        return random.randint(15, 35)
    
    def get_image_url(self, obj):
        # Используем иконку темы или fallback на случайное изображение
        if obj.icon and obj.icon != '/static/blog/images/icons/default-icon.png':
            return obj.icon
        else:
            # Fallback на красивые изображения
            return f"https://picsum.photos/400/400?{obj.id}" 