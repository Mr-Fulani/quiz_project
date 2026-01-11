"""
Версии статических файлов для cache-busting в Django backend.
Обновляйте эти версии при изменении соответствующих файлов.
"""

STATIC_VERSIONS = {
    'quiz_combined.js': '2.1',  # Добавлен mobile image zoom, исправлена обработка touch событий для кнопок ответов
    'quiz_styles.css': '2.1',   # Добавлены стили для модального окна объяснений, mobile image zoom overlay

    # Дополнительно версионируем базовые стили, чтобы изменения (алиасы классов) сразу подтягивались
    'global.css': '5.0',  # Добавлены стили для полосы прогресса на карточках тем и подтем
    'blog_page.html': '1.1',
    'portfolio.html': '1.1',
    'header-spacing.css': '2.0',
    'animated_auth.css': '2.0',
    'cookie-consent.css': '2.0',
    'font-awesome.min.css': '2.0',
    'font-awesome.min.js': '2.0',
    'resources.css': '2.0',  # Обновлено для отображения иконок по 2 в ряд на мобильных
    'interactions.js': '2.3',  # Реализовано круговое меню для шаринга с анимациями
    'interactions.css': '2.3',  # Реализовано круговое меню для шаринга с анимациями
}

