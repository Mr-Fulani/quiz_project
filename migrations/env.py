import asyncio
import os
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from alembic import context, op
from dotenv import load_dotenv
import logging
import sqlalchemy as sa

from bot.database.database import Base

# Загрузка конфигурации логов Alembic
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Настройка логирования
logger = logging.getLogger('alembic.runtime.migration')

# Задаём метаданные из моделей для Alembic
target_metadata = Base.metadata

# Загрузка переменных окружения
load_dotenv()


# Проверка на наличие переменной окружения DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Не удалось найти переменную окружения DATABASE_URL")


# Создание асинхронного движка
def get_engine() -> AsyncEngine:
    logger.info("Создание асинхронного движка...")
    return create_async_engine(DATABASE_URL, poolclass=pool.NullPool)


# Асинхронная миграция
async def run_migrations_async():
    logger.info("Запуск асинхронной миграции...")
    connectable = get_engine()

    async with connectable.connect() as connection:
        logger.info("Установлено соединение с базой данных.")
        await connection.run_sync(do_run_migrations)


# Синхронная миграция для поддержки Alembic
def run_migrations():
    logger.info("Запуск синхронной миграции...")
    connectable = get_engine().sync_engine  # Преобразование в синхронный движок

    with connectable.connect() as connection:
        logger.info("Установлено соединение с базой данных (синхронный режим).")
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            logger.info("Выполнение миграций...")
            context.run_migrations()


# Основная функция для выполнения миграций (общая логика)
def do_run_migrations(connection):
    logger.info("Конфигурация и запуск миграций...")
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        logger.info("Начало транзакции миграции...")
        context.run_migrations()
        logger.info("Миграции успешно выполнены.")


# Выполняем миграцию
if context.is_offline_mode():
    logger.info("Запуск миграции в оффлайн-режиме...")
    run_migrations()
else:
    logger.info("Запуск миграции в онлайн-режиме...")
    asyncio.run(run_migrations_async())


# Функция upgrade
def upgrade():
    logger.info("Применяем изменение типа для колонки wrong_answers на JSON...")
    # Изменяем тип колонки wrong_answers с Text на JSON
    op.alter_column('tasks', 'wrong_answers', type_=sa.JSON)


# Функция downgrade
def downgrade():
    logger.info("Откат миграции изменения типа wrong_answers обратно на Text...")
    # Откат изменений (с JSON обратно на Text)
    op.alter_column('tasks', 'wrong_answers', type_=sa.Text)