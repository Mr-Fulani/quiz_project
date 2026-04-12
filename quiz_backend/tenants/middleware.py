# tenants/middleware.py

import logging
from django.db import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)

_tenant_cache = {}


def _get_tenant_by_host(host):
    """
    Ищет тенанта по домену. Кэширует результат в памяти.
    Возвращает объект Tenant или None.
    """
    if host in _tenant_cache:
        return _tenant_cache[host]

    try:
        from tenants.models import Tenant
        from django.db.models import Q

        tenant = Tenant.objects.filter(
            Q(domain=host) | Q(mini_app_domain=host),
            is_active=True
        ).first()

        if tenant:
            _tenant_cache[host] = tenant
            logger.debug(f'[TenantMiddleware] Host "{host}" → Tenant "{tenant.slug}"')
        else:
            logger.warning(f'[TenantMiddleware] No active tenant for host "{host}"')
            _tenant_cache[host] = None

        return tenant

    except (OperationalError, ProgrammingError):
        # БД не готова (например при первом запуске/migrate)
        logger.warning('[TenantMiddleware] DB not ready, skipping tenant resolution')
        return None
    except Exception as e:
        logger.error(f'[TenantMiddleware] Unexpected error: {e}')
        return None


def clear_tenant_cache():
    """
    Очищает кэш тенантов. Вызывай при изменении Tenant в admin.
    """
    global _tenant_cache
    _tenant_cache = {}
    logger.info('[TenantMiddleware] Tenant cache cleared')


class TenantMiddleware:
    """
    Определяет текущего тенанта по домену входящего запроса
    и помещает объект в request.tenant.

    Порядок определения:
        1. Убираем порт и www-префикс из Host
        2. Ищем тенанта по domain или mini_app_domain
        3. Если не найден — request.tenant = None (обрабатывается далее)

    Использование в views/templates:
        tenant = request.tenant
        if tenant:
            bot_token = tenant.bot_token
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = self._normalize_host(request.get_host())
        request.tenant = _get_tenant_by_host(host)
        response = self.get_response(request)
        return response

    @staticmethod
    def _normalize_host(raw_host: str) -> str:
        """Убирает порт и www. из Host-заголовка."""
        # Убираем порт (quiz-code.com:8000 → quiz-code.com)
        host = raw_host.split(':')[0].lower().strip()
        # Убираем www. (www.quiz-code.com → quiz-code.com)
        if host.startswith('www.'):
            host = host[4:]
        return host
