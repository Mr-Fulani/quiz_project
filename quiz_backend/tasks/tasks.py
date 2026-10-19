"""
Фоновые (Celery) задачи админки задач: публикация в Telegram и соцсети, генерация изображений.

Админ-экшены только ставят задачу в очередь: синхронный цикл с паузами 3–6 с между
публикациями упирался в таймаут nginx (504). Результат — в логах воркера и в полях
задач (published_*, publish_date, image_url, error), как у генерации видео.

ОЧЕРЕДЬ: celery (по умолчанию) — её слушает основной worker.
"""
import logging
import random
import time

from celery import shared_task
from django.utils import timezone

from .models import Task
from .services.image_generation_service import generate_image_for_task, get_tenant_logo_path
from .services.s3_service import upload_image_to_s3
from .services.telegram_service import publish_task_to_telegram

logger = logging.getLogger(__name__)

# Пачка задач с паузами 3–6 с между публикациями может идти дольше глобального лимита (30 мин)
PUBLICATION_SOFT_TIME_LIMIT = 2 * 60 * 60
PUBLICATION_TIME_LIMIT = PUBLICATION_SOFT_TIME_LIMIT + 5 * 60


def _tasks_in_order(task_ids):
    """Задачи по id в порядке task_ids (порядок публикации задаёт админка)."""
    tasks = Task.objects.filter(id__in=task_ids).select_related(
        'tenant', 'topic', 'subtopic', 'group'
    ).prefetch_related('translations')
    by_id = {task.id: task for task in tasks}
    return [by_id[task_id] for task_id in task_ids if task_id in by_id]


def _pause_between_task_publications(task_id):
    """
    Вставляет случайную паузу между публикациями задач (чтобы не воспринималось как спам).
    """
    pause_seconds = random.randint(3, 6)
    logger.info(f"⏸️ Пауза {pause_seconds} сек перед следующей задачей (последняя: {task_id})")
    time.sleep(pause_seconds)


def _generate_and_upload_image(task, translation, image_theme):
    """
    Генерирует изображение задачи, загружает в S3 и сохраняет image_url.
    Возвращает текст ошибки или None при успехе; при ошибке выставляет task.error.
    """
    topic_name = task.topic.name if task.topic else 'python'
    logger.info(f"🎨 Генерация изображения для задачи {task.id} (тема: {image_theme}, язык: {topic_name})")

    image = generate_image_for_task(
        translation.question,
        topic_name,
        theme=image_theme,
        custom_logo_path=get_tenant_logo_path(task.tenant),
    )
    if not image:
        task.error = True
        task.save(update_fields=['error'])
        return f"Задача {task.id}: не удалось сгенерировать изображение"

    # Формируем имя файла в формате, как в боте
    language_code = translation.language or "unknown"
    subtopic_name = task.subtopic.name if task.subtopic else 'general'
    image_name = f"{task.topic.name}_{subtopic_name}_{language_code}_{task.id}.png"
    image_name = image_name.replace(" ", "_").lower()

    logger.info(f"☁️ Загрузка в S3: {image_name}...")
    image_url = upload_image_to_s3(image, image_name)
    if not image_url:
        task.error = True
        task.save(update_fields=['error'])
        return f"Задача {task.id}: не удалось загрузить в S3"

    task.image_url = image_url
    task.error = False  # Сбрасываем ошибку если генерация успешна
    task.save(update_fields=['image_url', 'error'])
    logger.info(f"✅ Задача {task.id}: изображение загружено в S3: {image_url}")
    return None


@shared_task(bind=True)
def generate_task_images_async(self, task_ids, image_theme='code'):
    """Генерирует изображения для задач и загружает их в S3."""
    generated_count = 0
    errors = []
    logger.info(f"📊 Начинаем генерацию изображений ({image_theme}) для {len(task_ids)} задач...")

    for task in _tasks_in_order(task_ids):
        translation = task.translations.first()
        if not translation:
            errors.append(f"Задача {task.id}: отсутствуют переводы")
            logger.warning(f"⚠️ {errors[-1]}")
            continue
        try:
            error = _generate_and_upload_image(task, translation, image_theme)
        except Exception as e:
            task.error = True
            task.save(update_fields=['error'])
            error = f"Задача {task.id}: {e}"
            logger.error(f"Исключение при генерации изображения для задачи {task.id}: {e}", exc_info=True)
        if error:
            errors.append(error)
            logger.error(f"❌ {error}")
        else:
            generated_count += 1

    logger.info(f"🎉 ЗАВЕРШЕНО: Сгенерировано {generated_count}, ошибок {len(errors)}")
    return {'generated': generated_count, 'errors': errors}


def _send_webhooks_after_publication(task_ids):
    """
    Запускает вебхуки (и при языковых вебхуках — генерацию видео) для опубликованных задач.
    """
    from accounts.models import TelegramAdmin
    from config.tasks import generate_video_for_task_async, send_webhooks_async
    from webhooks.models import Webhook

    # Обновляем задачи из БД, чтобы подтянуть `TaskPoll`
    refreshed_tasks = list(
        Task.objects.filter(id__in=task_ids)
        .select_related('topic', 'subtopic')
        .prefetch_related('translations__taskpoll_set')
    )

    # Получаем admin_chat_id для уведомлений о результатах
    admin_chat_id = None
    try:
        admin = TelegramAdmin.objects.filter(is_active=True).first()
        if admin:
            admin_chat_id = str(admin.telegram_id)
    except Exception:
        pass  # Не критично, если не найдется

    # Анализируем активные вебхуки для определения стратегии генерации видео
    active_webhooks = list(Webhook.objects.filter(is_active=True))
    webhook_types = set(webhook.webhook_type for webhook in active_webhooks)
    needs_video_generation = bool(webhook_types.intersection({'russian_only', 'english_only'}))

    if not active_webhooks:
        logger.info("✅ Задачи опубликованы. Нет активных вебхуков - генерация видео пропущена")
    elif not needs_video_generation:
        # Только regular вебхуки - отправляем без видео
        webhook_task = send_webhooks_async.delay(
            task_ids=[task.id for task in refreshed_tasks],
            webhook_type_filter=None,
            admin_chat_id=admin_chat_id,
            include_video=False
        )
        logger.info(f"🛰️ Regular вебхуки отправлены без видео (ID: {webhook_task.id})")
    else:
        # Есть языковые вебхуки - генерируем видео для нужных языков,
        # вебхуки уйдут с видео после завершения генерации
        languages_to_generate = set()
        if 'russian_only' in webhook_types:
            languages_to_generate.add('ru')
        if 'english_only' in webhook_types:
            languages_to_generate.add('en')

        for task in refreshed_tasks:
            # Отмечаем какие языки планируются к генерации
            task.video_generation_progress = {lang: False for lang in languages_to_generate}
            task.save(update_fields=['video_generation_progress'])

            for language in languages_to_generate:
                translation = task.translations.filter(language=language).first()
                if translation:
                    generate_video_for_task_async.delay(
                        task_id=task.id,
                        task_question=translation.question,
                        topic_name=task.topic.name,
                        subtopic_name=task.subtopic.name if task.subtopic else None,
                        difficulty=task.difficulty,
                        admin_chat_id=admin_chat_id,
                        video_language=language,
                        expected_languages=list(languages_to_generate)
                    )

        video_count = len(refreshed_tasks) * len(languages_to_generate)
        logger.info(f"🎬 Запущена генерация {video_count} видео для языков: {', '.join(languages_to_generate)}")


@shared_task(bind=True, soft_time_limit=PUBLICATION_SOFT_TIME_LIMIT, time_limit=PUBLICATION_TIME_LIMIT)
def publish_tasks_to_telegram_async(self, task_ids):
    """
    Публикует задачи в Telegram (каждый перевод — в канал своего языка) ботом тенанта задачи.
    Если у задачи нет изображения, сначала генерирует его. Между задачами — пауза 3–6 с.
    После публикации запускает вебхуки / генерацию видео.
    """
    from platforms.models import TelegramGroup

    tasks = _tasks_in_order(task_ids)
    published_count = 0
    errors = []
    published_by_language = {}
    published_task_ids = []

    logger.info(f"📊 Публикация в Telegram: {len(tasks)} задач")

    for index, task in enumerate(tasks):
        try:
            # Получаем ВСЕ переводы задачи
            translations = task.translations.all()
            if not translations:
                errors.append(f"Задача {task.id}: отсутствуют переводы")
                logger.warning(f"Пропуск задачи {task.id}: нет переводов")
                continue

            # Автоматическая генерация изображения, если его нет
            if not task.image_url:
                tenant = task.tenant
                image_theme = 'islamic' if tenant and tenant.slug == 'iqro-forum' else 'code'
                try:
                    error = _generate_and_upload_image(task, translations[0], image_theme)
                except Exception as e:
                    task.error = True
                    task.save(update_fields=['error'])
                    error = f"Задача {task.id}: {e}"
                    logger.error(f"Исключение при генерации изображения для задачи {task.id}: {e}", exc_info=True)
                if error:
                    errors.append(error)
                    logger.error(f"❌ {error}")
                    continue

            # Публикуем каждый перевод в свой канал
            task_published_any_language = False
            for translation in translations:
                language = translation.language.upper()

                telegram_group = TelegramGroup.objects.filter(
                    topic_id=task.topic,
                    language=translation.language
                ).first()

                if not telegram_group:
                    errors.append(
                        f"Задача {task.id} ({language}): не найдена Telegram группа для языка {language} "
                        f"(topic_id={task.topic.id if task.topic else None})"
                    )
                    logger.warning(f"⚠️ {errors[-1]}")
                    continue

                logger.info(f"🚀 Публикуем задачу {task.id} ({language}) в канал {telegram_group.group_name}...")
                result = publish_task_to_telegram(
                    task=task,
                    translation=translation,
                    telegram_group=telegram_group
                )
                for log in result.get('detailed_logs', []):
                    logger.info(log)

                if result['success']:
                    task_published_any_language = True
                    published_by_language[language] = published_by_language.get(language, 0) + 1
                else:
                    errors.append(f"Задача {task.id} ({language}): {', '.join(result['errors'])}")
                    logger.error(f"❌ {errors[-1]}")

            if task_published_any_language:
                task.published = True
                task.published_telegram = True
                task.published_website = True
                task.published_mini_app = True
                task.publish_date = timezone.now()
                task.error = False
                update_fields = ['published', 'published_telegram', 'published_website', 'published_mini_app', 'publish_date', 'error']
                if not task.message_id:
                    update_fields.append('message_id')
                if not task.group:
                    update_fields.append('group')
                task.save(update_fields=update_fields)
                published_count += 1
                published_task_ids.append(task.id)
            else:
                task.error = True
                task.save(update_fields=['error'])
                errors.append(f"Задача {task.id}: не удалось опубликовать ни один перевод")
                logger.error(f"❌ {errors[-1]}")

        except Exception as e:
            task.error = True
            task.save(update_fields=['error'])
            errors.append(f"Задача {task.id}: {e}")
            logger.error(f"Исключение при публикации задачи {task.id}: {e}", exc_info=True)
        finally:
            if index < len(tasks) - 1:
                _pause_between_task_publications(task.id)

    if published_task_ids:
        try:
            _send_webhooks_after_publication(published_task_ids)
        except Exception as exc:
            logger.exception("Ошибка при отправке сводного вебхука: %s", exc)

    lang_stats = ", ".join(f"{lang}: {count}" for lang, count in sorted(published_by_language.items()))
    logger.info(f"🎉 Опубликовано {published_count} задач из {len(tasks)} ({lang_stats}), ошибок: {len(errors)}")
    return {'published': published_count, 'total': len(tasks), 'errors': errors}


@shared_task(bind=True, soft_time_limit=PUBLICATION_SOFT_TIME_LIMIT, time_limit=PUBLICATION_TIME_LIMIT)
def publish_tasks_to_social_async(self, task_ids, platform=None, require_video=False):
    """
    Публикует задачи в соцсети: во все активные (platform=None) или в одну платформу.
    require_video=True — для Reels с автоматическим репостом (нужно видео, а не изображение).
    """
    from .services.social_media_service import publish_to_platform, publish_to_social_media

    target = platform or 'все соцсети'
    published_count = 0
    tasks = _tasks_in_order(task_ids)
    logger.info(f"📊 Начинаем публикацию {len(tasks)} задач в {target}...")

    for task in tasks:
        try:
            if require_video and not task.video_url:
                logger.warning(f"⚠️ Задача {task.id}: нет видео, пропускаем")
                continue
            if not require_video and not task.image_url:
                logger.warning(f"⚠️ Задача {task.id}: нет изображения, пропускаем")
                continue

            translation = task.translations.first()
            if not translation:
                logger.warning(f"⚠️ Задача {task.id}: нет переводов, пропускаем")
                continue

            if platform:
                result = publish_to_platform(task, translation, platform)
                success = bool(result.get('success'))
            else:
                result = publish_to_social_media(task, translation)
                success = result['success'] > 0

            if success:
                published_count += 1
                task.published = True
                if not task.publish_date:
                    task.publish_date = timezone.now()
                task.save(update_fields=['published', 'publish_date'])
                logger.info(f"✅ Задача {task.id}: опубликована в {target}: {result}")
            else:
                logger.error(f"❌ Задача {task.id}: ошибка публикации в {target}: {result.get('error') or result}")

        except Exception as e:
            logger.error(f"Ошибка публикации задачи {task.id} в {target}: {e}", exc_info=True)

    logger.info(f"📊 Публикация в {target} завершена: {published_count}/{len(tasks)} задач опубликовано")
    return {'published': published_count, 'total': len(tasks)}
