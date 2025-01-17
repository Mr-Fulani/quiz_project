from django.contrib import admin
from .models import FeedbackMessage

@admin.register(FeedbackMessage)
class FeedbackMessageAdmin(admin.ModelAdmin):
    """
    Админка для модели FeedbackMessage.
    """
    list_display = ('user_id', 'username', 'created_at', 'is_processed')
    list_filter = ('is_processed', 'created_at')
    search_fields = ('username', 'message')