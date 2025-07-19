import os
from django import forms
from django.contrib import admin
from django.conf import settings
from .models import Topic

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

class TopicAdmin(admin.ModelAdmin):
    form = TopicAdminForm
    list_display = ['name', 'icon_preview', 'description']
    search_fields = ['name', 'description']
    
    def icon_preview(self, obj):
        if obj.icon:
            return f'<img src="{obj.icon}" alt="{obj.name}" style="width: 32px; height: 32px; object-fit: contain;">'
        return 'Нет иконки'
    icon_preview.short_description = 'Иконка'
    icon_preview.allow_tags = True

admin.site.register(Topic, TopicAdmin)
