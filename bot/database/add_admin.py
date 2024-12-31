import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from bot.config import DATABASE_URL
from bot.database.models import Admin  # Убедитесь, что модель Admin правильно импортирована
import logging


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


# Настройка базы данных
engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def add_admin(telegram_id: int, username: str = None):
    async with async_session_maker() as session:
        query = select(Admin).where(Admin.telegram_id == telegram_id)
        result = await session.execute(query)
        admin = result.scalar_one_or_none()
        if not admin:
            admin = Admin(telegram_id=telegram_id, username=username)
            session.add(admin)
            await session.commit()
            logger.info(f"✅ Добавлен администратор: Telegram ID={telegram_id}, Username={username}")
        else:
            logger.info(f"⚠️ Администратор с Telegram ID={telegram_id} уже существует.")


async def main():
    telegram_id = int(input("Введите Telegram ID администратора: "))
    username = input("Введите Username администратора (необязательно): ")
    await add_admin(telegram_id, username if username else None)


if __name__ == "__main__":
    asyncio.run(main())