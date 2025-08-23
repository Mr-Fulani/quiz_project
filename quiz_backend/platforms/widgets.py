from django import forms
from django.utils.safestring import mark_safe


class MultipleFileInput(forms.FileInput):
    """
    Кастомный виджет для загрузки нескольких файлов.
    """
    
    def __init__(self, attrs=None):
        default_attrs = {'multiple': 'multiple'}
        if attrs:
            default_attrs.update(attrs)
        # Убираем проверку на multiple в родительском классе
        super().__init__()
        self.attrs = default_attrs
    
    def render(self, name, value, attrs=None, renderer=None):
        # Создаем HTML для множественной загрузки файлов
        html = super().render(name, value, attrs, renderer)
        
        # Добавляем JavaScript для обработки множественных файлов
        js = f"""
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            const fileInput = document.querySelector('input[name="{name}"]');
            if (fileInput) {{
                fileInput.addEventListener('change', function(e) {{
                    const files = e.target.files;
                    const fileList = document.getElementById('file-list-{name}');
                    if (fileList) {{
                        fileList.innerHTML = '';
                        for (let i = 0; i < files.length; i++) {{
                            const file = files[i];
                            const fileItem = document.createElement('div');
                            fileItem.className = 'file-item';
                            fileItem.innerHTML = `
                                <span class="file-name">${{file.name}}</span>
                                <span class="file-size">(${{(file.size / 1024 / 1024).toFixed(2)}} МБ)</span>
                            `;
                            fileList.appendChild(fileItem);
                        }}
                    }}
                }});
            }}
        }});
        </script>
        """
        
        # Добавляем контейнер для отображения выбранных файлов
        file_list_html = f'<div id="file-list-{name}" class="file-list"></div>'
        
        return mark_safe(html + file_list_html + js)


class MultipleFileField(forms.FileField):
    """
    Кастомное поле для загрузки нескольких файлов.
    """
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)
    
    def clean(self, data, initial=None):
        # Получаем список файлов
        if hasattr(data, 'getlist'):
            files = data.getlist(self.name)
        else:
            # Если data - это файл, оборачиваем его в список
            files = data.get(self.name) if hasattr(data, 'get') else data
            if files:
                files = [files] if not isinstance(files, list) else files
            else:
                files = []
        
        # Фильтруем пустые файлы
        files = [f for f in files if f and hasattr(f, 'size') and f.size > 0]
        
        if self.required and not files:
            raise forms.ValidationError(self.error_messages['required'])
        
        return files
