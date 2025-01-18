from django.contrib import admin
from .models import User, Group, UserChannelSubscription, Admin


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'telegram_id', 'username', 'subscription_status', 'created_at')
    list_filter = ('subscription_status',)
    search_fields = ('telegram_id', 'username')

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'group_name', 'group_id', 'language', 'location_type')
    list_filter = ('location_type', 'language')
    search_fields = ('group_name', 'group_id')

@admin.register(UserChannelSubscription)
class UserChannelSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'channel', 'subscription_status')
    list_filter = ('subscription_status',)
    search_fields = ('user__telegram_id', 'channel__group_name')


@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    list_display = ('id', 'telegram_id', 'username')  # Поля для отображения в списке
    search_fields = ('telegram_id', 'username')  # Поля для поиска
