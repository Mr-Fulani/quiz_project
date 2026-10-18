"""
Настройки для прогона тестов без Docker/Postgres: настройки проекта + SQLite в памяти.

Миграции проекта содержат Postgres-специфичный SQL, поэтому таблицы создаются прямо из моделей.
Запуск: pytest --ds=config.test_settings_sqlite ... (см. DEPLOYMENT.md, «Тесты backend без Docker»).
"""
from config.settings import *  # noqa: F401,F403


class _DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = _DisableMigrations()

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
