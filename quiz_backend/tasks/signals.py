"""
Сигналы для автоматической отправки уведомлений администраторам.

Обрабатывает создание новых комментариев и жалоб,
отправляя уведомления через Telegram всем активным админам.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TaskComment, TaskCommentReport
from .notification_service import notify_admins_new_comment, notify_admins_new_report

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TaskComment)
def comment_created_notification(sender, instance, created, **kwargs):
    """
    Отправляет уведомление администраторам при создании нового комментария.
    
    Args:
        sender: Модель TaskComment
        instance: Созданный комментарий
        created: True если это новый объект, False если обновление
        **kwargs: Дополнительные аргументы сигнала
    """
    # Отправляем уведомление только при создании нового комментария
    if created:
        try:
            logger.info(f"Новый комментарий создан: #{instance.id} от пользователя {instance.author_telegram_id}")
            
            # Отправляем уведомления админам
            sent_count = notify_admins_new_comment(instance)
            
            if sent_count > 0:
                logger.info(f"Уведомления о новом комментарии отправлены {sent_count} админам")
            else:
                logger.warning(f"Не удалось отправить уведомления о новом комментарии #{instance.id}")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке сигнала создания комментария: {e}", exc_info=True)


@receiver(post_save, sender=TaskCommentReport)
def report_created_notification(sender, instance, created, **kwargs):
    """
    Отправляет уведомление администраторам при создании новой жалобы.
    
    Args:
        sender: Модель TaskCommentReport
        instance: Созданная жалоба
        created: True если это новый объект, False если обновление
        **kwargs: Дополнительные аргументы сигнала
    """
    # Отправляем уведомление только при создании новой жалобы
    if created:
        try:
            logger.info(f"Новая жалоба создана: #{instance.id} от пользователя {instance.reporter_telegram_id} на комментарий #{instance.comment.id}")
            
            # Отправляем уведомления админам
            sent_count = notify_admins_new_report(instance)
            
            if sent_count > 0:
                logger.info(f"Уведомления о новой жалобе отправлены {sent_count} админам")
            else:
                logger.warning(f"Не удалось отправить уведомления о новой жалобе #{instance.id}")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке сигнала создания жалобы: {e}", exc_info=True)
