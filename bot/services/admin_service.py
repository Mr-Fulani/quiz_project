
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from database.models import Admin
from sqlalchemy import delete







# Проверка, является ли пользователь администратором
async def is_admin(user_id: int, db_session: AsyncSession) -> bool:
    """Проверка, является ли пользователь администратором."""
    result = await db_session.execute(select(Admin).where(Admin.telegram_id == user_id))
    admin = result.scalar_one_or_none()
    return admin is not None



# Добавление администратора
async def add_admin(user_id: int, username: str, db_session: AsyncSession):
    """Добавление нового администратора."""
    new_admin = Admin(telegram_id=user_id, username=username)
    db_session.add(new_admin)
    await db_session.commit()




# Удаление администратора
async def remove_admin(user_id: int, db_session: AsyncSession):
    """Удаление администратора."""
    await db_session.execute(delete(Admin).where(Admin.telegram_id == user_id))
    await db_session.commit()











