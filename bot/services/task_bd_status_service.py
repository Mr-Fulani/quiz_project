from sqlalchemy import select, func, asc
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from database.models import Task, Topic





async def get_task_status(db_session):
    """
    Получает информацию о неопубликованных задачах, опубликованных задачах и общей информации по базе.
    """
    one_month_ago = datetime.now() - timedelta(days=30)

    # Запрос для получения неопубликованных задач
    result_unpublished = await db_session.execute(
        select(Task.topic_id, func.count(Task.id), func.array_agg(Task.id))
        .where(Task.published.is_(False))
        .group_by(Task.topic_id)
    )
    unpublished_tasks = result_unpublished.all()

    # Запрос для получения опубликованных задач (актуальных)
    result_published = await db_session.execute(
        select(Task.topic_id, func.array_agg(Task.id))
        .where(Task.published.is_(True), Task.publish_date >= one_month_ago)
        .group_by(Task.topic_id)
    )
    published_tasks = result_published.all()

    # Запрос для получения старых опубликованных задач
    result_old_published = await db_session.execute(
        select(Task.topic_id, Task.id)
        .where(Task.published.is_(True), Task.publish_date < one_month_ago)
    )
    old_published_tasks = result_old_published.all()

    # Общее количество задач
    result_total_tasks = await db_session.execute(select(func.count(Task.id)))
    total_tasks = result_total_tasks.scalar()

    # Получение средней даты создания задач с использованием EXTRACT (извлечение секунд)
    result_all_tasks = await db_session.execute(
        select(func.to_timestamp(func.avg(func.extract('epoch', Task.create_date))))
    )
    all_tasks_info = {
        "average_creation_date": result_all_tasks.scalar()
    }

    # Получение списка тем (topics)
    result_topics = await db_session.execute(select(Topic.id, Topic.name))
    topics = {row.id: row.name for row in result_topics}

    return unpublished_tasks, published_tasks, old_published_tasks, total_tasks, all_tasks_info, topics








async def get_zero_task_topics(db_session: AsyncSession) -> list:
    """
    Получает все топики, у которых нет связанных задач.
    Возвращает список словарей с 'id' и 'name' топиков.
    """
    stmt = (
        select(Topic.id, Topic.name)
        .outerjoin(Task, Topic.id == Task.topic_id)
        .group_by(Topic.id)
        .having(func.count(Task.id) == 0)
        .order_by(asc(Topic.id))  # Добавлена сортировка по ID
    )
    result = await db_session.execute(stmt)
    zero_task_topics = [{"id": row.id, "name": row.name} for row in result.fetchall()]
    return zero_task_topics