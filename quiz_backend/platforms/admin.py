from django.contrib import admin
from django.core.exceptions import ValidationError
from django import forms
from .models import TelegramGroup
from topics.models import Topic


class TelegramChannelAdminForm(forms.ModelForm):
    """
    Кастомная форма для админки TelegramChannel, добавляем поле topic_name.
    """
    topic_name = forms.CharField(
        label='Название темы',
        max_length=255,
        required=True,
        help_text='Введите название темы (например, "Python", "Golang")'
    )

    class Meta:
        model = TelegramGroup
        fields = ['group_name', 'group_id', 'language', 'location_type', 'username', 'topic_name']

    def clean_group_id(self):
        group_id = self.cleaned_data['group_id']
        if not str(group_id).startswith('-100') or not str(group_id)[4:].isdigit():
            raise ValidationError('Telegram ID должен начинаться с -100 и содержать только цифры.')
        return group_id


@admin.register(TelegramGroup)
class TelegramChannelAdmin(admin.ModelAdmin):
    """
    Админка для модели TelegramChannel.
    """
    form = TelegramChannelAdminForm
    list_display = ('group_name', 'group_id', 'language', 'location_type', 'username', 'topic_id')
    list_filter = ('language', 'location_type')
    search_fields = ('group_name', 'group_id', 'username')
    ordering = ('-id',)

    # Скрываем поля id и topic_id
    exclude = ('id', 'topic_id')

    # Поля в форме
    fields = ('group_name', 'group_id', 'topic_name', 'language', 'location_type', 'username')

    def save_model(self, request, obj, form, change):
        """
        Логика сохранения: ищем или создаём тему по topic_name и задаём topic_id.
        """
        if not change:  # Только для новых объектов
            topic_name = form.cleaned_data['topic_name']
            # Ищем или создаём тему
            topic, created = Topic.objects.get_or_create(
                name=topic_name,
                defaults={'name': topic_name}
            )
            obj.topic_id = topic.id
        super().save_model(request, obj, form, change)