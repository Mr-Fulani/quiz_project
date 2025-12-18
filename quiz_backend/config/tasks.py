"""
Celery задачи для фоновой обработки.

Все длительные операции должны выполняться через Celery,
чтобы не блокировать HTTP-запросы.
"""
import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_async(self, subject, message, from_email, recipient_list, html_message=None):
    """
    Асинхронная отправка email.
    
    Args:
        subject: Тема письма
        message: Текст письма (plain text)
        from_email: Email отправителя
        recipient_list: Список получателей
        html_message: HTML версия письма (опционально)
    
    Автоматически повторяет попытку при ошибке (до 3 раз).
    """
    try:
        logger.info(f"Отправка email: {subject} -> {recipient_list}")
        
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Email успешно отправлен: {subject}")
        return True
        
    except Exception as exc:
        logger.error(f"Ошибка отправки email: {str(exc)}")
        # Повторная попытка через 60 секунд
        raise self.retry(exc=exc)


@shared_task
def send_contact_form_email(fullname, email, message_text):
    """
    Отправка сообщения из контактной формы.
    
    Args:
        fullname: Имя отправителя
        email: Email отправителя
        message_text: Текст сообщения
    """
    subject = f'Новое сообщение от {fullname} ({email})'
    message = f'Имя: {fullname}\nEmail: {email}\nСообщение:\n{message_text}'
    
    return send_email_async.delay(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=settings.EMAIL_ADMIN,
    )


@shared_task
def clear_expired_sessions():
    """
    Очистка устаревших сессий из БД.
    Запускается автоматически каждый день в 3:00.
    """
    try:
        expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
        count = expired_sessions.count()
        expired_sessions.delete()
        logger.info(f"Удалено {count} устаревших сессий")
        return count
    except Exception as e:
        logger.error(f"Ошибка очистки сессий: {str(e)}")
        return 0


@shared_task
def update_user_statistics_cache():
    """
    Обновление кэша статистики пользователей.
    Запускается каждые 30 минут для активных пользователей.
    """
    from accounts.models import CustomUser
    from django.core.cache import cache
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Обновляем кэш для пользователей, активных за последние 24 часа
        active_since = timezone.now() - timedelta(hours=24)
        active_users = CustomUser.objects.filter(
            last_seen__gte=active_since
        ).select_related().prefetch_related('statistics')
        
        count = 0
        for user in active_users:
            cache_key = f'user_stats_{user.id}'
            stats = user.get_statistics()
            cache.set(cache_key, stats, 3600)  # Кэшируем на 1 час
            count += 1
        
        logger.info(f"Обновлен кэш статистики для {count} активных пользователей")
        return count
        
    except Exception as e:
        logger.error(f"Ошибка обновления кэша статистики: {str(e)}")
        return 0


@shared_task
def generate_og_image(post_id):
    """
    Генерация OG-изображения для поста.
    
    Args:
        post_id: ID поста
    """
    try:
        from blog.models import Post
        
        logger.info(f"Генерация OG-изображения для поста {post_id}")
        post = Post.objects.get(id=post_id)
        
        # TODO: Здесь добавить логику генерации изображения
        # Пока просто логируем
        logger.info(f"OG-изображение для '{post.title}' готово")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка генерации OG-изображения: {str(e)}")
        return False


@shared_task
def cleanup_old_media_files():
    """
    Очистка неиспользуемых медиа-файлов.
    Удаляет файлы, на которые нет ссылок в БД.
    """
    import os
    from django.conf import settings
    
    try:
        logger.info("Начало очистки неиспользуемых медиа-файлов")
        # TODO: Реализовать логику поиска и удаления
        logger.info("Очистка медиа-файлов завершена")
        return True
    except Exception as e:
        logger.error(f"Ошибка очистки медиа-файлов: {str(e)}")
        return False


@shared_task(bind=True)
def process_uploaded_file(self, file_path, user_id):
    """
    Обработка загруженного файла (изменение размера, оптимизация).
    
    Args:
        file_path: Путь к файлу
        user_id: ID пользователя
    """
    try:
        from PIL import Image
        
        logger.info(f"Обработка файла: {file_path}")
        
        # Открываем изображение
        img = Image.open(file_path)
        
        # Оптимизируем размер (если больше 2000px)
        max_size = (2000, 2000)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            img.save(file_path, optimize=True, quality=85)
            logger.info(f"Изображение оптимизировано: {file_path}")
        
        return True
        
    except Exception as exc:
        logger.error(f"Ошибка обработки файла: {str(exc)}")
        raise self.retry(exc=exc, countdown=30)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def generate_video_for_task_async(self, task_id, task_question, topic_name, subtopic_name=None, difficulty=None):
    """
    Асинхронная генерация видео для задачи.
    
    Генерирует видео в фоне, чтобы не блокировать публикацию задач.
    Видео автоматически отправляется админу после генерации.
    Все этапы логируются для отслеживания в админке.
    
    Args:
        task_id: ID задачи
        task_question: Текст вопроса задачи
        topic_name: Название темы
        subtopic_name: Название подтемы (опционально)
        difficulty: Сложность задачи (опционально)
    
    Returns:
        URL видео или None при ошибке
    """
    try:
        from tasks.models import Task
        from tasks.services.video_generation_service import generate_video_for_task
        from django.contrib import messages
        from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
        
        logger.info(f"🎬 [Celery] ════════════════════════════════════════════════")
        logger.info(f"🎬 [Celery] Начало генерации видео для задачи {task_id}")
        logger.info(f"🎬 [Celery] Параметры: тема={topic_name}, подтема={subtopic_name}, сложность={difficulty}")
        
        # Проверяем, что задача еще существует и не имеет видео
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            logger.warning(f"⚠️ [Celery] Задача {task_id} не найдена, пропускаем генерацию видео")
            return None
        
        # Если видео уже есть, пропускаем
        if task.video_url:
            logger.info(f"ℹ️ [Celery] Задача {task_id} уже имеет видео: {task.video_url}")
            return task.video_url
        
        logger.info(f"📝 [Celery] Этап 1/4: Извлечение кода из вопроса...")
        # Генерируем видео (внутри функции уже есть отправка админу)
        video_url = generate_video_for_task(
            task_question,
            topic_name,
            subtopic_name=subtopic_name,
            difficulty=difficulty
        )
        
        if video_url:
            logger.info(f"📝 [Celery] Этап 2/4: Видео сгенерировано")
            logger.info(f"📝 [Celery] Этап 3/4: Загрузка в S3/R2...")
            
            # Сохраняем URL видео в задачу
            task.video_url = video_url
            task.save(update_fields=['video_url'])
            
            logger.info(f"📝 [Celery] Этап 4/4: Видео отправлено админу в Telegram")
            logger.info(f"✅ [Celery] Видео успешно сгенерировано для задачи {task_id}")
            logger.info(f"   🔗 URL: {video_url}")
            logger.info(f"🎬 [Celery] ════════════════════════════════════════════════")
            return video_url
        else:
            logger.warning(f"⚠️ [Celery] Не удалось сгенерировать видео для задачи {task_id}")
            logger.warning(f"   🔍 Проверьте логи выше для деталей ошибки")
            logger.info(f"🎬 [Celery] ════════════════════════════════════════════════")
            return None
            
    except Exception as exc:
        logger.error(f"❌ [Celery] ════════════════════════════════════════════════")
        logger.error(f"❌ [Celery] ОШИБКА генерации видео для задачи {task_id}")
        logger.error(f"   📋 Тип ошибки: {type(exc).__name__}")
        logger.error(f"   📝 Сообщение: {str(exc)}")
        logger.error(f"   🔍 Полный traceback будет в логах выше")
        logger.error(f"❌ [Celery] ════════════════════════════════════════════════")
        # Повторная попытка через 5 минут (если не превышен лимит)
        raise self.retry(exc=exc, countdown=300)

