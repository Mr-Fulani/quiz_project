"""
Картинка задачи — только для соцсетей (Pinterest, Facebook, вебхуки Make.com) и только для английских задач.

На сайте, в Mini App и Telegram вопрос показывается текстом, картинка там не нужна.
Картинка генерируется при импорте английской задачи или по требованию при публикации в соцсети.
"""
import logging

from tasks.models import Task
from tasks.services.image_generation_service import generate_image_for_task, get_tenant_logo_path
from tasks.services.s3_service import upload_image_to_s3

logger = logging.getLogger(__name__)

# Языки задач, для которых делаются картинки
SOCIAL_IMAGE_LANGUAGES = ('en',)
NOT_ENGLISH_REASON = 'Картинки для соцсетей делаются только для английских задач'


def needs_social_image(translation):
    return bool(translation) and (translation.language or '').lower() in SOCIAL_IMAGE_LANGUAGES


def generate_task_image(task, translation, image_theme=None):
    """
    Генерирует картинку задачи, загружает в хранилище и сохраняет image_url.
    Возвращает текст ошибки или None. Сохраняет через update(), чтобы не запускать сигналы Task.
    """
    tenant = task.tenant
    theme = image_theme or (tenant.image_theme if tenant else 'code')
    topic_name = task.topic.name if task.topic_id else 'python'
    logger.info(f"🎨 Генерация картинки для задачи {task.id} (тема: {theme}, язык: {topic_name})")

    image = generate_image_for_task(
        translation.question,
        topic_name,
        theme=theme,
        custom_logo_path=get_tenant_logo_path(tenant),
    )
    if not image:
        Task.objects.filter(pk=task.pk).update(error=True)
        task.error = True
        return f"Задача {task.id}: не удалось сгенерировать картинку"

    subtopic_name = task.subtopic.name if task.subtopic_id else 'general'
    image_name = f"{topic_name}_{subtopic_name}_{translation.language or 'unknown'}_{task.id}.png"
    image_name = image_name.replace(" ", "_").lower()
    image_url = upload_image_to_s3(
        image, image_name,
        tenant_slug=tenant.slug if tenant else None,
        topic_slug=topic_name,
    )
    if not image_url:
        Task.objects.filter(pk=task.pk).update(error=True)
        task.error = True
        return f"Задача {task.id}: не удалось загрузить картинку в хранилище"

    Task.objects.filter(pk=task.pk).update(image_url=image_url, error=False)
    task.image_url, task.error = image_url, False
    logger.info(f"✅ Задача {task.id}: картинка загружена: {image_url}")
    return None


def ensure_social_image(task, translation):
    """
    URL картинки для соцсетей: существующая или новая. В соцсети идут только английские задачи.
    Возвращает (url, None) или (None, причина).
    """
    if not needs_social_image(translation):
        return None, NOT_ENGLISH_REASON
    if task.image_url:
        return task.image_url, None
    error = generate_task_image(task, translation)
    return (task.image_url, None) if not error else (None, error)
