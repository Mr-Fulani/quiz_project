from django.contrib import admin
from .models import FeedbackMessage

@admin.register(FeedbackMessage)
class FeedbackMessageAdmin(admin.ModelAdmin):
    """
    Админка для управления сообщениями обратной связи
    """
    list_display = ('id', 'user_id', 'username', 'short_message', 'created_at', 'is_processed')
    list_filter = ('is_processed', 'created_at')
    search_fields = ('user_id', 'username', 'message')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    def short_message(self, obj):
        """Сокращенная версия сообщения для отображения в списке"""
        return (obj.message[:50] + '...') if len(obj.message) > 50 else obj.message
    short_message.short_description = 'Сообщение'

    actions = ['mark_as_processed', 'mark_as_unprocessed']

    def mark_as_processed(self, request, queryset):
        """Отметить выбранные сообщения как обработанные"""
        queryset.update(is_processed=True)
    mark_as_processed.short_description = 'Отметить как обработанные'

    def mark_as_unprocessed(self, request, queryset):
        """Отметить выбранные сообщения как необработанные"""
        queryset.update(is_processed=False)
    mark_as_unprocessed.short_description = 'Отметить как необработанные'
