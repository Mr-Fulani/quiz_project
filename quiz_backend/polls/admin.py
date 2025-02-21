from django.contrib import admin
from .models import Poll, Choice, UserResponse


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    """
    Класс для управления моделью Poll в админке.

    Определяет, как опросы отображаются, фильтруются и ищутся в интерфейсе администратора.
    """
    list_display = ('question', 'created_at', 'author')  # Используем имена полей модели
    list_filter = ('created_at',)  # Фильтр по дате создания
    search_fields = ('question',)  # Поиск по вопросу


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    """
    Класс для управления моделью Choice в админке.

    Определяет, как варианты ответа отображаются, фильтруются и ищутся в интерфейсе администратора.
    """
    list_display = ('text', 'poll', 'is_correct', 'votes')  # Используем имена полей модели
    list_filter = ('poll', 'is_correct')  # Фильтры по опросу и правильности
    search_fields = ('text',)  # Поиск по тексту варианта


@admin.register(UserResponse)
class UserResponseAdmin(admin.ModelAdmin):
    """
    Класс для управления моделью UserResponse в админке.

    Определяет, как ответы пользователей отображаются, фильтруются и ищутся в интерфейсе администратора.
    """
    list_display = ('poll', 'choice', 'user', 'responded_at')  # Используем имена полей модели
    list_filter = ('poll', 'responded_at')  # Фильтры по опросу и дате ответа
    search_fields = ('user__username',)  # Поиск по имени пользователя