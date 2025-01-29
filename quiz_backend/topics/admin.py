from django.contrib import admin
from .models import Topic, Subtopic

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    """
    Админка для управления темами
    """
    list_display = ('id', 'name', 'description')
    search_fields = ('name', 'description')
    ordering = ('name',)

    def get_subtopics_count(self, obj):
        """Получить количество подтем"""
        return obj.subtopics.count()
    get_subtopics_count.short_description = 'Количество подтем'

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    """
    Админка для управления подтемами
    """
    list_display = ('id', 'name', 'topic')
    list_filter = ('topic',)
    search_fields = ('name', 'topic__name')
    raw_id_fields = ('topic',)
    ordering = ('topic', 'name')

    def get_tasks_count(self, obj):
        """Получить количество задач в подтеме"""
        return obj.tasks.count()
    get_tasks_count.short_description = 'Количество задач'
