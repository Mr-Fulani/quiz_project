"""
Сигналы для автоматической отправки уведомлений администраторам.

Обрабатывает создание новых комментариев и жалоб,
отправляя уведомления через Telegram всем активным админам.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TaskComment, TaskCommentReport

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
