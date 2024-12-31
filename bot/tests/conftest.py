
from sqlalchemy.ext.asyncio import AsyncSession
import pytest
from aiogram import Bot
from unittest.mock import MagicMock, AsyncMock


# Фикстура для создания мок-объекта бота
@pytest.fixture
def bot():
    mock_bot = MagicMock(spec=Bot)  # Создаем мок-объект на основе класса Bot
    return mock_bot




@pytest.fixture
def db_session():
    # Мокаем объект AsyncSession
    session = AsyncMock(spec=AsyncSession)
    return session