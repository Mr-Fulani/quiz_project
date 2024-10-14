import logging

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Admin
from sqlalchemy import delete



# Логгер для отслеживания действий
logger = logging.getLogger(__name__)



# Проверка, является ли пользователь администратором
async def is_admin(user_id: int, db_session: AsyncSession) -> bool:
    """Проверка, является ли пользователь администратором."""
    logger.info("Попытка выполнить запрос к базе данных1")
    logger.info(f"db_session is async: {isinstance(db_session, AsyncSession)}")
    result = await db_session.execute(select(Admin).where(Admin.telegram_id == user_id))
    logger.info("Запрос выполнен успешно")
    admin = result.scalar_one_or_none()
    return admin is not None



# Добавление администратора
async def add_admin(user_id: int, username: str, db_session: AsyncSession):
    """Добавление нового администратора."""
    new_admin = Admin(telegram_id=user_id, username=username)
    db_session.add(new_admin)
    await db_session.commit()
    logger.info("Транзакция выполнена успешно 1")




# Удаление администратора
async def remove_admin(user_id: int, db_session: AsyncSession):
    """Удаление администратора."""
    logger.info("Попытка выполнить запрос к базе данных3")
    logger.info(f"db_session is async: {isinstance(db_session, AsyncSession)}")
    await db_session.execute(delete(Admin).where(Admin.telegram_id == user_id))
    logger.info("Запрос выполнен успешно")

    await db_session.commit()
    logger.info("Транзакция выполнена успешно 2")











