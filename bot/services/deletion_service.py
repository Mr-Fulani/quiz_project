import logging
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Task, TaskTranslation, Topic, Group




logger = logging.getLogger(__name__)







async def delete_task_by_id(task_id: int, db_session: AsyncSession):
    """
    Удаляет задачу и связанные с ней переводы по ID задачи.

    Args:
        task_id (int): ID задачи для удаления.
        db_session (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        dict: Содержит информацию об удалённых задачах и переводах, или None, если задача не найдена.
    """
    logger.debug(f"Получен запрос на удаление задачи с ID: {task_id}")

    # Получаем задачу и её группу переводов
    result_task = await db_session.execute(
        select(Task.id, Task.topic_id, Task.translation_group_id).where(Task.id == task_id)
    )
    task = result_task.first()

    if not task:
        logger.warning(f"⚠️ Задача с ID {task_id} не найдена.")
        return None  # Возвращаем None, если задача не найдена

    translation_group_id = task.translation_group_id
    topic_id = task.topic_id

    # Получаем название топика
    result_topic = await db_session.execute(
        select(Topic.name).where(Topic.id == topic_id)
    )
    topic_name = result_topic.scalar()

    # Получаем все задачи и переводы, связанные с translation_group_id
    result_tasks_in_group = await db_session.execute(
        select(Task.id, Task.group_id).where(Task.translation_group_id == translation_group_id)
    )
    tasks_in_group = result_tasks_in_group.fetchall()
    task_ids_in_group = [row[0] for row in tasks_in_group]
    group_ids = [row[1] for row in tasks_in_group]

    result_translations = await db_session.execute(
        select(TaskTranslation.id, TaskTranslation.language).where(TaskTranslation.task_id.in_(task_ids_in_group))
    )
    translations = result_translations.fetchall()
    translation_ids = [row[0] for row in translations]
    translation_languages = [row[1] for row in translations]

    # Получаем названия групп
    if group_ids:
        result_groups = await db_session.execute(
            select(Group.group_name).where(Group.id.in_(group_ids))
        )
        group_names = [row[0] for row in result_groups.fetchall()]
    else:
        group_names = []

    # Логируем переводы до удаления
    logger.debug(f"Переводы до удаления для группы переводов {translation_group_id}: {translations}")

    if not translation_ids:
        logger.warning(f"Переводы для задачи с ID {task_id} не найдены.")

    try:
        # Удаляем переводы, связанные с translation_group_id
        await db_session.execute(
            delete(TaskTranslation).where(TaskTranslation.task_id.in_(task_ids_in_group))
        )

        # Удаляем все задачи в группе переводов
        await db_session.execute(
            delete(Task).where(Task.translation_group_id == translation_group_id)
        )
        await db_session.commit()

        logger.info(f"✅ Задачи с ID {', '.join(map(str, task_ids_in_group))} успешно удалены.")

        # Формируем информацию об удалении
        deletion_info = {
            'deleted_task_ids': task_ids_in_group,
            'topic_name': topic_name,
            'deleted_translation_count': len(translation_ids),
            'deleted_translation_languages': translation_languages,
            'group_names': group_names
        }

        return deletion_info

    except Exception as e:
        await db_session.rollback()
        logger.error(f"Ошибка при удалении задач с группой переводов {translation_group_id}: {e}")
        return None