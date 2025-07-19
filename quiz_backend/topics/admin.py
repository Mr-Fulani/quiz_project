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
    list_display = ('id', 'name', 'icon_preview', 'description', 'get_subtopics_count')
    search_fields = ('name', 'description')
    ordering = ('name',)

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
