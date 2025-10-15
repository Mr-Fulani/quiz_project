import os
from django import forms
from django.contrib import admin
from django.conf import settings
from .models import Topic, Subtopic

class TopicAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        icons_dir = os.path.join(settings.BASE_DIR, 'blog', 'static', 'blog', 'images', 'icons')
        choices = [('', '--- Выберите иконку ---')]
        
        if os.path.exists(icons_dir):
            icon_files = []
            for filename in os.listdir(icons_dir):
                if filename.endswith(('.png', '.jpg', '.jpeg', '.svg')):
                    icon_files.append(filename)
            
            # Сортируем файлы по алфавиту
            icon_files.sort()
            
            for filename in icon_files:
                icon_path = f'/static/blog/images/icons/{filename}'
                # Убираем расширение и дефисы для отображения
                display_name = filename.replace('-icon.png', '').replace('-icon.svg', '').replace('-', ' ').title()
                choices.append((icon_path, f"{display_name} ({filename})"))
        
        self.fields['icon'] = forms.ChoiceField(
            choices=choices, 
            required=False, 
            help_text='Выберите иконку для темы'
        )

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    """
    Админка для управления темами
    """
    form = TopicAdminForm
    list_display = ('id', 'name', 'icon_preview', 'media_type', 'media_preview', 'description', 'get_subtopics_count')
    search_fields = ('name', 'description')
    list_filter = ('media_type',)
    ordering = ('name',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'icon')
        }),
        ('Медиа для карточки в карусели', {
            'fields': ('media_type', 'card_image', 'card_video', 'video_poster'),
            'description': 'Загрузите изображение, GIF или видео для отображения в карусели мини-приложения. Для видео можно загрузить постер (превью). Максимальный размер файла: 50 МБ.'
        }),
    )

    def get_subtopics_count(self, obj):
        """Получить количество подтем"""
        return obj.subtopics.count()
    get_subtopics_count.short_description = 'Количество подтем'
    
    def icon_preview(self, obj):
        if obj.icon:
            return f'<img src="{obj.icon}" alt="{obj.name}" style="width: 32px; height: 32px; object-fit: contain;">'
        return 'Нет иконки'
    icon_preview.short_description = 'Иконка'
    icon_preview.allow_tags = True
    
    def media_preview(self, obj):
        """Превью медиа для карточки"""
        if obj.media_type == 'image' and obj.card_image:
            return f'<img src="{obj.card_image.url}" alt="{obj.name}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;">'
        elif obj.media_type == 'video' and obj.card_video:
            return f'<video src="{obj.card_video.url}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" muted></video>'
        elif obj.media_type == 'default':
            return '📷 По умолчанию'
        return '❌ Нет медиа'
    media_preview.short_description = 'Превью медиа'
    media_preview.allow_tags = True

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    """
    Админка для управления подтемами
    """
    list_display = ('id', 'name', 'topic', 'get_tasks_count')
    list_filter = ('topic',)
    search_fields = ('name', 'topic__name')
    raw_id_fields = ('topic',)
    ordering = ('topic', 'name')

    def get_tasks_count(self, obj):
        """Получить количество задач в подтеме"""
        return obj.tasks.count()
    get_tasks_count.short_description = 'Количество задач'
