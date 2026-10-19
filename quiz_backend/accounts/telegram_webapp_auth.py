"""
Проверка подписи Telegram Mini App initData.

Mini App передаёт подписанную Telegram строку initData в заголовке X-Telegram-Init-Data.
Подпись проверяется токеном бота тенанта (HMAC-SHA256 по алгоритму из документации Telegram:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).

Только проверенный telegram_id считается личностью пользователя: любые telegram_id
в URL, теле или query-параметрах запроса обязаны с ним совпадать.
"""

import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

from django.conf import settings
from rest_framework.permissions import SAFE_METHODS, BasePermission

logger = logging.getLogger(__name__)

INIT_DATA_HEADER = 'HTTP_X_TELEGRAM_INIT_DATA'


class InitDataError(Exception):
    """initData отсутствует, подделан или устарел."""


def validate_init_data(init_data, bot_token, max_age_seconds=None, now=None):
    """
    Проверяет подпись и срок действия initData.

    Returns:
        dict: данные пользователя Telegram из поля user (id, first_name, username, ...).
    Raises:
        InitDataError: если подпись неверна, auth_date устарел или нет пользователя.
    """
    if not init_data:
        raise InitDataError('initData is missing')
    if not bot_token:
        raise InitDataError('bot token is not configured')

    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as exc:
        raise InitDataError('initData is malformed') from exc

    received_hash = fields.pop('hash', None)
    if not received_hash:
        raise InitDataError('hash is missing')

    data_check_string = '\n'.join(f'{key}={value}' for key, value in sorted(fields.items()))
    secret_key = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise InitDataError('signature mismatch')

    if max_age_seconds is None:
        max_age_seconds = getattr(settings, 'TELEGRAM_INIT_DATA_MAX_AGE', 24 * 60 * 60)
    try:
        auth_date = int(fields.get('auth_date', ''))
    except ValueError as exc:
        raise InitDataError('auth_date is missing') from exc
    current_time = time.time() if now is None else now
    if current_time - auth_date > max_age_seconds:
        raise InitDataError('initData is expired')

    try:
        user = json.loads(fields.get('user', ''))
    except ValueError as exc:
        raise InitDataError('user is missing') from exc
    if not isinstance(user, dict) or not user.get('id'):
        raise InitDataError('user id is missing')
    return user


def get_bot_token(request):
    """Токен бота тенанта; глобальный токен — только если у тенанта он не задан."""
    from tenants.scoping import bot_token_for
    return bot_token_for(getattr(request, 'tenant', None))


def get_verified_telegram_user(request):
    """
    Возвращает проверенного пользователя Telegram из заголовка запроса или None.
    Результат кэшируется на объекте запроса.
    """
    if hasattr(request, '_verified_telegram_user'):
        return request._verified_telegram_user

    user = None
    init_data = request.META.get(INIT_DATA_HEADER, '')
    if init_data:
        try:
            user = validate_init_data(init_data, get_bot_token(request))
        except InitDataError as exc:
            logger.warning(f'[TelegramInitData] Rejected initData: {exc}')
    request._verified_telegram_user = user
    return user


def _same_id(value, telegram_id):
    return str(value).strip() == str(telegram_id)


def verified_telegram_id_param(request, claimed=None):
    """
    telegram_id из query-параметра (или переданный claimed), только если он совпадает
    с проверенным по initData пользователем; иначе None.

    Для публичных эндпоинтов, где telegram_id лишь добавляет персональный прогресс:
    без подписи ответ строится как для анонима, а чужой прогресс не раскрывается.
    """
    if claimed is None:
        claimed = request.GET.get('telegram_id')
    if claimed in (None, ''):
        return None
    user = get_verified_telegram_user(request)
    if user and _same_id(claimed, user['id']):
        return str(claimed).strip()
    return None


class IsMiniAppUserOrReadOnly(BasePermission):
    """
    Чтение — без ограничений; запись — только с валидным initData.

    Если в запросе указан telegram_id (в URL, теле или query), он обязан совпадать
    с проверенным telegram_id — иначе 403. Так один пользователь не может действовать
    от имени другого.
    """

    message = 'Valid Telegram initData (X-Telegram-Init-Data header) is required.'
    require_for_safe_methods = False
    identity_fields = ('telegram_id', 'author_telegram_id', 'reporter_telegram_id')
    identity_kwargs = ('telegram_id',)

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS and not self.require_for_safe_methods:
            return True

        user = get_verified_telegram_user(request)
        if not user:
            return False
        telegram_id = user['id']

        kwargs = getattr(view, 'kwargs', {}) or {}
        for name in self.identity_kwargs:
            if kwargs.get(name) not in (None, '') and not _same_id(kwargs[name], telegram_id):
                self.message = 'telegram_id does not match the authenticated Telegram user.'
                return False

        sources = [request.query_params]
        if hasattr(request.data, 'get'):
            sources.append(request.data)
        for source in sources:
            for name in self.identity_fields:
                value = source.get(name)
                if value not in (None, '') and not _same_id(value, telegram_id):
                    self.message = 'telegram_id does not match the authenticated Telegram user.'
                    return False
        return True


class IsMiniAppUser(IsMiniAppUserOrReadOnly):
    """Валидный initData обязателен для любых методов, включая чтение."""

    require_for_safe_methods = True


class IsMiniAppUserByPk(IsMiniAppUserOrReadOnly):
    """Для MiniAppUserViewSet: pk в URL — это telegram_id пользователя."""

    identity_kwargs = ('telegram_id', 'pk')


class IsMiniAppUserByPkStrict(IsMiniAppUserByPk):
    """Как IsMiniAppUserByPk, но initData обязателен и для чтения (приватные данные профиля)."""

    require_for_safe_methods = True


class IsMiniAppFeedbackAuthor(IsMiniAppUser):
    """Обратная связь из Mini App: поле user_id — это telegram_id автора."""

    identity_fields = IsMiniAppUserOrReadOnly.identity_fields + ('user_id',)
