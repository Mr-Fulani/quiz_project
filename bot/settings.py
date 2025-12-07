# bot/settings.py
"""
Модуль для доступа к настройкам Django из бота.
"""

from django.conf import settings as django_settings


def get_settings():
    """
    Возвращает объект настроек Django.
    
    Returns:
        Модуль настроек Django с атрибутами DEBUG, AWS_PUBLIC_MEDIA_DOMAIN и другими.
    """
    return django_settings

