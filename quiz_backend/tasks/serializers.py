from rest_framework import serializers
from .models import Task, TaskStatistics, TaskTranslation
from topics.serializers import TopicSerializer, SubtopicSerializer

class TaskTranslationSerializer(serializers.ModelSerializer):
    """Сериализатор для переводов задач."""
    class Meta:
        model = TaskTranslation
        fields = ['id', 'language', 'question', 'answers', 'correct_answer', 'explanation']

class TaskSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Task.
    """
    topic = serializers.PrimaryKeyRelatedField(read_only=True)
    subtopic = serializers.PrimaryKeyRelatedField(read_only=True)
    topic_id = serializers.IntegerField(write_only=True)
    subtopic_id = serializers.IntegerField(write_only=True)
    success_rate = serializers.FloatField(read_only=True)
    translations = TaskTranslationSerializer(many=True)
    is_solved = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id',
            'topic',
            'subtopic',
            'difficulty',
            'published',
            'create_date',
            'publish_date',
            'image_url',
            'external_link',
            'translations',
            'error',
            'message_id',
            'group',
            'topic_id',
            'subtopic_id',
            'success_rate',
            'is_solved'
        ]
        read_only_fields = ['id', 'topic', 'subtopic', 'create_date', 'publish_date', 'success_rate']

    def get_is_solved(self, obj):
        """Проверяет, решена ли задача текущим пользователем."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return TaskStatistics.objects.filter(
                user=request.user,
                task=obj,
                successful=True
            ).exists()
        return False

    def to_representation(self, instance):
        """
        Преобразование объекта в словарь для ответа API.
        """
        data = super().to_representation(instance)
        stats = TaskStatistics.objects.filter(task=instance)
        total = stats.count()
        if total > 0:
            successful = stats.filter(successful=True).count()
            data['success_rate'] = (successful / total) * 100
        else:
            data['success_rate'] = 0
        
        # Добавляем translation_id для системы комментариев
        if instance.translations.exists():
            translation = instance.translations.first()
            data['translation_id'] = translation.id
        
        return data

    def create(self, validated_data):
        translations_data = validated_data.pop('translations')
        task = Task.objects.create(**validated_data)
        for translation_data in translations_data:
            TaskTranslation.objects.create(task=task, **translation_data)
        return task

class TaskStatisticsSerializer(serializers.ModelSerializer):
    """
    Сериализатор для статистики задач.
    """
    task = TaskSerializer(read_only=True)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = TaskStatistics
        fields = [
            'id',
            'user',
            'task',
            'attempts'
        ]
        read_only_fields = ('id',)

class TaskSubmitSerializer(serializers.Serializer):
    """
    Сериализатор для отправки ответа на задачу.
    """
    answer = serializers.CharField(max_length=255)
    time_spent = serializers.IntegerField(min_value=0)

class TaskSkipSerializer(serializers.Serializer):
    """
    Сериализатор для пропуска задачи.
    """
    time_spent = serializers.IntegerField(min_value=0)

class TaskStatsResponseSerializer(serializers.Serializer):
    """
    Сериализатор для ответа со статистикой.
    """
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    success_rate = serializers.FloatField()
    average_time = serializers.FloatField()
    total_points = serializers.IntegerField()