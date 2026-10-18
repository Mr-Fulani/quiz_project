import logging
from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.database.models import TelegramAdmin

logger = logging.getLogger(__name__)

async def is_admin(user_id: int, db_session: AsyncSession) -> bool:
    """
    Проверяет, является ли пользователь активным админом.
    """
    logger.debug(f"Проверка админа для user_id={user_id}")
    query = select(TelegramAdmin).where(
        TelegramAdmin.telegram_id == user_id,
        TelegramAdmin.is_active.is_(True),
    )
    result = await db_session.execute(query)
    # first(): пользователь может быть админом в нескольких тенантах — не падаем на дублях
    admin = result.scalars().first()
    logger.debug(f"Результат проверки для user_id={user_id}: {admin is not None}")
    return admin is not None


class IsAdminFilter(BaseFilter):
    """
    Пропускает апдейт только от активного админа.
    Вешается на роутер целиком (router.message.filter / router.callback_query.filter)
    или на отдельный хендлер; db_session приходит из DbSessionMiddleware.
    """

    async def __call__(self, event: TelegramObject, db_session: AsyncSession) -> bool:
        user = getattr(event, 'from_user', None)
        if user is None:
            return False
        allowed = await is_admin(user.id, db_session)
        if not allowed:
            logger.warning(f"Отклонён админский апдейт от не-админа user_id={user.id}")
        return allowed

async def add_admin(user_id: int, username: str | None, db_session: AsyncSession, groups: list = None):
    """
    Добавляет админа с опциональными группами.
    """
    try:
        admin = TelegramAdmin(
            telegram_id=user_id,
            username=username,
            language=None,
            is_active=True
        )
        if groups:
            admin.groups = groups
        db_session.add(admin)
        await db_session.commit()
        logger.info(f"Админ с ID {user_id} (@{username}) добавлен с группами: {[g.username for g in groups] if groups else 'без групп'}")
    except IntegrityError:
        logger.error(f"Не удалось добавить админа с ID {user_id}: нарушение целостности.")
        raise
    except Exception as e:
        logger.error(f"Ошибка добавления админа с ID {user_id}: {e}")
        raise

async def remove_admin(user_id: int, db_session: AsyncSession):
    """
    Удаляет админа.
    """
    try:
        query = select(TelegramAdmin).where(TelegramAdmin.telegram_id == user_id)
        result = await db_session.execute(query)
        admin = result.scalar_one_or_none()
        if admin:
            await db_session.delete(admin)
            await db_session.commit()
            logger.info(f"Админ с ID {user_id} удалён.")
        else:
            logger.warning(f"Попытка удалить несуществующего админа с ID {user_id}.")
    except Exception as e:
        logger.error(f"Ошибка удаления админа с ID {user_id}: {e}")
        raise