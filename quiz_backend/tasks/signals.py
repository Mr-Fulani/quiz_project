"""
Сигналы для автоматической очистки связанных ресурсов при удалении задач.
"""
import logging
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from .models import Task
from .services.s3_service import delete_image_from_s3

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=Task)
def delete_related_tasks_and_images(sender, instance, **kwargs):
    """
    При удалении задачи удаляет все связанные задачи по translation_group_id
    и их изображения из S3.
    
    Args:
        sender: Класс модели (Task)
        instance: Удаляемый экземпляр Task
        **kwargs: Дополнительные аргументы сигнала
    """
    try:
        translation_group_id = instance.translation_group_id
        
        if not translation_group_id:
            logger.warning(f"Задача {instance.id} не имеет translation_group_id")
            return
        
        # Находим все связанные задачи
        related_tasks = Task.objects.filter(
            translation_group_id=translation_group_id
        ).exclude(id=instance.id)
        
        # Собираем URL изображений для удаления
        image_urls = []
        if instance.image_url:
            image_urls.append(instance.image_url)
        
        for task in related_tasks:
            if task.image_url:
                image_urls.append(task.image_url)
        
        # Удаляем изображения из S3
        for image_url in image_urls:
            try:
                success = delete_image_from_s3(image_url)
                if success:
                    logger.info(f"✅ Удалено изображение из S3: {image_url}")
                else:
                    logger.warning(f"⚠️ Не удалось удалить изображение из S3: {image_url}")
            except Exception as e:
                logger.error(f"❌ Ошибка удаления изображения {image_url}: {e}")
        
        # Удаляем связанные задачи
        # Django автоматически удалит TaskTranslation через CASCADE
        deleted_count, _ = related_tasks.delete()
        
        if deleted_count > 0:
            logger.info(
                f"✅ Удалено {deleted_count} связанных задач "
                f"для translation_group_id {translation_group_id}"
            )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в сигнале удаления задачи {instance.id}: {e}")


@receiver(post_delete, sender=Task)
def log_task_deletion(sender, instance, **kwargs):
    """
    Логирует удаление задачи.
    
    Args:
        sender: Класс модели (Task)
        instance: Удаленный экземпляр Task
        **kwargs: Дополнительные аргументы сигнала
    """
    logger.info(
        f"🗑️ Задача {instance.id} удалена "
        f"(topic: {instance.topic.name if instance.topic else 'N/A'}, "
        f"translation_group_id: {instance.translation_group_id})"
    )

