from django.contrib import admin
from django import forms
from .models import TelegramGroup
from topics.models import Topic
import re


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
    username = forms.CharField(
        max_length=32,
        required=False,
        help_text='Username должен содержать 5-32 символа, только латинские буквы, цифры и нижнее подчеркивание. Без "@".',
        widget=forms.TextInput(attrs={'placeholder': 'channel_name'})
    )

    class Meta:
        model = TelegramGroup
        fields = ['group_name', 'group_id', 'language', 'location_type', 'username', 'topic', 'new_topic_name']

    def __init__(self, *args, **kwargs):
        """
        Инициализация формы: устанавливаем текущий topic_id как начальное значение для topic
        и добавляем дополнительную стилизацию для поля username.
        """
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:  # Проверяем только сохранённые объекты
            self.fields['topic'].initial = self.instance.topic_id

        # Добавляем класс для стилизации поля username
        self.fields['username'].widget.attrs.update({
            'class': 'username-field',
            'style': 'width: 300px;',
        })

    def clean(self):
        """
        Проверка: должна быть выбрана либо существующая тема, либо введена новая.
        """
        cleaned_data = super().clean()
        topic = cleaned_data.get('topic')
        new_topic_name = cleaned_data.get('new_topic_name')
        if not topic and not new_topic_name:
            raise forms.ValidationError('Выберите тему или введите название новой темы.')
        if topic and new_topic_name:
            raise forms.ValidationError('Выберите только одну опцию: существующую тему или новую.')
        return cleaned_data

    def clean_group_id(self):
        """
        Проверка: group_id должен начинаться с -100 и содержать только цифры.
        """
        group_id = self.cleaned_data['group_id']
        if not str(group_id).startswith('-100') or not str(group_id)[4:].isdigit():
            raise forms.ValidationError('Telegram ID должен начинаться с -100 и содержать только цифры.')
        return group_id

    def clean_username(self):
        """
        Проверка корректности формата username.

        Returns:
            str: Проверенный username или None если поле пустое.

        Raises:
            ValidationError: Если формат username некорректный
        """
        username = self.cleaned_data.get('username')

        # Если поле пустое, считаем это допустимым (None)
        if not username or username.strip() == '':
            return None

        # Если username начинается с @, удаляем этот символ
        if username.startswith('@'):
            username = username[1:]

        # Проверяем формат (длина 5-32, только буквы, цифры и _)
        if not re.match(r'^[A-Za-z0-9_]{5,32}$', username):
            errors = []

            if len(username) < 5 or len(username) > 32:
                errors.append(f"Длина username должна быть от 5 до 32 символов (сейчас {len(username)})")

            if not re.match(r'^[A-Za-z0-9_]*$', username):
                invalid_chars = [char for char in username if not re.match(r'[A-Za-z0-9_]', char)]
                errors.append(f"Недопустимые символы: {', '.join(invalid_chars)}")

            raise forms.ValidationError([
                "Некорректный формат username:",
                *errors,
                "Используйте только латинские буквы, цифры и нижнее подчеркивание."
            ])

        return username


@admin.register(TelegramGroup)
class TelegramChannelAdmin(admin.ModelAdmin):
    """
    Админка для модели TelegramGroup.
    """
    form = TelegramChannelAdminForm
    list_display = ('group_name', 'group_id', 'language', 'location_type', 'username', 'get_topic_name')
    list_filter = ('language', 'location_type')
    search_fields = ('group_name', 'group_id', 'username')
    ordering = ('-id',)

    # Скрываем поле id
    exclude = ('id',)

    # Поля в форме
    fields = ('group_name', 'group_id', 'topic', 'new_topic_name', 'language', 'location_type', 'username')

    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

    def get_topic_name(self, obj):
        """
        Возвращает название связанной темы для отображения в списке.

        Args:
            obj (TelegramGroup): Объект TelegramGroup.

        Returns:
            str: Название темы или '—' если тема не указана.
        """
        return obj.topic_id.name if obj.topic_id else '—'

    get_topic_name.short_description = 'Тема'

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
        obj.topic_id = topic  # Присваиваем объект Topic, как ожидает ForeignKey
        super().save_model(request, obj, form, change)