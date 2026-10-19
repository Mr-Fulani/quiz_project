from django.db import models

from tasks.storage_urls import to_public_url, to_storage_key


class StorageURLField(models.URLField):
    """
    Ссылка на файл в хранилище: в БД лежит ключ объекта, модель отдаёт полный URL
    с текущим доменом хранилища (см. tasks/storage_urls.py).
    """

    def from_db_value(self, value, expression, connection):
        return to_public_url(value)

    def get_prep_value(self, value):
        return super().get_prep_value(to_storage_key(value))


class StorageURLMapField(models.JSONField):
    """Словарь {язык: ссылка на файл в хранилище}; хранение — как у StorageURLField."""

    def from_db_value(self, value, expression, connection):
        return _map_urls(super().from_db_value(value, expression, connection), to_public_url)

    def get_prep_value(self, value):
        return super().get_prep_value(_map_urls(value, to_storage_key))


def _map_urls(value, convert):
    if not isinstance(value, dict):
        return value
    return {key: convert(url) for key, url in value.items()}
