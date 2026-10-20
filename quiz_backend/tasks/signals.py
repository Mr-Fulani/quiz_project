"""
Сигналы для автоматической отправки уведомлений администраторам.

Обрабатывает создание новых комментариев и жалоб,
отправляя уведомления через Telegram всем активным админам.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Task, TaskComment, TaskCommentReport

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TaskComment)
def comment_created_notification(sender, instance, created, **kwargs):
    """
    Отправляет уведомление администраторам при создании нового комментария.
    
    ОТКЛЮЧЕНО: Уведомления отправляются напрямую в comment_views.py,
    так как только там есть доступ к request для правильного формирования URL.
    
    Args:
        sender: Модель TaskComment
        instance: Созданный комментарий
        created: True если это новый объект, False если обновление
        **kwargs: Дополнительные аргументы сигнала
    """
    # Отключено — уведомления отправляются в comment_views.py с передачей request
    pass


@receiver(post_save, sender=TaskCommentReport)
def report_created_notification(sender, instance, created, **kwargs):
    """
    Отправляет уведомление администраторам при создании новой жалобы.
    
    ОТКЛЮЧЕНО: Уведомления теперь отправляются напрямую в comment_views.py
    для корректной работы с динамическими URL и правильного экранирования.
    
    Args:
        sender: Модель TaskCommentReport
        instance: Созданная жалоба
        created: True если это новый объект, False если обновление
        **kwargs: Дополнительные аргументы сигнала
    """
    # Отключено — уведомления отправляются в comment_views.py
    pass


@receiver(post_save, sender=Task)
def auto_publish_to_social_media(sender, instance, created, **kwargs):
    """
    Автоматически публикует задачу в социальные сети при published=True.
    
    Срабатывает когда:
    1. Задача создается с published=True
    2. Задача обновляется и published меняется с False на True
    
    Args:
        sender: Модель Task
        instance: Объект задачи
        created: True если это новый объект
        **kwargs: Дополнительные аргументы сигнала
    """
    # Проверяем, что задача опубликована
    if not instance.published:
        return
    
    # Получаем перевод задачи
    translation = instance.translations.first()
    if not translation:
        logger.warning(f"⚠️ Задача {instance.id} не имеет переводов, пропускаем отправку в соцсети")
        return

    # В соцсети идут только английские задачи (картинки делаются только для них)
    from .services.social_image import needs_social_image
    if not needs_social_image(translation):
        return
    
    # Проверяем, не отправляли ли уже эту задачу (избегаем дублей)
    # Проверяем любые существующие записи для этой задачи
    existing_posts = instance.social_media_posts.exists()
    
    if existing_posts:
        logger.info(f"ℹ️ Задача {instance.id} уже имеет записи о публикации в соцсети, пропускаем автопубликацию")
        return
    
    # Публикуем в соцсети
    try:
        from .services.social_media_service import publish_to_social_media
        
        logger.info(f"🌐 Автопубликация задачи {instance.id} в соцсети")
        result = publish_to_social_media(instance, translation)
        
        if result['success'] > 0:
            logger.info(f"✅ Задача {instance.id} опубликована: {result['success']}/{result['total']} платформ")
        else:
            logger.warning(f"⚠️ Задача {instance.id}: не удалось опубликовать ни в одной платформе")
            
    except Exception as e:
        logger.error(f"❌ Ошибка автопубликации задачи {instance.id}: {e}", exc_info=True)
