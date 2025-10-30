"""
Инициализация приложения Django и Celery.
"""

# Это гарантирует, что Celery приложение всегда импортируется
# когда Django стартует, чтобы shared_task использовал это приложение.
# Делаем импорт опциональным для совместимости с telegram bot
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celery не установлен (например, в telegram bot контейнере)
    __all__ = ()

