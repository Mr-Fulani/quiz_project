# 🎯 Django + Celery: Руководство для разработчика

## 📚 Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Как использовать Celery](#как-использовать-celery)
3. [Примеры задач](#примеры-задач)
4. [Периодические задачи](#периодические-задачи)
5. [Best Practices](#best-practices)

---

## 🚀 Быстрый старт

### 1. Создать асинхронную задачу

```python
# В любом файле приложения (например, tasks.py)
from celery import shared_task
from django.core.mail import send_mail

@shared_task
def send_welcome_email(user_email):
    """Отправка приветственного письма новому пользователю."""
    send_mail(
        subject='Добро пожаловать!',
        message='Спасибо за регистрацию!',
        from_email='noreply@quiz-code.com',
        recipient_list=[user_email],
    )
```

### 2. Вызвать задачу

```python
# В представлении или другом коде
from .tasks import send_welcome_email

def register_user(request):
    # ... логика регистрации ...
    
    # Синхронный вызов (блокирует выполнение)
    # send_welcome_email(user.email)  # ❌ ПЛОХО
    
    # Асинхронный вызов (мгновенно возвращает управление)
    send_welcome_email.delay(user.email)  # ✅ ХОРОШО
    
    return JsonResponse({'status': 'success'})
```

---

## 📋 Как использовать Celery

### Простая задача

```python
from celery import shared_task

@shared_task
def add_numbers(x, y):
    """Простая задача для демонстрации."""
    return x + y

# Вызов
result = add_numbers.delay(4, 5)
# result.id - ID задачи
# result.status - статус ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE')
# result.get() - получить результат (блокирующий вызов!)
```

### Задача с повторными попытками

```python
from celery import shared_task
import requests

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_data_from_api(self, url):
    """Получение данных с внешнего API с повторными попытками."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        # Повторить через 60 секунд (максимум 3 раза)
        raise self.retry(exc=exc)
```

### Задача с таймаутом

```python
@shared_task(time_limit=300, soft_time_limit=250)
def process_large_file(file_path):
    """Обработка большого файла с ограничением времени."""
    # soft_time_limit=250: предупреждение за 50 секунд до жесткого лимита
    # time_limit=300: жесткий лимит - задача будет убита
    pass
```

### Цепочка задач

```python
from celery import chain

# Последовательное выполнение задач
result = chain(
    download_file.s('https://example.com/file.pdf'),
    process_file.s(),
    send_notification.s('admin@quiz-code.com')
).apply_async()
```

### Групповое выполнение

```python
from celery import group

# Параллельное выполнение задач
job = group(
    send_email.s('user1@example.com', 'Hello'),
    send_email.s('user2@example.com', 'Hello'),
    send_email.s('user3@example.com', 'Hello'),
)
result = job.apply_async()
```

---

## 💡 Примеры задач

### Отправка email

```python
# config/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task(bind=True, max_retries=3)
def send_email_async(self, subject, message, recipient_list):
    """
    Асинхронная отправка email с автоматическими повторными попытками.
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        return True
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)

# Использование во view
from config.tasks import send_email_async

def contact_form(request):
    # ... обработка формы ...
    send_email_async.delay(
        subject='Новое сообщение',
        message=request.POST['message'],
        recipient_list=['admin@quiz-code.com']
    )
    return JsonResponse({'status': 'sent'})
```

### Генерация отчета

```python
@shared_task
def generate_user_report(user_id, report_type):
    """
    Генерация отчета для пользователя.
    Может занимать несколько минут.
    """
    from accounts.models import CustomUser
    import pandas as pd
    
    user = CustomUser.objects.get(id=user_id)
    
    # Собираем данные
    stats = user.get_statistics()
    tasks = user.task_statistics.all().values()
    
    # Создаем отчет
    df = pd.DataFrame(list(tasks))
    report_path = f'/tmp/report_{user_id}.xlsx'
    df.to_excel(report_path)
    
    # Отправляем пользователю
    send_email_async.delay(
        subject='Ваш отчет готов',
        message=f'Отчет сгенерирован: {report_path}',
        recipient_list=[user.email]
    )
    
    return report_path
```

### Обработка изображений

```python
@shared_task(bind=True)
def optimize_image(self, image_path):
    """
    Оптимизация загруженного изображения.
    """
    from PIL import Image
    import os
    
    try:
        img = Image.open(image_path)
        
        # Уменьшаем размер если больше 2000px
        max_size = (2000, 2000)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Конвертируем в RGB если RGBA
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # Сохраняем с оптимизацией
        img.save(image_path, optimize=True, quality=85)
        
        return f"Оптимизировано: {os.path.getsize(image_path)} байт"
        
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
```

---

## ⏰ Периодические задачи

### Настройка в celery.py

```python
# config/celery.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    # Каждый день в 3:00
    'cleanup-sessions': {
        'task': 'config.tasks.cleanup_old_sessions',
        'schedule': crontab(hour=3, minute=0),
    },
    
    # Каждые 30 минут
    'update-cache': {
        'task': 'config.tasks.update_statistics_cache',
        'schedule': crontab(minute='*/30'),
    },
    
    # Каждый понедельник в 9:00
    'weekly-report': {
        'task': 'config.tasks.send_weekly_report',
        'schedule': crontab(day_of_week=1, hour=9, minute=0),
    },
    
    # Каждые 10 секунд (только для тестирования!)
    'test-task': {
        'task': 'config.tasks.test_periodic',
        'schedule': 10.0,
    },
}
```

### Создание периодической задачи

```python
@shared_task
def cleanup_old_sessions():
    """
    Очистка устаревших сессий из БД.
    Запускается каждый день в 3:00.
    """
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    
    expired = Session.objects.filter(expire_date__lt=timezone.now())
    count = expired.count()
    expired.delete()
    
    return f"Удалено {count} устаревших сессий"
```

---

## 🎓 Best Practices

### 1. **Idempotency (Идемпотентность)**

Задача должна давать одинаковый результат при повторном выполнении:

```python
# ❌ ПЛОХО: каждый запуск добавляет +1
@shared_task
def increment_counter(user_id):
    user = User.objects.get(id=user_id)
    user.counter += 1
    user.save()

# ✅ ХОРОШО: результат одинаковый
@shared_task
def set_counter(user_id, value):
    user = User.objects.get(id=user_id)
    user.counter = value
    user.save()
```

### 2. **Обработка ошибок**

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def risky_task(self, data):
    try:
        # ... выполнение задачи ...
        pass
    except TemporaryError as exc:
        # Повторить позже
        raise self.retry(exc=exc)
    except PermanentError as exc:
        # Не повторять, залогировать
        logger.error(f"Permanent error: {exc}")
        return None
```

### 3. **Передавайте простые типы данных**

```python
# ❌ ПЛОХО: передача объектов Django
@shared_task
def process_user(user):  # User object
    user.process()

# ✅ ХОРОШО: передача ID
@shared_task
def process_user(user_id):
    user = User.objects.get(id=user_id)
    user.process()
```

### 4. **Логирование**

```python
import logging
logger = logging.getLogger(__name__)

@shared_task
def important_task(data):
    logger.info(f"Starting task with data: {data}")
    
    try:
        # ... выполнение ...
        logger.info("Task completed successfully")
    except Exception as e:
        logger.error(f"Task failed: {str(e)}")
        raise
```

### 5. **Не блокируйте worker'ы**

```python
# ❌ ПЛОХО: блокирующий sleep
@shared_task
def bad_task():
    time.sleep(3600)  # блокирует worker на час!

# ✅ ХОРОШО: используйте countdown
@shared_task
def good_task():
    # Выполнить задачу через час
    next_task.apply_async(countdown=3600)
```

### 6. **Мониторинг выполнения**

```python
@shared_task(bind=True)
def long_task(self, items):
    total = len(items)
    
    for idx, item in enumerate(items, 1):
        # Обновляем прогресс
        self.update_state(
            state='PROGRESS',
            meta={'current': idx, 'total': total}
        )
        
        # Обрабатываем item
        process_item(item)
    
    return {'status': 'completed', 'processed': total}
```

---

## 🔍 Отладка

### Просмотр активных задач

```bash
docker compose exec celery_worker celery -A config inspect active
```

### Просмотр зарегистрированных задач

```bash
docker compose exec celery_worker celery -A config inspect registered
```

### Отмена задачи

```python
from celery.result import AsyncResult

# Получить задачу по ID
result = AsyncResult(task_id)

# Отменить
result.revoke(terminate=True)
```

### Логи Celery

```bash
docker compose logs -f celery_worker
docker compose logs -f celery_beat
```

---

## 📚 Дополнительные ресурсы

- [Официальная документация Celery](https://docs.celeryproject.org/)
- [Django Celery Beat](https://django-celery-beat.readthedocs.io/)
- [Best practices](https://celery.readthedocs.io/en/stable/userguide/tasks.html#tips-and-best-practices)

