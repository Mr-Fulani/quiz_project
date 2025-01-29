from django.contrib import admin
from .models import TelegramChannel




@admin.register(TelegramChannel)
class TelegramChannelAdmin(admin.ModelAdmin):
    """
    Админка для модели TelegramChannel
    """
    list_display = ('group_name', 'group_id', 'language', 'location_type', 'username', 'topic_id')
    list_filter = ('language', 'location_type')
    search_fields = ('group_name', 'group_id', 'username')
    ordering = ('-id',)