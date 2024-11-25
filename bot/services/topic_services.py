# database/services.py
import logging
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from database.models import Topic



logger = logging.getLogger(__name__)






async def add_topic_to_db(db_session: AsyncSession, topic_name: str) -> Topic:
    """
    Добавляет новый топик в базу данных и возвращает его.
    """
    new_topic = Topic(name=topic_name)
    db_session.add(new_topic)
    try:
        await db_session.commit()
        await db_session.refresh(new_topic)  # Получаем обновлённый объект с ID
        logger.info(f"Топик '{topic_name}' (ID: {new_topic.id}) добавлен в базу данных.")
        return new_topic
    except IntegrityError:
        await db_session.rollback()
        logger.warning(f"Топик '{topic_name}' уже существует.")
        raise ValueError(f"Топик '{topic_name}' уже существует.")
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Ошибка при добавлении топика '{topic_name}': {e}")
        raise e





async def delete_topic_from_db(db_session: AsyncSession, topic_id: int) -> Optional[Topic]:
    """
    Удаляет топик из базы данных по ID и возвращает удалённый топик.
    Если топик не найден, возвращает None.
    """
    stmt = select(Topic).where(Topic.id == topic_id)
    result = await db_session.execute(stmt)
    topic = result.scalars().first()

    if topic:
        await db_session.delete(topic)
        await db_session.commit()
        logger.info(f"Топик '{topic.name}' (ID: {topic.id}) удалён из базы данных.")
        return topic
    else:
        logger.warning(f"Топик с ID {topic_id} не найден.")
        return None