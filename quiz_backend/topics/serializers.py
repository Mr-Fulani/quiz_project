from rest_framework import serializers
from .models import Topic, Subtopic
from .utils import normalize_subtopic_name
from tasks.models import Task
import random


def get_request_language(context, default='en'):
    request = context.get('request')
    if not request:
        return default
    return request.query_params.get('language', default)


def get_subtopic_description(obj, language):
    description = obj.get_localized_description(language)
    if description:
        return description
    prefix = 'Подтема' if language == 'ru' else 'Subtopic'
    return f'{prefix}: {obj.get_localized_name(language)}'


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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = get_request_language(self.context)
        data['name'] = instance.get_localized_name(language)
        return data

    def validate_name(self, value):
        """
        Нормализует имя подтемы перед сохранением.
        """
        return normalize_subtopic_name(value)


class SubtopicWithTasksSerializer(serializers.ModelSerializer):
    """
    Сериализатор для подтем с количеством задач (для мини-приложения).
    """
    name = serializers.SerializerMethodField()
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

    def get_name(self, obj):
        language = get_request_language(self.context)
        return obj.get_localized_name(language)

    def get_questions_count(self, obj):
        language = get_request_language(self.context)
        from django.db.models import Q
        return obj.tasks.filter(
            Q(published=True) | Q(published_mini_app=True),
            translations__language=language
        ).distinct().count()

    def get_topic_id(self, obj):
        return obj.topic.id

    def get_description(self, obj):
        language = get_request_language(self.context)
        return get_subtopic_description(obj, language)

    def get_difficulty_counts(self, obj):
        """Возвращает количество задач по уровням сложности на активном языке."""
        language = get_request_language(self.context)
        from django.db.models import Q
        qs = obj.tasks.filter(Q(published=True) | Q(published_mini_app=True), translations__language=language)
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
        language = get_request_language(self.context)
        telegram_id = None
        if request:
            telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return {'easy': 0, 'medium': 0, 'hard': 0}

        from django.db.models import Q
        base_qs = Task.objects.filter(
            subtopic=obj,
            translations__language=language
        ).filter(
            Q(published=True) | Q(published_mini_app=True)
        ).filter(
            mini_app_statistics__mini_app_user__telegram_id=telegram_id,
            mini_app_statistics__successful=True
        ).values('translation_group_id', 'difficulty').distinct()

        easy = base_qs.filter(difficulty='easy').count()
        medium = base_qs.filter(difficulty='medium').count()
        hard = base_qs.filter(difficulty='hard').count()
        return {'easy': easy, 'medium': medium, 'hard': hard}

    def get_is_completed(self, obj):
        """Определяет, пройдена ли подтема (все задачи решены)."""
        difficulty_counts = self.get_difficulty_counts(obj)
        solved_counts = self.get_solved_counts(obj)

        total_tasks = difficulty_counts['easy'] + difficulty_counts['medium'] + difficulty_counts['hard']
        total_solved = solved_counts['easy'] + solved_counts['medium'] + solved_counts['hard']

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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = get_request_language(self.context)
        data['name'] = instance.get_localized_name(language)
        data['description'] = instance.get_localized_description(language)
        return data

    def get_subtopics_count(self, obj):
        return obj.subtopics.count()


class TopicMiniAppSerializer(serializers.ModelSerializer):
    """
    Сериализатор для тем в мини-приложении с дополнительными полями для UI.
    """
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
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

    def get_name(self, obj):
        language = get_request_language(self.context)
        return obj.get_localized_name(language)

    def get_description(self, obj):
        language = get_request_language(self.context)
        description = obj.get_localized_description(language)
        return description or obj.description

    def get_subtopics_count(self, obj):
        return obj.subtopics.count()

    def get_difficulty(self, obj):
        difficulties = ['Легкий', 'Средний', 'Сложный']
        random.seed(obj.id)
        return random.choice(difficulties)

    def get_questions_count(self, obj):
        language = get_request_language(self.context)
        from django.db.models import Q
        return obj.tasks.filter(
            Q(published=True) | Q(published_mini_app=True),
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

        if obj.media_type == 'default':
            return f"https://picsum.photos/800/800?{obj.id}"

        if obj.media_type == 'image' and obj.card_image:
            return f"{settings.MEDIA_URL}{obj.card_image.name}"

        if obj.media_type == 'video' and obj.card_video:
            return f"{settings.MEDIA_URL}{obj.card_video.name}"

        return f"https://picsum.photos/800/800?{obj.id}"

    def get_video_poster_url(self, obj):
        """
        Возвращает URL постера для видео (если есть)
        """
        from django.conf import settings

        if obj.media_type == 'video' and obj.video_poster:
            return f"{settings.MEDIA_URL}{obj.video_poster.name}"

        return None
