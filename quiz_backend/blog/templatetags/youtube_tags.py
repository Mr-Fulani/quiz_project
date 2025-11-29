from django import template
from django.conf import settings
from urllib.parse import quote
import re
import logging

register = template.Library()


def _extract_video_id(value):
    """Извлекает ID видео из различных форматов YouTube URL."""
    if not value:
        return None
    
    # Обычные видео: youtube.com/watch?v=VIDEO_ID или youtu.be/VIDEO_ID
    match_standard = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', value)
    # Shorts: youtube.com/shorts/VIDEO_ID
    match_shorts = re.search(r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})', value)
    # Embed: youtube.com/embed/VIDEO_ID (возможно, с параметрами)
    match_embed = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]{11})', value)

    if match_standard:
        return match_standard.group(1)
    elif match_shorts:
        return match_shorts.group(1)
    elif match_embed:
        return match_embed.group(1)
    return None


@register.filter
def youtube_embed_url(value):
    """
    Преобразует любую ссылку YouTube (включая Shorts) в embed-формат.
    Использует youtube-nocookie.com для лучшей совместимости и privacy.
    
    Использование: {{ url|youtube_embed_url }}
    """
    video_id = _extract_video_id(value)
    if not video_id:
        return value  # Если не распознано, возвращаем как есть
    
    # Используем youtube-nocookie.com - часто лучше работает с встраиванием
    # Минимальные параметры для максимальной совместимости
    return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1"


@register.simple_tag(takes_context=True)
def youtube_embed_url_with_api(context, value):
    """
    Преобразует YouTube URL в embed-формат с поддержкой JavaScript API.
    Автоматически получает request из контекста для формирования origin.
    
    Использование: {% youtube_embed_url_with_api video.video_url %}
    """
    video_id = _extract_video_id(value)
    if not video_id:
        return value
    
    # Получаем origin для enablejsapi (необходимо для предотвращения ошибки 153)
    origin = None
    request = context.get('request')
    
    if request:
        try:
            scheme = 'https' if request.is_secure() else 'http'
            host = request.get_host()
            origin = f"{scheme}://{host}"
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting origin from request: {e}")
    
    if not origin:
        # Fallback на настройки
        origin = getattr(settings, 'PUBLIC_URL', 'http://localhost:8001')
        if not origin.startswith(('http://', 'https://')):
            origin = f"https://{origin}"
    
    # Формируем URL с параметрами для правильной работы YouTube API
    # Важно: origin должен быть правильно закодирован
    base_url = f"https://www.youtube.com/embed/{video_id}"
    params = [
        "enablejsapi=1",
        f"origin={quote(origin, safe='')}",
        "modestbranding=1",
        "rel=0",
        "playsinline=1"
    ]
    
    return f"{base_url}?{'&'.join(params)}"