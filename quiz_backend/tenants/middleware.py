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

    # Очищаем хост от лишних слэшей для поиска
    clean_host = host.rstrip('/')
    # Хост без порта для запасного поиска
    host_no_port = clean_host.split(':')[0]

    try:
        from tenants.models import Tenant
        from django.db.models import Q
        from django.conf import settings

        # Ищем с учетом порта, без порта и со слэшами
        tenant = Tenant.objects.filter(
            Q(domain=clean_host) | Q(domain=clean_host + '/') |
            Q(domain=host_no_port) | Q(domain=host_no_port + '/') |
            Q(mini_app_domain=clean_host) | Q(mini_app_domain=host_no_port),
            is_active=True
        ).first()

        # Если не нашли, но мы в DEBUG режиме и это ngrok хост
        if not tenant and settings.DEBUG:
            ngrok_host = getattr(settings, 'NGROK_HOST', None)
            ngrok_slug = getattr(settings, 'NGROK_TENANT_SLUG', None)
            
            # Сравниваем очищенный хост с очищенным ngrok_host
            if ngrok_host and clean_host == ngrok_host.rstrip('/') and ngrok_slug:
                tenant = Tenant.objects.filter(slug=ngrok_slug, is_active=True).first()
                if tenant:
                    logger.info(f'[TenantMiddleware] Mapped ngrok host "{clean_host}" to development tenant "{tenant.slug}"')

        if tenant:
            _tenant_cache[host] = tenant
            logger.debug(f'[TenantMiddleware] Host "{clean_host}" → Tenant "{tenant.slug}"')
        else:
            # Не кэшируем None — при следующем запросе снова проверим БД.
            # Это важно: если тенант добавлен в БД после запуска сервера,
            # кэширование None заблокировало бы его обнаружение навсегда.
            logger.warning(f'[TenantMiddleware] No active tenant for host "{clean_host}" (not cached)')

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
        raw_host = request.META.get('HTTP_HOST', '')
        host = self._normalize_host(request.get_host())
        tenant = _get_tenant_by_host(host)
        logger.info(
            f"[TenantMiddleware] HTTP_HOST={raw_host!r} → normalized={host!r} → "
            f"tenant={tenant.slug if tenant else 'None (ПРОВЕРЬ mini_app_domain в админке!)'}"
        )
        request.tenant = tenant
        response = self.get_response(request)
        return response

    @staticmethod
    def _normalize_host(raw_host: str) -> str:
        """Убирает только www. и лишние пробелы. Порт сохраняем для точного поиска."""
        host = raw_host.lower().strip()
        if host.startswith('www.'):
            host = host[4:]
        return host
