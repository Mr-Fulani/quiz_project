from django.contrib import admin
from .models import Task, TaskTranslation, TaskStatistics, Topic, Subtopic

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'topic', 'difficulty', 'published', 'create_date')
    list_filter = ('published', 'difficulty')
    search_fields = ('topic__name', 'difficulty')

@admin.register(TaskTranslation)
class TaskTranslationAdmin(admin.ModelAdmin):
    list_display = ('id', 'task', 'language', 'question')
    search_fields = ('task__id', 'language')

@admin.register(TaskStatistics)
class TaskStatisticsAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'task', 'attempts', 'successful')
    list_filter = ('successful',)
    search_fields = ('user__id', 'task__id')

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name',)

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'topic')
    search_fields = ('name', 'topic__name')