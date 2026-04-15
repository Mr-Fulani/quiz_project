# tenants/middleware.py

import logging
from urllib.parse import urlparse
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
        logger.debug(f'[TenantMiddleware] Lookup attempt for: clean={clean_host!r}, no_port={host_no_port!r}')
        
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
            logger.info(f'[TenantMiddleware] ✅ Resolved host "{clean_host}" to Tenant "{tenant.slug}"')
        else:
            # Не кэшируем None — при следующем запросе снова проверим БД.
            # Это важно: если тенант добавлен в БД после запуска сервера,
            # кэширование None заблокировало бы его обнаружение навсегда.
            logger.warning(f'[TenantMiddleware] ❌ No active tenant for host "{clean_host}". Check admin settings (domain/mini_app_domain)!')

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
        tenant = None

        # 0. Явное указание тенанта (например, от API-шлюза или mini-app)
        # Поддерживаем заголовок X-Tenant-Slug (регистр не важен).
        tenant_slug = (
            request.META.get('HTTP_X_TENANT_SLUG')
            or request.META.get('HTTP_X_TENANT')
        )
        if tenant_slug:
            try:
                from tenants.models import Tenant
                tenant = Tenant.objects.filter(slug=str(tenant_slug).strip(), is_active=True).first()
                if tenant:
                    logger.info(f"[TenantMiddleware] ✅ Resolved tenant via X-Tenant-Slug: {tenant.slug!r}")
            except (OperationalError, ProgrammingError):
                logger.warning('[TenantMiddleware] DB not ready, skipping tenant resolution by slug')
            except Exception as e:
                logger.error(f'[TenantMiddleware] Unexpected error while resolving tenant by slug: {e}')

        # 1. Сначала пробуем X-Forwarded-Host (доверенный заголовок от прокси/mini_app)
        forwarded_host = request.META.get('HTTP_X_FORWARDED_HOST', '')
        
        if not tenant and forwarded_host:
            # Берём первый хост если их список (стандарт для прокси)
            first_forwarded = forwarded_host.split(',')[0].strip()
            host = self._normalize_host(first_forwarded)
            tenant = _get_tenant_by_host(host)
            if tenant:
                logger.debug(f"[TenantMiddleware] ✅ Tenant {tenant.slug} resolved via X-Forwarded-Host: {host!r}")

        # 2. Если не нашли через Forwarded, пробуем обычный Host
        if not tenant:
            raw_host = request.get_host()
            host = self._normalize_host(raw_host)
            tenant = _get_tenant_by_host(host)
            if tenant:
                logger.debug(f"[TenantMiddleware] ✅ Tenant {tenant.slug} resolved via Host: {host!r}")

        # 3. Если backend на общем домене (api.*), пробуем определить тенанта по Origin/Referer.
        # Это частый кейс для Telegram Mini App: фронт на mini_app_domain, API на другом хосте.
        if not tenant:
            origin = request.META.get('HTTP_ORIGIN', '')
            referer = request.META.get('HTTP_REFERER', '')

            for raw in (origin, referer):
                if not raw:
                    continue
                try:
                    parsed = urlparse(raw)
                    if parsed.hostname:
                        host = self._normalize_host(parsed.hostname)
                        tenant = _get_tenant_by_host(host)
                        if tenant:
                            logger.info(
                                f"[TenantMiddleware] ✅ Tenant {tenant.slug} resolved via "
                                f"{'Origin' if raw == origin else 'Referer'}: {host!r}"
                            )
                            break
                except Exception as e:
                    logger.debug(f"[TenantMiddleware] Failed to parse Origin/Referer {raw!r}: {e}")

        # 4. Безопасный фоллбэк для односайтового режима: если активен ровно один тенант,
        # назначаем его, чтобы мини-апп не падал при отсутствии корректных заголовков.
        if not tenant:
            try:
                from tenants.models import Tenant
                active_tenants = Tenant.objects.filter(is_active=True)
                if active_tenants.count() == 1:
                    tenant = active_tenants.first()
                    logger.warning(
                        f"[TenantMiddleware] ⚠ Fallback to single active tenant {tenant.slug!r}. "
                        f"Configure domain/mini_app_domain or proxy headers for strict isolation."
                    )
            except (OperationalError, ProgrammingError):
                logger.warning('[TenantMiddleware] DB not ready, skipping single-tenant fallback')
            except Exception as e:
                logger.error(f'[TenantMiddleware] Unexpected error in single-tenant fallback: {e}')

        # 3. Дополнительное логирование для отладки если всё ещё None
        if not tenant:
            logger.info(
                f"[TenantMiddleware] ⚠ No tenant resolved. "
                f"HTTP_HOST={request.META.get('HTTP_HOST')!r}, "
                f"X-Forwarded-Host={forwarded_host!r}, "
                f"Origin={request.META.get('HTTP_ORIGIN')!r}, "
                f"Referer={request.META.get('HTTP_REFERER')!r}, "
                f"Normalized_Host={self._normalize_host(request.get_host())!r}"
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
