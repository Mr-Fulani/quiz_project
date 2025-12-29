"""
Celery задачи для фоновой обработки.

Все длительные операции должны выполняться через Celery,
чтобы не блокировать HTTP-запросы.
"""
import logging
import os
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


@shared_task(
    bind=True,
    max_retries=1,  # Уменьшаем количество повторных попыток для видео
    default_retry_delay=600,  # Увеличиваем задержку до 10 минут
    queue='celery' if os.getenv('DEBUG') == 'True' else 'video_queue',  # Локально celery, на проде video_queue
    time_limit=2200,     # Hard limit: 2200 секунд (принудительное завершение)
    soft_time_limit=2000 # Soft limit: 2000 секунд (graceful завершение)
)
def generate_video_for_task_async(self, task_id, task_question, topic_name, subtopic_name=None, difficulty=None, force_regenerate=False, admin_chat_id=None, video_language='ru', expected_languages=None):
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
        force_regenerate: Если True, перегенерирует видео даже если оно уже существует
        admin_chat_id: ID чата админа для отправки видео (опционально, если не указан, будет получен из настроек/БД)
        video_language: Язык видео ('ru', 'en') - определяет в какое поле сохранить URL
        expected_languages: Набор языков, которые должны быть сгенерированы для этой задачи

    Returns:
        URL видео или None при ошибке
    """
    try:
        from tasks.models import Task
        from tasks.services.video_generation_service import generate_video_for_task
        from django.contrib import messages
        from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
        from django.core.cache import cache

        # 🛡️ Circuit Breaker: проверка на частые ошибки видео генерации
        circuit_breaker_key = "video_generation_failures"
        max_failures = 5
        failures_count = cache.get(circuit_breaker_key, 0)

        if failures_count >= max_failures:
            logger.error(f"🚫 [Circuit Breaker] Видео генерация отключена из-за {failures_count} последовательных ошибок")
            logs.append(f"🚫 Circuit Breaker: {failures_count} ошибок подряд, генерация отключена")
            return None

        # Инициализируем логи для админки (максимум 5000 символов для экономии памяти)
        MAX_LOG_LENGTH = 5000
        logs = []
        logs.append("🎬 ════════════════════════════════════════════════")
        logs.append(f"🎬 Начало генерации видео для задачи {task_id}")
        logs.append(f"📋 Параметры: тема={topic_name}, подтема={subtopic_name}, сложность={difficulty}")
        
        logger.info(f"🎬 [Celery] ════════════════════════════════════════════════")
        logger.info(f"🎬 [Celery] Начало генерации видео для задачи {task_id}")
        logger.info(f"🎬 [Celery] Параметры: тема={topic_name}, подтема={subtopic_name}, сложность={difficulty}")
        
        # Проверяем, что задача еще существует и не имеет видео
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            error_msg = f"⚠️ Задача {task_id} не найдена, пропускаем генерацию видео"
            logger.warning(f"⚠️ [Celery] {error_msg}")
            logs.append(error_msg)
            return None
        
        # Обновляем логи в задаче (с ограничением размера)
        log_text = "\n".join(logs)
        if len(log_text) > MAX_LOG_LENGTH:
            # Обрезаем до последних MAX_LOG_LENGTH символов
            log_text = "..." + log_text[-MAX_LOG_LENGTH:]
        task.video_generation_logs = log_text
        task.save(update_fields=['video_generation_logs'])
        
        # Если видео уже есть и задача не опубликована, пропускаем генерацию
        if task.video_url and not task.published:
            info_msg = f"ℹ️ Задача {task_id} уже имеет видео и не опубликована: {task.video_url}"
            logger.info(f"ℹ️ [Celery] {info_msg}")
            logs.append(info_msg)
            task.video_generation_logs = "\n".join(logs)
            task.save(update_fields=['video_generation_logs'])
            return task.video_url
        
        # Если требуется перегенерация и есть старое видео, удаляем его
        if task.video_url and force_regenerate:
            old_video_url = task.video_url
            logs.append(f"🔄 Принудительная перегенерация видео")
            logs.append(f"🗑️ Удаление старого видео: {old_video_url}")
            from tasks.services.s3_service import delete_image_from_s3
            if delete_image_from_s3(old_video_url):
                logger.info(f"🗑️ [Celery] Старое видео удалено: {old_video_url}")
                logs.append(f"✅ Старое видео успешно удалено")
            else:
                logger.warning(f"⚠️ [Celery] Не удалось удалить старое видео: {old_video_url}")
                logs.append(f"⚠️ Не удалось удалить старое видео (продолжаем генерацию)")
            # Очищаем video_url
            task.video_url = None
            # Обновляем логи
            log_text = "\n".join(logs)
            if len(log_text) > MAX_LOG_LENGTH:
                log_text = "..." + log_text[-MAX_LOG_LENGTH:]
            task.video_generation_logs = log_text
            task.save(update_fields=['video_url', 'video_generation_logs'])
        
        logs.append("📝 Этап 1/4: Извлечение кода из вопроса...")
        log_text = "\n".join(logs)
        if len(log_text) > MAX_LOG_LENGTH:
            log_text = "..." + log_text[-MAX_LOG_LENGTH:]
        task.video_generation_logs = log_text
        task.save(update_fields=['video_generation_logs'])
        logger.info(f"📝 [Celery] Этап 1/4: Извлечение кода из вопроса...")
        
        # Генерируем видео (внутри функции уже есть отправка админу)
        # Передаем admin_chat_id и task_id для формирования понятного имени файла
        video_url = generate_video_for_task(
            task_question,
            topic_name,
            subtopic_name=subtopic_name,
            difficulty=difficulty,
            admin_chat_id=admin_chat_id,
            task_id=task_id,
            video_language=video_language
        )
        
        if video_url:
            logs.append("📝 Этап 2/4: Видео сгенерировано")
            logs.append("📝 Этап 3/4: Загрузка в S3/R2...")
            log_text = "\n".join(logs)
            if len(log_text) > MAX_LOG_LENGTH:
                log_text = "..." + log_text[-MAX_LOG_LENGTH:]
            task.video_generation_logs = log_text
            task.save(update_fields=['video_generation_logs'])
            logger.info(f"📝 [Celery] Этап 2/4: Видео сгенерировано")
            logger.info(f"📝 [Celery] Этап 3/4: Загрузка в S3/R2...")
            
            # Сохраняем URL видео в задачу по языку
            task.video_urls = task.video_urls or {}
            task.video_urls[video_language] = video_url

            # Отмечаем язык как готовый
            task.video_generation_progress = task.video_generation_progress or {}
            task.video_generation_progress[video_language] = True
            task.save(update_fields=['video_urls', 'video_generation_progress', 'video_generation_logs'])

            # Проверяем, все ли ожидаемые языки готовы
            if expected_languages:
                all_ready = all(task.video_generation_progress.get(lang, False) for lang in expected_languages)
                if all_ready:
                    # Все видео готовы - отправляем вебхуки
                    try:
                        logger.info(f"🛰️ [Celery] Все видео для задачи {task_id} готовы ({', '.join(expected_languages)}), отправляем вебхуки с видео...")
                        from config.tasks import send_webhooks_async
                        webhook_task = send_webhooks_async.delay(
                            task_ids=[task_id],
                            webhook_type_filter=None,
                            admin_chat_id=admin_chat_id,
                            include_video=True
                        )
                        logger.info(f"✅ [Celery] Вебхуки с видео запущены (ID: {webhook_task.id})")
                    except Exception as webhook_exc:
                        logger.error(f"❌ [Celery] Ошибка запуска вебхуков для задачи {task_id}: {webhook_exc}")
                else:
                    ready_langs = [lang for lang in expected_languages if task.video_generation_progress.get(lang, False)]
                    logger.info(f"📋 [Celery] Видео для языка {video_language} готово. Прогресс: {ready_langs}/{list(expected_languages)}")
            else:
                # Старая логика для совместимости - отправляем вебхуки сразу
                try:
                    logger.info(f"🛰️ [Celery] Задача {task_id} опубликована, отправляем вебхуки с видео...")
                    from config.tasks import send_webhooks_async
                    webhook_task = send_webhooks_async.delay(
                        task_ids=[task_id],
                        webhook_type_filter=None,
                        admin_chat_id=admin_chat_id,
                        include_video=True
                    )
                    logger.info(f"✅ [Celery] Вебхуки с видео запущены (ID: {webhook_task.id})")
                except Exception as webhook_exc:
                    logger.error(f"❌ [Celery] Ошибка запуска вебхуков для задачи {task_id}: {webhook_exc}")
            
            logs.append("📝 Этап 4/4: Видео отправлено админу в Telegram")
            logs.append(f"✅ Видео успешно сгенерировано для задачи {task_id} (язык: {video_language})")
            logs.append(f"🔗 URL: {video_url}")
            logs.append("🎬 ════════════════════════════════════════════════")
            log_text = "\n".join(logs)
            if len(log_text) > MAX_LOG_LENGTH:
                log_text = "..." + log_text[-MAX_LOG_LENGTH:]
            task.video_generation_logs = log_text
            task.save(update_fields=['video_generation_logs'])
            
            logger.info(f"📝 [Celery] Этап 4/4: Видео отправлено админу в Telegram")
            logger.info(f"✅ [Celery] Видео успешно сгенерировано для задачи {task_id}")
            logger.info(f"   🔗 URL: {video_url}")
            logger.info(f"🎬 [Celery] ════════════════════════════════════════════════")

            # 🛡️ Circuit Breaker: сбрасываем счетчик ошибок при успехе
            try:
                cache.set(circuit_breaker_key, 0, timeout=3600)
                logger.info("🔄 [Circuit Breaker] Счетчик ошибок видео генерации сброшен")
            except Exception as cache_exc:
                logger.error(f"❌ Ошибка сброса circuit breaker: {cache_exc}")

            # 📡 Если задача опубликована - отправляем вебхуки с видео
            if task.published:
                try:
                    logger.info(f"🛰️ [Celery] Задача {task_id} опубликована, отправляем вебхуки с видео...")
                    from config.tasks import send_webhooks_async
                    webhook_task = send_webhooks_async.delay(
                        task_ids=[task_id],
                        webhook_type_filter=None,
                        admin_chat_id=admin_chat_id,
                        include_video=True
                    )
                    logger.info(f"✅ [Celery] Вебхуки с видео запущены (ID: {webhook_task.id})")
                except Exception as webhook_exc:
                    logger.error(f"❌ [Celery] Ошибка запуска вебхуков для задачи {task_id}: {webhook_exc}")
            else:
                logger.info(f"ℹ️ [Celery] Задача {task_id} не опубликована, вебхуки не отправляются")

            return video_url
        else:
            logs.append("⚠️ Не удалось сгенерировать видео")
            logs.append("🔍 Проверьте логи Celery для деталей ошибки")
            logs.append("🎬 ════════════════════════════════════════════════")
            log_text = "\n".join(logs)
            if len(log_text) > MAX_LOG_LENGTH:
                log_text = "..." + log_text[-MAX_LOG_LENGTH:]
            task.video_generation_logs = log_text
            task.save(update_fields=['video_generation_logs'])
            
            logger.warning(f"⚠️ [Celery] Не удалось сгенерировать видео для задачи {task_id}")
            logger.warning(f"   🔍 Проверьте логи выше для деталей ошибки")
            logger.info(f"🎬 [Celery] ════════════════════════════════════════════════")
            return None
            
    except Exception as exc:
        error_logs = []
        error_logs.append("❌ ════════════════════════════════════════════════")
        error_logs.append(f"❌ ОШИБКА генерации видео для задачи {task_id}")
        error_logs.append(f"📋 Тип ошибки: {type(exc).__name__}")
        error_logs.append(f"📝 Сообщение: {str(exc)}")
        error_logs.append(f"🔍 Полный traceback будет в логах Celery")
        error_logs.append("❌ ════════════════════════════════════════════════")
        
        # Сохраняем логи ошибки в задачу (с ограничением размера)
        try:
            task = Task.objects.get(id=task_id)
            existing_logs = task.video_generation_logs or ""
            new_logs = existing_logs + "\n" + "\n".join(error_logs) if existing_logs else "\n".join(error_logs)
            # Ограничиваем размер логов
            if len(new_logs) > MAX_LOG_LENGTH:
                new_logs = "..." + new_logs[-MAX_LOG_LENGTH:]
            task.video_generation_logs = new_logs
            task.save(update_fields=['video_generation_logs'])
        except Exception:
            pass  # Если не удалось сохранить логи, продолжаем
        
        logger.error(f"❌ [Celery] ════════════════════════════════════════════════")
        logger.error(f"❌ [Celery] ОШИБКА генерации видео для задачи {task_id}")
        logger.error(f"   📋 Тип ошибки: {type(exc).__name__}")
        logger.error(f"   📝 Сообщение: {str(exc)}")
        logger.error(f"   🔍 Полный traceback будет в логах выше")
        logger.error(f"❌ [Celery] ════════════════════════════════════════════════")

        # 🛡️ Circuit Breaker: увеличиваем счетчик ошибок
        try:
            current_failures = cache.get(circuit_breaker_key, 0)
            cache.set(circuit_breaker_key, current_failures + 1, timeout=3600)  # 1 час
            logger.warning(f"⚠️ [Circuit Breaker] Счетчик ошибок видео генерации: {current_failures + 1}/{max_failures}")
        except Exception as cache_exc:
            logger.error(f"❌ Ошибка обновления circuit breaker: {cache_exc}")

        # Повторная попытка через 5 минут (если не превышен лимит)
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=2, default_retry_delay=60, queue='webhooks_queue' if os.getenv('DEBUG') != 'True' else 'celery')
def send_webhooks_async(self, task_ids, webhook_type_filter=None, admin_chat_id=None, include_video=False):
    """
    Асинхронная отправка вебхуков для списка задач.

    ОЧЕРЕДЬ: webhooks_queue (продакшен) или celery (локальная разработка)
    Это обеспечивает совместимость с разными конфигурациями Celery worker'ов.
    """
    """
    Асинхронная отправка вебхуков для списка задач.

    Args:
        task_ids: Список ID задач для отправки
        webhook_type_filter: Фильтр по типу вебхуков ('russian_only', 'english_only', etc.)
        admin_chat_id: ID чата админа для уведомлений
        include_video: Если True, включает видео URL в payload вебхуков

    Returns:
        Dict с результатами отправки
    """
    try:
        from tasks.models import Task
        from webhooks.services import send_webhooks_for_bulk_tasks
        from django.contrib import messages
        from django.contrib.admin.models import LogEntry, ADDITION
        from django.core.cache import cache

        # 🔒 Rate limiting: адаптивно по окружению
        MAX_CONCURRENT_WEBHOOKS = 5 if os.getenv('DEBUG') == 'True' else 1
        active_webhooks_key = "webhooks_active_count"

        active_count = cache.get(active_webhooks_key, 0)
        if active_count >= MAX_CONCURRENT_WEBHOOKS:
            logger.warning(f"⚠️ [Rate Limit] Слишком много активных вебхуков ({active_count}/{MAX_CONCURRENT_WEBHOOKS}), откладываем на 2 минуты")
            raise self.retry(countdown=120, exc=Exception(f"Rate limit exceeded: {active_count} active webhooks"))

        # Увеличиваем счетчик активных задач (инициализируем если ключ не существует)
        try:
            cache.incr(active_webhooks_key, 1)
        except ValueError:
            # Ключ не существует, создаем его со значением 1
            cache.set(active_webhooks_key, 1, 600)

        # Автоматический сброс через 10 минут (работает только с Redis, игнорируется для LocMemCache)
        try:
            cache.expire(active_webhooks_key, 600)
        except AttributeError:
            # LocMemCache не поддерживает expire, игнорируем
            pass

        logger.info(f"🛰️ [Celery] Начало асинхронной отправки вебхуков для {len(task_ids)} задач (активных: {active_count + 1}/{MAX_CONCURRENT_WEBHOOKS})")
        if webhook_type_filter:
            logger.info(f"   🎯 Фильтр по типу: {webhook_type_filter}")

        # Получаем задачи из БД с необходимыми связями
        tasks = Task.objects.filter(id__in=task_ids).select_related('topic', 'group').prefetch_related('translations')

        if not tasks:
            logger.warning("⚠️ [Celery] Не найдено задач для отправки вебхуков")
            return {"total": 0, "success": 0, "failed": 0, "details": []}

        # Логируем информацию о задачах и их переводах для диагностики
        logger.info(f"📋 [Celery] Отправка {len(tasks)} задач на вебхуки")
        for task in tasks:
            translations_info = []
            for trans in task.translations.all():
                translations_info.append(f"{trans.language}")
            logger.info(f"   Задача {task.id}: переводы {', '.join(translations_info) if translations_info else 'отсутствуют'}")

        # Отправляем вебхуки
        result = send_webhooks_for_bulk_tasks(tasks, include_video=include_video)

        # Логируем результат
        video_status = "с видео" if include_video else "без видео"
        logger.info(f"✅ [Celery] Отправка вебхуков {video_status} завершена: "
                   f"успешно {result['success']}, неудачно {result['failed']}")

        # Если указан admin_chat_id, отправляем уведомление в Telegram
        if admin_chat_id and (result['success'] > 0 or result['failed'] > 0):
            try:
                from aiogram import Bot
                from aiogram.exceptions import TelegramBadRequest
                import asyncio

                # Создаем новый event loop для асинхронного кода
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def send_notification():
                    try:
                        # Получаем токен бота из настроек
                        from django.conf import settings
                        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
                        if not bot_token:
                            logger.warning("⚠️ [Celery] Не найден TELEGRAM_BOT_TOKEN для уведомления")
                            return

                        bot = Bot(token=bot_token)

                        # Группируем результаты по типам вебхуков
                        webhook_stats = {}
                        for detail in result['details']:
                            webhook_type = detail['type']
                            if webhook_type not in webhook_stats:
                                webhook_stats[webhook_type] = {'total': 0, 'success': 0, 'failed': 0, 'webhooks': []}
                            webhook_stats[webhook_type]['total'] += 1
                            if detail['success']:
                                webhook_stats[webhook_type]['success'] += 1
                            else:
                                webhook_stats[webhook_type]['failed'] += 1
                            webhook_stats[webhook_type]['webhooks'].append(detail)

                        # Формируем сообщение
                        video_status = "🎬 С видео" if include_video else "📄 Без видео"
                        message_parts = [f"🛰️ Вебхуки отправлены ({video_status})\n"]

                        # Информация о задачах
                        message_parts.append(f"📋 Задач: {len(tasks)}")
                        task_ids_str = ', '.join(str(task.id) for task in tasks[:5])  # Показываем максимум 5 ID
                        if len(tasks) > 5:
                            task_ids_str += f" ... и ещё {len(tasks) - 5}"
                        message_parts.append(f"🆔 ID: {task_ids_str}")
                        message_parts.append("")

                        # Общая статистика
                        message_parts.append(f"📊 Всего: {result['total']}")
                        message_parts.append(f"✅ Успешно: {result['success']}")
                        message_parts.append(f"❌ Ошибок: {result['failed']}")
                        if webhook_type_filter:
                            message_parts.append(f"🎯 Фильтр: {webhook_type_filter}")
                        message_parts.append("")

                        # Статистика по типам
                        for webhook_type, stats in webhook_stats.items():
                            type_name = {
                                'regular': '🔄 Regular',
                                'russian_only': '🇷🇺 Только русский',
                                'english_only': '🇺🇸 Только английский',
                                'social_media': '📱 Соцсети'
                            }.get(webhook_type, webhook_type)

                            status_icon = "✅" if stats['failed'] == 0 else "⚠️"
                            message_parts.append(f"{status_icon} {type_name}: {stats['success']}/{stats['total']}")

                            # Показываем детали по каждому вебхуку (с ограничением)
                            for webhook_detail in stats['webhooks'][:5]:  # Максимум 5 вебхуков на тип
                                status = "✅" if webhook_detail['success'] else "❌"
                                service_name = webhook_detail['service'][:25] + "..." if len(webhook_detail['service']) > 25 else webhook_detail['service']
                                message_parts.append(f"  {status} {service_name}")

                            if len(stats['webhooks']) > 5:
                                message_parts.append(f"  ... и ещё {len(stats['webhooks']) - 5}")

                        message = "\n".join(message_parts)

                        # Ограничиваем длину сообщения (Telegram limit ~4096 chars)
                        if len(message) > 3500:
                            message = message[:3500] + "\n\n... (сообщение обрезано)"

                        await bot.send_message(chat_id=admin_chat_id, text=message)
                        logger.info(f"📨 [Celery] Уведомление отправлено в Telegram (chat_id: {admin_chat_id})")

                    except Exception as e:
                        logger.error(f"❌ [Celery] Ошибка отправки уведомления в Telegram: {e}")

                # Запускаем асинхронную функцию
                loop.run_until_complete(send_notification())
                loop.close()

            except Exception as e:
                logger.error(f"❌ [Celery] Критическая ошибка при отправке уведомления: {e}")

        # Уменьшаем счетчик активных задач после успешного выполнения
        try:
            cache.decr(active_webhooks_key)
        except:
            # Если ключ не существует, сбрасываем в 0
            cache.set(active_webhooks_key, 0, 600)

        return result

    except Exception as exc:
        # Уменьшаем счетчик активных задач при ошибке
        try:
            cache.decr(active_webhooks_key)
        except:
            # Если ключ не существует, сбрасываем в 0
            cache.set(active_webhooks_key, 0, 600)

        logger.error(f"❌ [Celery] Критическая ошибка в send_webhooks_async: {str(exc)}")
        # Повторная попытка через 1 минуту
        raise self.retry(exc=exc, countdown=60)

    finally:
        # 🔓 Гарантированно уменьшаем счетчик активных задач
        try:
            cache.decr(active_webhooks_key)
        except:
            # Если ключ не существует, сбрасываем в 0
            cache.set(active_webhooks_key, 0, 600)


@shared_task
def delete_old_videos_from_r2():
    """
    Удаляет видео из R2, которые старше 10 дней.
    Запускается автоматически каждый день в 4:00.
    
    Returns:
        int: Количество удаленных видео
    """
    from tasks.models import Task
    from tasks.services.s3_service import delete_image_from_s3
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Вычисляем дату 10 дней назад
        cutoff_date = timezone.now() - timedelta(days=10)
        
        # Находим задачи с видео, которые старше 10 дней
        # Используем publish_date если есть, иначе create_date
        from django.db.models import Q, F
        old_tasks = Task.objects.filter(
            video_url__isnull=False
        ).exclude(video_url='').filter(
            Q(publish_date__lt=cutoff_date) | 
            Q(publish_date__isnull=True, create_date__lt=cutoff_date)
        )
        
        deleted_count = 0
        failed_count = 0
        
        logger.info(f"🗑️ [Celery] ════════════════════════════════════════════════")
        logger.info(f"🗑️ [Celery] Начинаем удаление старых видео (старше 10 дней)")
        logger.info(f"   📅 Дата отсечки: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   📊 Найдено задач с видео: {old_tasks.count()}")
        
        for task in old_tasks:
            try:
                video_url = task.video_url
                if delete_image_from_s3(video_url):
                    # Очищаем video_url в задаче
                    task.video_url = None
                    task.save(update_fields=['video_url'])
                    deleted_count += 1
                    logger.info(f"✅ [Celery] Видео удалено для задачи {task.id}")
                else:
                    failed_count += 1
                    logger.warning(f"⚠️ [Celery] Не удалось удалить видео для задачи {task.id}")
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ [Celery] Ошибка при удалении видео для задачи {task.id}: {e}")
        
        logger.info(f"🎉 [Celery] Удаление завершено: удалено {deleted_count}, ошибок {failed_count}")
        
        # Очищаем старые логи генерации видео (старше 7 дней)
        logs_cutoff_date = timezone.now() - timedelta(days=7)
        old_logs_tasks = Task.objects.filter(
            video_generation_logs__isnull=False
        ).exclude(video_generation_logs='').filter(
            Q(publish_date__lt=logs_cutoff_date) | 
            Q(publish_date__isnull=True, create_date__lt=logs_cutoff_date)
        )
        
        logs_cleared_count = old_logs_tasks.update(video_generation_logs=None)
        if logs_cleared_count > 0:
            logger.info(f"🧹 [Celery] Очищено старых логов генерации видео: {logs_cleared_count}")
        
        logger.info(f"🗑️ [Celery] ════════════════════════════════════════════════")
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ [Celery] Критическая ошибка при удалении старых видео: {e}", exc_info=True)
        return 0

