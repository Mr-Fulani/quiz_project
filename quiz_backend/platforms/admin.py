from django.contrib import admin
from django import forms
from .models import TelegramGroup
from topics.models import Topic


class TelegramChannelAdminForm(forms.ModelForm):
    """
    Кастомная форма для админки TelegramGroup с выбором или созданием темы.
    """
    topic = forms.ModelChoiceField(
        queryset=Topic.objects.all(),
        label='Тема',
        required=False,
        help_text='Выберите существующую тему (например, Python, Golang)'
    )
    new_topic_name = forms.CharField(
        label='Новая тема',
        max_length=255,
        required=False,
        help_text='Введите название новой темы, если не выбрана существующая'
    )

    class Meta:
        model = TelegramGroup
        fields = ['group_name', 'group_id', 'language', 'location_type', 'username', 'topic', 'new_topic_name']

    def __init__(self, *args, **kwargs):
        """
        Инициализация формы: устанавливаем текущий topic_id как начальное значение для topic.
        """
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.topic_id:  # Если редактируем существующий объект
            self.fields['topic'].initial = self.instance.topic_id

    def clean(self):
        cleaned_data = super().clean()
        topic = cleaned_data.get('topic')
        new_topic_name = cleaned_data.get('new_topic_name')
        if not topic and not new_topic_name:
            raise forms.ValidationError('Выберите тему или введите название новой темы.')
        if topic and new_topic_name:
            raise forms.ValidationError('Выберите только одну опцию: существующую тему или новую.')
        return cleaned_data

    def clean_group_id(self):
        group_id = self.cleaned_data['group_id']
        if not str(group_id).startswith('-100') or not str(group_id)[4:].isdigit():
            raise forms.ValidationError('Telegram ID должен начинаться с -100 и содержать только цифры.')
        return group_id


@admin.register(TelegramGroup)
class TelegramChannelAdmin(admin.ModelAdmin):
    """
    Админка для модели TelegramGroup.
    """
    form = TelegramChannelAdminForm
    list_display = ('group_name', 'group_id', 'language', 'location_type', 'username', 'topic_id')
    list_filter = ('language', 'location_type')
    search_fields = ('group_name', 'group_id', 'username')
    ordering = ('-id',)

    # Скрываем поле id
    exclude = ('id',)

    # Поля в форме
    fields = ('group_name', 'group_id', 'topic', 'new_topic_name', 'language', 'location_type', 'username')

    def save_model(self, request, obj, form, change):
        """
        Логика сохранения: используем topic из формы или создаём новую тему.
        """
        topic = form.cleaned_data['topic']
        new_topic_name = form.cleaned_data['new_topic_name']
        if new_topic_name:
            topic, created = Topic.objects.get_or_create(
                name=new_topic_name,
                defaults={'name': new_topic_name}
            )
        obj.topic_id = topic
        super().save_model(request, obj, form, change)