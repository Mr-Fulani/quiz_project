import os
from sqlalchemy import engine_from_config, pool
from alembic import context
from logging.config import fileConfig

# Укажите метаданные ваших моделей
from bot.database.database import Base

target_metadata = Base.metadata

# Настройка логов
config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# Используем синхронный драйвер только для миграций
sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql+psycopg2://admin_fulani_quiz:4748699@postgres_db:5432/fulani_quiz_db")
async_url = config.get_main_option("sqlalchemy.url")

def run_migrations_offline():
    """Запуск миграций в оффлайн-режиме."""
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Запуск миграций в онлайн-режиме."""
    connectable = engine_from_config(
        {"sqlalchemy.url": sync_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()