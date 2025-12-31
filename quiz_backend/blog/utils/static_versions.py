"""
Версии статических файлов для cache-busting в Django backend.
Обновляйте эти версии при изменении соответствующих файлов.
"""

STATIC_VERSIONS = {
    'quiz_combined.js': '2.1',  # Добавлен mobile image zoom, исправлена обработка touch событий для кнопок ответов
    'quiz_styles.css': '2.1',   # Добавлены стили для модального окна объяснений, mobile image zoom overlay
}

