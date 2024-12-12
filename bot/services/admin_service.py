# bot/services/admin_service.py

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.models import Admin

logger = logging.getLogger(__name__)



async def is_admin(user_id: int, db_session: AsyncSession) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    """
    logger.debug(f"Проверка администратора для user_id={user_id}")
    query = select(Admin).where(Admin.telegram_id == user_id)
    result = await db_session.execute(query)
    admin = result.scalar_one_or_none()
    logger.debug(f"Результат проверки администратора для user_id={user_id}: {admin is not None}")
    return admin is not None



async def add_admin(user_id: int, username: str, db_session: AsyncSession):
    try:
        admin = Admin(telegram_id=user_id, username=username)
        db_session.add(admin)
        await db_session.commit()
        logger.info(f"Администратор с ID {user_id} и username @{username} добавлен.")
    except IntegrityError:
        logger.error(f"Не удалось добавить администратора с ID {user_id}: нарушение целостности данных.")
        raise
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при добавлении администратора с ID {user_id}: {e}")
        raise




async def remove_admin(user_id: int, db_session: AsyncSession):
    try:
        query = select(Admin).where(Admin.telegram_id == user_id)
        result = await db_session.execute(query)
        admin = result.scalar_one_or_none()
        if admin:
            await db_session.delete(admin)
            await db_session.commit()
            logger.info(f"Администратор с ID {user_id} удалён.")
        else:
            logger.warning(f"Попытка удалить несуществующего администратора с ID {user_id}.")
    except Exception as e:
        logger.exception(f"Ошибка при удалении администратора с ID {user_id}: {e}")
        raise