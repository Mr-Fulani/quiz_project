# blog/templatetags/blog_tags.py
from urllib.parse import quote

from django import template


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