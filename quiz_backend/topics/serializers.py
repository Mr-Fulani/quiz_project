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


DIFFICULTIES = ('easy', 'medium', 'hard')


def build_subtopic_stats(subtopic_ids, language, telegram_id=None, tenant=None):
    """
    Статистика задач для набора подтем тремя агрегатными запросами (вместо ~13 запросов
    на каждую подтему): всего задач, задач по сложности и решённых пользователем по сложности.

    Решённые считаются по translation_group_id (одна задача на разных языках — одна),
    пользователь ищется в тенанте запроса.

    Returns:
        dict: {subtopic_id: {'questions_count': int, 'difficulty_counts': {...}, 'solved_counts': {...}}}
    """
    from django.db.models import Count, Q

    stats = {
        subtopic_id: {
            'questions_count': 0,
            'difficulty_counts': dict.fromkeys(DIFFICULTIES, 0),
            'solved_counts': dict.fromkeys(DIFFICULTIES, 0),
        }
        for subtopic_id in subtopic_ids
    }
    if not stats:
        return stats

    tasks = Task.objects.filter(
        Q(published=True) | Q(published_mini_app=True),
        subtopic_id__in=list(stats),
        translations__language=language,
    )

    for row in tasks.values('subtopic_id').annotate(total=Count('id', distinct=True)):
        stats[row['subtopic_id']]['questions_count'] = row['total']

    for row in tasks.filter(difficulty__in=DIFFICULTIES).values('subtopic_id', 'difficulty').annotate(
        total=Count('id', distinct=True)
    ):
        stats[row['subtopic_id']]['difficulty_counts'][row['difficulty']] = row['total']

    if telegram_id:
        solved_filter = Q(
            mini_app_statistics__mini_app_user__telegram_id=telegram_id,
            mini_app_statistics__successful=True,
        )
        if tenant is not None:
            solved_filter &= Q(mini_app_statistics__mini_app_user__tenant=tenant)
        solved_rows = tasks.filter(solved_filter, difficulty__in=DIFFICULTIES).values(
            'subtopic_id', 'difficulty'
        ).annotate(
            groups=Count('translation_group_id', distinct=True),
            # Задачи без группы переводов считаются по одной
            ungrouped=Count('id', filter=Q(translation_group_id__isnull=True), distinct=True),
        )
        for row in solved_rows:
            stats[row['subtopic_id']]['solved_counts'][row['difficulty']] = row['groups'] + row['ungrouped']

    return stats


class SubtopicWithTasksSerializer(serializers.ModelSerializer):
    """
    Сериализатор для подтем с количеством задач (для мини-приложения).

    Статистику задач берёт из context['subtopic_stats'] (build_subtopic_stats для всего списка);
    без неё считает для одной подтемы.
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

    def _stats(self, obj):
        stats = self.context.get('subtopic_stats')
        if stats is None or obj.id not in stats:
            request = self.context.get('request')
            stats = build_subtopic_stats(
                [obj.id],
                get_request_language(self.context),
                telegram_id=request.query_params.get('telegram_id') if request else None,
                tenant=getattr(request, 'tenant', None) if request else None,
            )
            self.context.setdefault('subtopic_stats', {}).update(stats)
        return stats[obj.id]

    def get_questions_count(self, obj):
        return self._stats(obj)['questions_count']

    def get_topic_id(self, obj):
        return obj.topic_id

    def get_description(self, obj):
        language = get_request_language(self.context)
        return get_subtopic_description(obj, language)

    def get_difficulty_counts(self, obj):
        """Возвращает количество задач по уровням сложности на активном языке."""
        return self._stats(obj)['difficulty_counts']

    def get_solved_counts(self, obj):
        """Количество решённых задач по уровням сложности для пользователя Telegram
        (по translation_group_id — задачи на всех языках считаются как одна)."""
        return self._stats(obj)['solved_counts']

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
