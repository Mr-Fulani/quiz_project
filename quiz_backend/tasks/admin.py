from django.contrib import admin
from .models import Task, TaskTranslation, TaskStatistics, TaskPoll


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
    Админка для управления задачами.
    """
    list_display = ('id', 'topic', 'subtopic', 'difficulty', 'published', 'create_date', 'publish_date')
    list_filter = ('published', 'difficulty', 'topic', 'subtopic', 'error')
    search_fields = ('id', 'topic__name', 'subtopic__name')
    raw_id_fields = ('topic', 'subtopic', 'group')  # Для удобства выбора связанных объектов
    date_hierarchy = 'create_date'
    ordering = ('-create_date',)
    list_per_page = 20  # Ограничение записей на странице для удобства


@admin.register(TaskTranslation)
class TaskTranslationAdmin(admin.ModelAdmin):
    """
    Админка для переводов задач.
    """
    list_display = ('id', 'task', 'language', 'question_preview')  # Добавим укороченный вопрос
    list_filter = ('language',)
    search_fields = ('question', 'correct_answer', 'task__id')
    raw_id_fields = ('task',)
    list_per_page = 20

    def question_preview(self, obj):
        """Отображает первые 50 символов вопроса."""
        return obj.question[:50] + ('...' if len(obj.question) > 50 else '')
    question_preview.short_description = 'Вопрос (превью)'


@admin.register(TaskStatistics)
class TaskStatisticsAdmin(admin.ModelAdmin):
    """
    Админка для статистики решения задач.
    """
    list_display = ('user', 'task', 'attempts', 'successful', 'last_attempt_date')
    list_filter = ('successful',)
    search_fields = ('user__username', 'task__id')
    raw_id_fields = ('user', 'task')
    date_hierarchy = 'last_attempt_date'
    list_per_page = 20


@admin.register(TaskPoll)
class TaskPollAdmin(admin.ModelAdmin):
    """
    Админка для опросов задач.
    """
    list_display = ('task', 'poll_id', 'is_anonymous', 'total_voter_count', 'poll_question_preview')
    list_filter = ('is_anonymous', 'allows_multiple_answers')
    search_fields = ('poll_id', 'task__id', 'poll_question')
    raw_id_fields = ('task', 'translation')
    list_per_page = 20

    def poll_question_preview(self, obj):
        """Отображает первые 50 символов вопроса опроса."""
        return obj.poll_question[:50] + ('...' if len(obj.poll_question) > 50 else '')
    poll_question_preview.short_description = 'Вопрос опроса (превью)'