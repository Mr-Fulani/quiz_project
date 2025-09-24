"""
Утилиты для обхода кэша в Telegram WebApp
"""
import time
import os
import hashlib
from typing import Optional

CACHE_BUSTER_CACHE = {}


def get_cache_buster() -> str:
    """
    Возвращает timestamp для обхода кэша
    В продакшене можно использовать хэш файла
    """
    return str(int(time.time()))


def get_file_hash(file_path: str) -> Optional[str]:
    """
    Возвращает MD5 хэш файла для кэширования
    Кэширует результат для производительности.
    """
    if file_path in CACHE_BUSTER_CACHE:
        return CACHE_BUSTER_CACHE[file_path]

    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../static', file_path.replace('/static/', ''))
    try:
        if os.path.exists(full_path):
            with open(full_path, 'rb') as f:
                content = f.read()
                file_hash = hashlib.md5(content).hexdigest()[:8]
                CACHE_BUSTER_CACHE[file_path] = file_hash
                return file_hash
    except Exception as e:
        # В случае ошибки возвращаем timestamp
        print(f"Ошибка при генерации хэша для файла {full_path}: {e}")
        pass
    
    # Если файл не найден или ошибка, используем timestamp
    return get_cache_buster()


def get_versioned_url(static_path: str, filename: str) -> str:
    """
    Возвращает URL с версией для статических файлов, используя хэш файла.
    Если хэш не может быть получен, используется timestamp или жестко заданная версия.
    
    Args:
        static_path: базовый путь к файлу (например, '/static/js/')
        filename: имя файла (например, 'tasks.js')
    
    Returns:
        URL с параметром версии (хэш файла).
    """
    file_hash = get_file_hash(f'{static_path}{filename}')
    
    # Используем версию из STATIC_VERSIONS как fallback, если хэш не получен
    version_from_config = STATIC_VERSIONS.get(filename, '1.0')
    
    # Принудительно используем версию из конфига для критически важных файлов
    if filename in STATIC_VERSIONS:
        return f"{static_path}{filename}?v={version_from_config}&t={get_cache_buster()}"
    # Если есть хэш, используем его, иначе используем версию из конфига + timestamp
    elif file_hash:
        return f"{static_path}{filename}?v={file_hash}"
    else:
        return f"{static_path}{filename}?v={version_from_config}&t={get_cache_buster()}"


# Версии для критически важных файлов
STATIC_VERSIONS = {
    'donation.js': '2.1',
    'localization.js': '2.1',
    'share-app.js': '1.8',
    'profile.js': '5.3',  # Обновлено: убрана отладка, исправлена проблема с localhost в avatar URL
    'search.js': '1.7',
    'tasks.js': '3.11',
    'topic-cards.js': '1.5',
    'topic-detail.js': '1.6',
    'top_users.js': '17.0',  # Изменены заголовки фильтров: "Технология" и "Грейд"
    'statistics.js': '3.6',  # Обновлено: исправлен mini_app API service для правильных заголовков
    'styles.css': '1.4',  # Обновлено: исправлен mini_app API service для аватарок
    'profile.css': '1.4',  # Обновлено: исправлен mini_app API service для аватарок
    'top_users.css': '2.0',  # Обновлены заголовки фильтров: "Технология" и "Грейд"
    'statistics.css': '2.7',  # Обновлено: принудительный сброс кэша для полосы прогресса
}


def get_js_url(filename: str) -> str:
    """
    Получить URL для JS файла с версией и cache buster.
    """
    return get_versioned_url('/static/js/', filename)


def get_css_url(filename: str) -> str:
    """
    Получить URL для CSS файла с версией и cache buster.
    """
    return get_versioned_url('/static/css/', filename)
