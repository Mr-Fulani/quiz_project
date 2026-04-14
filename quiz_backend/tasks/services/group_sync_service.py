# tasks/services/group_sync_service.py

import logging
from django.db.models import Q
from tasks.models import Task
from platforms.models import TelegramGroup

logger = logging.getLogger(__name__)

def sync_tasks_with_groups(tenant, topic=None, language=None, task_queryset=None):
    """
    Синхронизирует задачи с Telegram-группами на основе темы и языка.
    
    Args:
        tenant: Тенант
        topic: (Optional) Конкретная тема
        language: (Optional) Конкретный язык
        task_queryset: (Optional) Готовый кверисет задач для обработки
        
    Returns:
        int: Количество обновленных задач
    """
    if task_queryset is None:
        # Берем задачи без групп или те, что нужно перепроверить
        task_queryset = Task.objects.filter(tenant=tenant)
        if topic:
            task_queryset = task_queryset.filter(topic=topic)

    updated_count = 0
    
    # Чтобы не делать запрос на каждую задачу, получим все группы тенанта
    groups_qs = TelegramGroup.objects.filter(tenant=tenant)
    if topic:
        groups_qs = groups_qs.filter(topic_id=topic)
    if language:
        groups_qs = groups_qs.filter(language=language)
        
    # Кэшируем группы в словаре: {(topic_id, language): group_object}
    groups_map = {
        (g.topic_id_id, g.language.lower()): g 
        for g in groups_qs
    }
    
    if not groups_map:
        logger.info(f"No Telegram groups found for tenant {tenant.slug} to sync with.")
        return 0

    # Обрабатываем задачи
    # Используем prefetch_related для переводов, чтобы узнать язык задачи
    for task in task_queryset.select_related('topic').prefetch_related('translations'):
        # Если у задачи уже есть группа, и мы не в режиме "принудительного переназначения",
        # то можно пропустить. Но обычно мы хотим найти группу, если её нет.
        
        # У задачи (в вашей текущей архитектуре импорта) один TaskTranslation на один Task object
        translation = task.translations.first()
        if not translation:
            continue
            
        task_lang = translation.language.lower()
        if language and task_lang != language.lower():
            continue
            
        # Ищем подходящую группу
        group = groups_map.get((task.topic_id, task_lang))
        
        if group and task.group_id != group.id:
            task.group = group
            task.save(update_fields=['group'])
            updated_count += 1
            logger.info(f"Task {task.id} linked to TelegramGroup {group.group_name} ({task_lang})")
            
    return updated_count
