"""
Утилиты для работы с задачами.
"""
from .models import Task


def get_tasks_by_translation_group(task):
    """
    Возвращает все задачи с тем же translation_group_id.
    
    Args:
        task: Экземпляр модели Task
        
    Returns:
        QuerySet: Все задачи с тем же translation_group_id
    """
    return Task.objects.filter(translation_group_id=task.translation_group_id)
