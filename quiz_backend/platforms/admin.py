from django.contrib import admin
from django import forms
from django.http import HttpResponseRedirect
from django.urls import path
from django.template.response import TemplateResponse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from .models import TelegramGroup
from .services import send_telegram_post_sync, send_post_to_bot_subscribers
from topics.models import Topic
from accounts.models import TelegramUser
import re
import asyncio
import logging

logger = logging.getLogger(__name__)


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
    
    def get_urls(self):
        """
        Добавляем кастомные URL для отправки постов.
        """
        urls = super().get_urls()
        custom_urls = [
            path('send-post/', self.admin_site.admin_view(self.send_post_view), name='telegram_send_post'),
        ]
        return custom_urls + urls
    
    def send_post_view(self, request):
        """
        Представление для отправки поста.
        """
        if request.method == 'POST':
            form = TelegramPostForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    # Получаем данные из формы
                    channels = form.cleaned_data['channels']
                    text = form.cleaned_data.get('text', '').strip()
                    
                    # Собираем файлы (только по одному каждого типа)
                    photos_list = []
                    gifs_list = []
                    videos_list = []
                    
                    # Фотография (только одно)
                    photo = form.cleaned_data.get('photo')
                    if photo:
                        photos_list.append(photo)
                        logger.info(f"Добавлено фото: {photo.name}")
                    
                    # GIF (только один)
                    gif = form.cleaned_data.get('gif')
                    if gif:
                        gifs_list.append(gif)
                        logger.info(f"Добавлен GIF: {gif.name}")
                    
                    # Видео (только одно)
                    video = form.cleaned_data.get('video')
                    if video:
                        videos_list.append(video)
                        logger.info(f"Добавлено видео: {video.name}")
                    
                    logger.info(f"Всего собрано: фото={len(photos_list)}, gif={len(gifs_list)}, видео={len(videos_list)}")
                    
                    # Подготавливаем кнопки
                    buttons = []
                    button1_text = form.cleaned_data.get('button1_text')
                    button1_url = form.cleaned_data.get('button1_url')
                    button2_text = form.cleaned_data.get('button2_text')
                    button2_url = form.cleaned_data.get('button2_url')
                    
                    if button1_text and button1_url:
                        buttons.append({'text': button1_text, 'url': button1_url})
                    
                    if button2_text and button2_url:
                        buttons.append({'text': button2_text, 'url': button2_url})
                    
                    # Отправляем пост во все выбранные каналы
                    success_count = 0
                    total_channels = len(channels) if channels else 0
                    bot_subscribers_sent = 0
                    
                    # Отправка в выбранные каналы/группы
                    if channels:
                        for channel in channels:
                            success = send_telegram_post_sync(
                                channel=channel,
                                text=text if text else None,
                                photos=photos_list,
                                gifs=gifs_list,
                                videos=videos_list,
                                buttons=buttons if buttons else None
                            )
                            
                            if success:
                                success_count += 1
                    
                    # Отправка подписчикам бота
                    send_to_subscribers = form.cleaned_data.get('send_to_bot_subscribers', False)
                    if send_to_subscribers:
                        bot_subscribers_sent = send_post_to_bot_subscribers(
                            text=text if text else None,
                            photos=photos_list,
                            gifs=gifs_list,
                            videos=videos_list,
                            buttons=buttons if buttons else None
                        )
                    
                    # Формируем сообщения об успехе
                    success_messages = []
                    if total_channels > 0:
                        if success_count == total_channels:
                            success_messages.append(_('Пост успешно отправлен во все {} каналов!').format(total_channels))
                        elif success_count > 0:
                            success_messages.append(_('Пост отправлен в {} из {} каналов.').format(success_count, total_channels))
                        else:
                            success_messages.append(_('Ошибка при отправке поста во все каналы.'))
                    
                    if send_to_subscribers:
                        if bot_subscribers_sent > 0:
                            success_messages.append(_('Пост отправлен {} подписчикам бота.').format(bot_subscribers_sent))
                        else:
                            success_messages.append(_('Не удалось отправить пост подписчикам бота.'))
                    
                    if not channels and not send_to_subscribers:
                        messages.error(request, _('Необходимо выбрать хотя бы один канал/группу или включить отправку подписчикам бота.'))
                    else:
                        for msg in success_messages:
                            if 'Ошибка' in msg or 'Не удалось' in msg:
                                messages.warning(request, msg)
                            else:
                                messages.success(request, msg)
                    
                    return HttpResponseRedirect('../')
                    
                except Exception as e:
                    logger.error(f"Ошибка при отправке поста: {e}")
                    messages.error(request, f'Ошибка при отправке поста: {str(e)}')
        else:
            form = TelegramPostForm()
        
        context = {
            'title': _('Отправить пост в Telegram'),
            'form': form,
            'opts': self.model._meta,
        }
        return TemplateResponse(request, 'admin/platforms/telegram_post_form.html', context)
    
    def changelist_view(self, request, extra_context=None):
        """
        Добавляем кнопку для отправки поста в список каналов.
        """
        extra_context = extra_context or {}
        extra_context['show_send_post_button'] = True
        return super().changelist_view(request, extra_context)

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


class TelegramPostForm(forms.Form):
    """
    Форма для создания и отправки поста в Telegram каналы/группы.
    """
    channels = forms.ModelMultipleChoiceField(
        queryset=TelegramGroup.objects.all(),
        label=_('Каналы/Группы'),
        help_text=_('Выберите один или несколько каналов/групп для публикации (можно выбрать несколько, удерживая Ctrl)'),
        widget=forms.SelectMultiple(attrs={'size': '8', 'class': 'channels-select'}),
        required=False
    )
    
    send_to_bot_subscribers = forms.BooleanField(
        required=False,
        label=_('Отправить подписчикам бота'),
        help_text=_('Отправить пост всем активным подписчикам бота в личные сообщения')
    )
    
    text = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5, 
            'cols': 80,
            'id': 'id_text'
        }),
        label=_('Текст поста'),
        help_text=_('Введите текст поста (макс. 1024 символа после конвертации). Поддерживается Markdown: ## заголовок, **жирный**, *курсив*, `код`, ```python\nблок кода\n```'),
        required=False
    )
    
    # Медиафайлы (только по одному файлу каждого типа)
    photo = forms.FileField(
        required=False,
        label=_('Фотография'),
        help_text=_('Загрузите изображение (JPG, PNG). Максимальный размер: 20 МБ'),
        widget=forms.FileInput(attrs={'accept': 'image/*'})
    )
    
    gif = forms.FileField(
        required=False,
        label=_('GIF анимация'),
        help_text=_('Загрузите GIF анимацию. Максимальный размер: 20 МБ'),
        widget=forms.FileInput(attrs={'accept': '.gif'})
    )
    
    video = forms.FileField(
        required=False,
        label=_('Видео'),
        help_text=_('Загрузите видео (MP4). Максимальный размер: 20 МБ'),
        widget=forms.FileInput(attrs={'accept': 'video/*'})
    )
    
    # Inline кнопки
    button1_text = forms.CharField(
        max_length=64,
        required=False,
        label=_('Текст кнопки 1'),
        help_text=_('Текст для первой inline кнопки')
    )
    
    button1_url = forms.URLField(
        required=False,
        label=_('Ссылка кнопки 1'),
        help_text=_('URL для первой кнопки (например: https://example.com или https://t.me/channel)')
    )
    
    button2_text = forms.CharField(
        max_length=64,
        required=False,
        label=_('Текст кнопки 2'),
        help_text=_('Текст для второй inline кнопки')
    )
    
    button2_url = forms.URLField(
        required=False,
        label=_('Ссылка кнопки 2'),
        help_text=_('URL для второй кнопки')
    )
    
    def clean(self):
        """
        Валидация формы: проверяем, что есть либо текст, либо медиа.
        """
        cleaned_data = super().clean()
        text = cleaned_data.get('text')
        channels = cleaned_data.get('channels')
        send_to_subscribers = cleaned_data.get('send_to_bot_subscribers', False)
        
        # Проверяем, что выбран хотя бы один канал или включена отправка подписчикам
        if not channels and not send_to_subscribers:
            raise forms.ValidationError(_('Необходимо выбрать хотя бы один канал/группу или включить отправку подписчикам бота.'))
        
        # Проверяем размеры файлов
        if cleaned_data.get('photo') and cleaned_data['photo'].size > 20 * 1024 * 1024:  # 20MB
            raise forms.ValidationError(_('Размер фотографии не должен превышать 20 МБ'))
        
        if cleaned_data.get('gif') and cleaned_data['gif'].size > 20 * 1024 * 1024:  # 20MB
            raise forms.ValidationError(_('Размер GIF не должен превышать 20 МБ'))
        
        if cleaned_data.get('video') and cleaned_data['video'].size > 20 * 1024 * 1024:  # 20MB
            raise forms.ValidationError(_('Размер видео не должен превышать 20 МБ'))
        
        # Проверяем, что есть хотя бы текст или один медиафайл
        has_media = any(cleaned_data.get(field) for field in ['photo', 'gif', 'video'])
        if not text and not has_media:
            raise forms.ValidationError(_('Необходимо указать текст поста или загрузить медиафайл.'))
        
        # Проверяем, что если есть текст кнопки, то есть и URL
        button1_text = cleaned_data.get('button1_text')
        button1_url = cleaned_data.get('button1_url')
        button2_text = cleaned_data.get('button2_text')
        button2_url = cleaned_data.get('button2_url')
        
        if button1_text and not button1_url:
            raise forms.ValidationError(_('Для кнопки 1 указан текст, но не указана ссылка.'))
        
        if button2_text and not button2_url:
            raise forms.ValidationError(_('Для кнопки 2 указан текст, но не указана ссылка.'))
        
        if button1_url and not button1_text:
            raise forms.ValidationError(_('Для кнопки 1 указана ссылка, но не указан текст.'))
        
        if button2_url and not button2_text:
            raise forms.ValidationError(_('Для кнопки 2 указана ссылка, но не указан текст.'))
        
        return cleaned_data


