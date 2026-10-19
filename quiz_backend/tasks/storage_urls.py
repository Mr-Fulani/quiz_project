"""
Ссылки на файлы в публичном хранилище (R2/S3).

В БД хранится ключ объекта (prod/<tenant>/tasks/.../x.png), а не полный URL: домен хранилища
берётся из настроек (R2_PUBLIC_DOMAIN → AWS_PUBLIC_MEDIA_DOMAIN) и меняется в .env без правки данных.
Внешние ссылки (не на наше хранилище) хранятся как есть.

Та же логика для бота — bot/utils/storage_urls.py.
"""
from urllib.parse import unquote, urlsplit

from django.conf import settings


def media_domain():
    """Публичный домен хранилища без схемы, например media.example.com."""
    return (getattr(settings, 'AWS_PUBLIC_MEDIA_DOMAIN', None) or '').strip().strip('/')


def _own_domains():
    """Текущий домен хранилища и прежние (STORAGE_LEGACY_DOMAINS) — ссылки на них сводятся к ключу."""
    domains = [media_domain(), *getattr(settings, 'STORAGE_LEGACY_DOMAINS', [])]
    return {d.strip().lower() for d in domains if d and d.strip()}


def to_storage_key(value):
    """Полный URL нашего хранилища → ключ объекта; ключ и внешние ссылки возвращаются без изменений."""
    if not isinstance(value, str) or not value.startswith(('http://', 'https://')):
        return value
    parts = urlsplit(value)
    if parts.hostname and parts.hostname.lower() in _own_domains():
        return unquote(parts.path).lstrip('/')
    return value


def to_public_url(value):
    """Ключ объекта → полный публичный URL; полные URL возвращаются без изменений."""
    if not isinstance(value, str) or not value or value.startswith(('http://', 'https://')):
        return value
    domain = media_domain()
    if not domain:
        return value
    return f'https://{domain}/{value.lstrip("/")}'
