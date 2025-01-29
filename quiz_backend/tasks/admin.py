from django.contrib import admin
from .models import Task, TaskTranslation, TaskStatistics, TaskPoll

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
    Админка для управления задачами
    """
    list_display = ('id', 'topic', 'subtopic', 'difficulty', 'published', 'create_date', 'publish_date')
    list_filter = ('published', 'difficulty', 'topic', 'subtopic', 'error')
    search_fields = ('id', 'topic__name', 'subtopic__name')
    raw_id_fields = ('topic', 'subtopic', 'group')
    date_hierarchy = 'create_date'
    ordering = ('-create_date',)

@admin.register(TaskTranslation)
class TaskTranslationAdmin(admin.ModelAdmin):
    """
    Админка для переводов задач
    """
    list_display = ('id', 'task', 'language', 'question')
    list_filter = ('language',)
    search_fields = ('question', 'correct_answer', 'task__id')
    raw_id_fields = ('task',)

@admin.register(TaskStatistics)
class TaskStatisticsAdmin(admin.ModelAdmin):
    """
    Админка для статистики решения задач
    """
    list_display = ('user', 'task', 'attempts', 'successful', 'last_attempt_date')
    list_filter = ('successful',)
    search_fields = ('user__username', 'task__id')
    raw_id_fields = ('user', 'task')
    date_hierarchy = 'last_attempt_date'

@admin.register(TaskPoll)
class TaskPollAdmin(admin.ModelAdmin):
    """
    Админка для опросов задач
    """
    list_display = ('task', 'poll_id', 'is_anonymous', 'total_voter_count')
    list_filter = ('is_anonymous', 'allows_multiple_answers')
    search_fields = ('poll_id', 'task__id', 'poll_question')
    raw_id_fields = ('task', 'translation')
