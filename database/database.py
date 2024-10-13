from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from config import DATABASE_URL
from typing import AsyncGenerator



# Создаем базу данных моделей
Base = declarative_base()



# Создаем асинхронный движок для подключения к базе данных
async_engine = create_async_engine(DATABASE_URL, echo=True)



# Создаем фабрику асинхронных сессий с использованием async_sessionmaker
AsyncSessionMaker = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False
)


# Функция получения асинхронной сессии
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionMaker() as session:
        yield session