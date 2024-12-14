import asyncio
import logging

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import Connection
from database.models import Task, TaskTranslation, Group
from database.database import async_engine, AsyncSessionMaker

# Настройка логгера
logger = logging.getLogger(__name__)

async def clear_tasks_and_reset_sequence(db_session: AsyncSession, conn: Connection):
    # Удаление данных из таблиц TaskTranslation и Task
    logger.info(f"db_session is async: {isinstance(db_session, AsyncSession)}")
    await db_session.execute(delete(TaskTranslation))
    await db_session.execute(delete(Task))
    await db_session.execute(delete(Group))

    # Сброс автоинкрементного ID для таблиц TaskTranslation и Task
    await conn.execute(text("ALTER SEQUENCE task_translations_id_seq RESTART WITH 1"))
    await conn.execute(text("ALTER SEQUENCE tasks_id_seq RESTART WITH 1"))
    await conn.execute(text("ALTER SEQUENCE groups_id_seq RESTART WITH 1"))

    await db_session.commit()
    print("Таблицы очищены и автоинкрементные значения сброшены.")

async def main():
    async with async_engine.begin() as conn:
        async with AsyncSessionMaker(bind=conn) as session:
            await clear_tasks_and_reset_sequence(session, conn)

if __name__ == "__main__":
    asyncio.run(main())