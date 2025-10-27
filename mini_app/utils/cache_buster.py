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
        return f"{static_path}{filename}?v={version_from_config}&t={get_cache_buster()}&force={int(time.time())}"
    # Если есть хэш, используем его, иначе используем версию из конфига + timestamp
    elif file_hash:
        return f"{static_path}{filename}?v={file_hash}"
    else:
        return f"{static_path}{filename}?v={version_from_config}&t={get_cache_buster()}"


# Версии для критически важных файлов
STATIC_VERSIONS = {
    'donation.js': '2.9',  # Установлена английская локаль для Stripe Elements
    'localization.js': '2.7',  # Добавлен перевод reply_to для индикации ответов в комментариях
    'share-app.js': '2.0',  # Улучшено: display flex для корректного отображения модального окна
    'search.js': '2.2',  # Исправлено: добавлен has_tasks в API endpoint и language в запрос
    'tasks.js': '3.12',  # Центрирование toast уведомлений с учетом Safe Areas
    'topic-cards.js': '2.5',  # Добавлено программное воспроизведение видео при открытии увеличенной карточки
    'topic-detail.js': '1.6',
    'top_users.js': '30.4',  # ИСПРАВЛЕНО: Фильтры теперь применяются ко всем пользователям (включая модальное окно)
    'top_users_swiper.js': '1.3',  # Отключен для избежания конфликтов (инициализация теперь в top_users.html)
    'statistics.js': '3.7',  # FIX: улучшена инициализация при SPA-навигации, предотвращена двойная загрузка
    'platform-detector.js': '2.0',  # Добавлены Telegram-специфичные CSS переменные для safe areas
    'styles.css': '3.2',  # Перенос контента из <head> в <body> (фикc скрытий)
    'donation.css': '1.3',  # Обновлено: добавлена поддержка safe areas для Stripe модального окна
    'profile.css': '12.0',  # CRITICAL FIX: Прямое переопределение .content вместо :has() для Telegram WebView
    'user_profile.css': '5.0',  # CRITICAL FIX: Прямое переопределение .content вместо :has() для Telegram WebView
    'share-app.css': '2.3',  # Увеличена высота окна: 80vh и 70vh для большего отображения контента
    'explanation-modal.css': '1.1',  # Обновлено: добавлена поддержка safe areas
    'profile.js': '7.1',  # FIX: Автоматическое удаление старых аватарок перед загрузкой новых
    'user_profile.js': '2.5',  # FIX: Добавлена загрузка Swiper JS и CSS для модального окна аватарок
    'avatar_modal.css': '2.1',  # FIX: Добавлена поддержка Safe Areas для Telegram в модальном окне аватарок
    # Принудительное обновление кэша для Django моделей
    'models.py': '1.1',  # FIX: Добавлено автоматическое удаление файлов аватарок при удалении записей
    'serializers.py': '1.1',  # FIX: Исправлена логика отображения аватаров - главный аватар теперь первый в свайпе
    'admin.py': '1.1',  # FIX: Улучшена админка для понятного отображения главного аватара и галереи
    'top_users.css': '35.0',  # CRITICAL FIX: Прямое переопределение .content вместо :has() для Telegram WebView
    'top_users_swiper.css': '30.3',  # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Убран inset:unset который переопределял top/left
    'topic_cards_swiper.css': '1.1',  # Добавлены стили для video в увеличенной карточке  # Стили для Swiper карточек тем (аналогично top_users_swiper.css)
    'statistics.css': '7.0',  # NEW: Добавлено отображение total_points, topic_progress и achievements
    # Принудительное обновление кэша для Django статических файлов
    'global.css': '2.0',  # Принудительное обновление кэша для исправления стилей
    # Добавляем недостающие CSS файлы для единообразного кэширования
    'topic_detail.css': '1.3',  # Улучшена кликабельность полос прогресса: иконки, анимации, увеличенная высота
    'tasks.css': '1.0',  # Унификация кэширования
    'settings.css': '6.2',  # Добавлена подсказка об изображениях
    'feedback.js': '2.6',  # Добавлена поддержка загрузки изображений (до 3 шт, макс 5MB)
    'admin_analytics.js': '4.4',  # FIX: фильтрация донатов мини-аппа на фронтенде из by_source
    'settings.js': '3.1',  # FIX: предотвращена повторная декларация класса при SPA
    'admin_analytics.css': '1.4',  # FIX: Добавлены Safe Area Insets для единообразия с другими страницами
    'share-topic.js': '4.2',  # FIX: Исправлен синтаксис для линтера
    'share-topic.css': '1.8',  # FIX: Улучшены CSS правила для скрытия кнопок в неразвернутых карточках
    'topic-cards.js': '2.8',  # FIX: Улучшена логика отображения кнопок поделиться
    'comments.js': '3.0',  # Автоматический скролл к форме при фокусе + Telegram.WebApp.expand()
    'comments.css': '2.5',  # Добавлен padding-bottom для пространства под навигацией
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
