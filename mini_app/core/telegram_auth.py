"""
Проверка пользователя Telegram Mini App.

Клиент присылает подписанный Telegram initData в заголовке X-Telegram-Init-Data.
Подпись проверяет Django (токеном бота текущего тенанта) через
/api/accounts/miniapp-users/auth/verify/; результат кэшируется на несколько минут.

telegram_id из URL, тела или query-параметров клиента не считается доказательством
личности — используйте только пользователя из verified_telegram_user.
"""

import hashlib
import logging
import time
from typing import Optional

import httpx
from fastapi import HTTPException, Request

from core.config import settings

logger = logging.getLogger(__name__)

INIT_DATA_HEADER = 'X-Telegram-Init-Data'
VERIFY_ENDPOINT = '/api/accounts/miniapp-users/auth/verify/'
_CACHE_TTL_SECONDS = 300
_CACHE_MAX_SIZE = 10000
_verified_cache: dict = {}


def tenant_host_headers(request: Request) -> dict:
    """Хост и схема исходного запроса — по ним Django определяет тенанта."""
    host = request.headers.get('x-forwarded-host') or request.headers.get('host')
    scheme = request.headers.get('x-forwarded-proto') or request.url.scheme
    return {'X-Forwarded-Host': host, 'X-Forwarded-Proto': scheme, 'Host': host}


async def verify_init_data(init_data: str, request: Request) -> dict:
    """Возвращает проверенного пользователя Telegram (dict с id, first_name, ...) или 401."""
    if not init_data:
        raise HTTPException(status_code=401, detail='Telegram initData is required')

    headers = tenant_host_headers(request)
    cache_key = hashlib.sha256(f"{headers['Host']}\n{init_data}".encode()).hexdigest()
    now = time.monotonic()
    cached = _verified_cache.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]

    headers[INIT_DATA_HEADER] = init_data
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f'{settings.DJANGO_API_BASE_URL}{VERIFY_ENDPOINT}', headers=headers)
    except httpx.RequestError as e:
        logger.error(f'initData verification request failed: {e}')
        raise HTTPException(status_code=502, detail='Could not verify Telegram initData')

    if response.status_code in (401, 403):
        raise HTTPException(status_code=401, detail='Invalid Telegram initData')
    if response.status_code != 200:
        logger.error(f'initData verification returned {response.status_code}')
        raise HTTPException(status_code=502, detail='Could not verify Telegram initData')

    user = (response.json() or {}).get('user') or {}
    if not user.get('id'):
        raise HTTPException(status_code=401, detail='Invalid Telegram initData')

    if len(_verified_cache) >= _CACHE_MAX_SIZE:
        _verified_cache.clear()
    _verified_cache[cache_key] = (now + _CACHE_TTL_SECONDS, user)
    return user


async def verified_telegram_user(request: Request) -> dict:
    """FastAPI-зависимость: пользователь из заголовка X-Telegram-Init-Data, иначе 401."""
    return await verify_init_data(request.headers.get(INIT_DATA_HEADER, ''), request)


async def optional_telegram_user(request: Request) -> Optional[dict]:
    """Как verified_telegram_user, но без заголовка возвращает None (например, оплата из браузера)."""
    if not request.headers.get(INIT_DATA_HEADER):
        return None
    return await verified_telegram_user(request)


def ensure_same_user(user: dict, telegram_id) -> None:
    """403, если telegram_id из запроса не совпадает с проверенным пользователем."""
    if str(telegram_id) != str(user['id']):
        raise HTTPException(status_code=403, detail='telegram_id does not match the authenticated Telegram user')
