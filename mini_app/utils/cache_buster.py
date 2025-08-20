"""
Утилиты для обхода кэша в Telegram WebApp
"""
import time
import os
import hashlib
from typing import Optional


def get_cache_buster() -> str:
    """
    Возвращает timestamp для обхода кэша
    В продакшене можно использовать хэш файла
    """
    return str(int(time.time()))


def get_file_hash(file_path: str) -> Optional[str]:
    """
    Возвращает MD5 хэш файла для кэширования
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()[:8]
    except Exception:
        pass
    return get_cache_buster()


def get_versioned_url(static_path: str, version: str = None) -> str:
    """
    Возвращает URL с версией для статических файлов
    
    Args:
        static_path: путь к файлу (например, '/static/js/donation.js')
        version: версия файла (опционально)
    
    Returns:
        URL с параметрами версии и timestamp
    """
    if version:
        return f"{static_path}?v={version}&t={get_cache_buster()}"
    else:
        return f"{static_path}?t={get_cache_buster()}"


# Версии для критически важных файлов
STATIC_VERSIONS = {
    'donation.js': '2.1',
    'localization.js': '1.9',
    'share-app.js': '1.8',
    'profile.js': '1.6',
    'search.js': '1.6',
    'tasks.js': '1.3',
    'topic-cards.js': '1.4'
}


def get_js_url(filename: str) -> str:
    """
    Получить URL для JS файла с версией и cache buster
    """
    version = STATIC_VERSIONS.get(filename, '1.0')
    return get_versioned_url(f'/static/js/{filename}', version)


def get_css_url(filename: str, version: str = '1.0') -> str:
    """
    Получить URL для CSS файла с версией и cache buster
    """
    return get_versioned_url(f'/static/css/{filename}', version)
