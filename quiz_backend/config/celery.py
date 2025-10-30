"""
Конфигурация Celery для асинхронных задач.

Используется для:
- Отправки email в фоне
- Генерации изображений OG
- Пересчета статистики пользователей
- Очистки устаревших данных
"""
import os
from celery import Celery
from celery.schedules import crontab

# Устанавливаем модуль настроек Django для Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('quiz_backend')

# Загружаем конфигурацию из settings.py с префиксом CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически находим задачи в приложениях Django
app.autodiscover_tasks()

# Явно импортируем задачи из config.tasks
# (т.к. config не является Django приложением)
app.autodiscover_tasks(['config'])


# Периодические задачи (запускаются по расписанию)
app.conf.beat_schedule = {
    # Очистка устаревших сессий каждый день в 3:00
    'clear-old-sessions': {
        'task': 'config.tasks.clear_expired_sessions',
        'schedule': crontab(hour=3, minute=0),
    },
    # Обновление статистики каждые 30 минут
    'update-statistics': {
        'task': 'config.tasks.update_user_statistics_cache',
        'schedule': crontab(minute='*/30'),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Тестовая задача для проверки работы Celery."""
    print(f'Request: {self.request!r}')

