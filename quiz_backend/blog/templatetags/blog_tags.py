# blog/templatetags/blog_tags.py
from urllib.parse import quote

from django import template
from django.conf import settings
from django.templatetags.static import static
from blog.utils import process_code_blocks_for_web


register = template.Library()


@register.filter
def endswith(value, arg):
    """Проверяет, заканчивается ли строка на заданное значение."""
    if value and isinstance(value, str):
        return value.lower().endswith(arg.lower())
    return False


@register.filter
def safe_url(value):
    """
    Экранирует только слэши в пути URL, сохраняя остальную структуру.

    Args:
        value (str): Исходный URL.

    Returns:
        str: URL с экранированными слэшами в пути.
    """
    if not value:
        return value
    # Разделяем URL на схему, домен и путь
    parts = value.split('/', 3)
    if len(parts) < 4:
        return value  # Если нет пути, возвращаем как есть
    # Экранируем только часть пути
    safe_path = quote(parts[3], safe='')  # Экранируем слэши в пути
    return f"{parts[0]}//{parts[1]}/{parts[2]}/{safe_path}"


@register.simple_tag
def static_versioned(path):
    """
    Возвращает URL статического файла с версией для cache-busting.
    
    Args:
        path (str): Путь к статическому файлу (например, 'blog/js/quiz_combined.js')
    
    Returns:
        str: URL с параметром версии (например, '/static/blog/js/quiz_combined.js?v=2.1')
    """
    url = static(path)
    # Извлекаем имя файла из пути
    filename = path.split('/')[-1]
    # Получаем версию из настроек
    version = getattr(settings, 'STATIC_FILES_VERSION', {}).get(filename, '1.0')
    # Добавляем версию как параметр запроса
    separator = '&' if '?' in url else '?'
    return f"{url}{separator}v={version}"


@register.filter
def process_code(content):
    """
    Обрабатывает кодовые блоки в контенте поста для веб-отображения.
    Конвертирует fenced Markdown блоки в HTML с классами для highlight.js.
    
    Args:
        content (str): HTML контент поста
        
    Returns:
        str: HTML с обработанными кодовыми блоками
    """
    if not content:
        return content
    return process_code_blocks_for_web(content)