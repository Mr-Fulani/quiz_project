from django import template
import re

register = template.Library()


@register.filter
def youtube_embed_url(value):
    """Преобразует любую ссылку YouTube (включая Shorts) в embed-формат"""
    if not value:
        return value
    # Обычные видео: youtube.com/watch?v=VIDEO_ID или youtu.be/VIDEO_ID
    match_standard = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', value)
    # Shorts: youtube.com/shorts/VIDEO_ID
    match_shorts = re.search(r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})', value)

    if match_standard:
        video_id = match_standard.group(1)
    elif match_shorts:
        video_id = match_shorts.group(1)
    else:
        return value  # Если не распознано, возвращаем как есть

    return f"https://www.youtube.com/embed/{video_id}"