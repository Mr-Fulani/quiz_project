"""
Ссылки на файлы в хранилище для бота — та же логика, что quiz_backend/tasks/storage_urls.py:
в БД хранится ключ объекта, код бота получает полный URL с текущим доменом хранилища.
"""
import os
from urllib.parse import unquote, urlsplit

from sqlalchemy import JSON, String
from sqlalchemy.types import TypeDecorator

from bot import config


def media_domain():
    """Публичный домен хранилища без схемы."""
    if config.USE_R2_STORAGE:
        domain = getattr(config, 'R2_PUBLIC_DOMAIN', None)
    elif config.S3_BUCKET_NAME:
        domain = f"{config.S3_BUCKET_NAME}.s3.{config.S3_REGION}.amazonaws.com"
    else:
        domain = None
    return (domain or '').strip().strip('/')


def _own_domains():
    legacy = os.getenv('STORAGE_LEGACY_DOMAINS', '').split(',')
    return {d.strip().lower() for d in [media_domain(), *legacy] if d and d.strip()}


def to_storage_key(value):
    """Полный URL нашего хранилища → ключ объекта; ключ и внешние ссылки — без изменений."""
    if not isinstance(value, str) or not value.startswith(('http://', 'https://')):
        return value
    parts = urlsplit(value)
    if parts.hostname and parts.hostname.lower() in _own_domains():
        return unquote(parts.path).lstrip('/')
    return value


def to_public_url(value):
    """Ключ объекта → полный публичный URL; полные URL — без изменений."""
    if not isinstance(value, str) or not value or value.startswith(('http://', 'https://')):
        return value
    domain = media_domain()
    if not domain:
        return value
    return f"https://{domain}/{value.lstrip('/')}"


class StorageURL(TypeDecorator):
    """Колонка со ссылкой на файл в хранилище (см. StorageURLField в Django)."""
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return to_storage_key(value)

    def process_result_value(self, value, dialect):
        return to_public_url(value)


class StorageURLMap(TypeDecorator):
    """JSON {язык: ссылка на файл в хранилище} (см. StorageURLMapField в Django)."""
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return _map_urls(value, to_storage_key)

    def process_result_value(self, value, dialect):
        return _map_urls(value, to_public_url)


def _map_urls(value, convert):
    if not isinstance(value, dict):
        return value
    return {key: convert(url) for key, url in value.items()}
