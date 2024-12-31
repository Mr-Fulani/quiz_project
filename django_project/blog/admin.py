from django.contrib import admin
from .models import (
    Admin,
    Task,
    TaskTranslation,
    User,
    TaskStatistics,
    Group,
    Topic,
    Subtopic,
    UserChannelSubscription,
    Webhook
)


# Регистрация всех моделей
@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'username')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'topic', 'difficulty', 'published', 'create_date', 'publish_date')


@admin.register(TaskTranslation)
class TaskTranslationAdmin(admin.ModelAdmin):
    list_display = ('id', 'task', 'language', 'question', 'correct_answer')


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'username', 'subscription_status', 'created_at', 'language')


@admin.register(TaskStatistics)
class TaskStatisticsAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'task', 'attempts', 'successful', 'last_attempt_date')


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('group_name', 'group_id', 'topic', 'language', 'location_type')


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')


@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'topic')


@admin.register(UserChannelSubscription)
class UserChannelSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'channel', 'subscription_status', 'subscribed_at', 'unsubscribed_at')


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ('id', 'url', 'service_name', 'is_active', 'created_at', 'updated_at')

