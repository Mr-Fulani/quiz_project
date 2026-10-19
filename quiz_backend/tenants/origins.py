"""
Домены активных тенантов как доверенные источники запросов (CORS и CSRF).

Списки доменов в settings не нужны: добавили или сменили домен тенанта в админке —
его сайт и мини-апп сразу доверенные. Дополнительные источники — через .env
(CORS_ALLOWED_ORIGINS, CSRF_TRUSTED_ORIGINS).
"""
import logging
from urllib.parse import urlsplit

from django.core.cache import cache
from django.db import DatabaseError
from django.middleware.csrf import CsrfViewMiddleware

logger = logging.getLogger(__name__)

CACHE_KEY = 'tenants:trusted_hosts'
CACHE_TTL = 300


def tenant_hosts():
    """Хосты активных тенантов: domain, www.domain, mini_app_domain."""
    hosts = cache.get(CACHE_KEY)
    if hosts is None:
        from tenants.models import Tenant
        hosts = set()
        try:
            for domain, mini_domain in Tenant.objects.filter(is_active=True).values_list('domain', 'mini_app_domain'):
                for host in (domain, f'www.{domain}' if domain else None, mini_domain):
                    if host:
                        hosts.add(host.strip().strip('/').lower())
        except DatabaseError as e:
            logger.warning(f'[tenants.origins] Не удалось прочитать домены тенантов: {e}')
            return set()
        cache.set(CACHE_KEY, hosts, CACHE_TTL)
    return hosts


def clear_tenant_hosts_cache():
    cache.delete(CACHE_KEY)


def is_tenant_origin(origin):
    """Origin вида https://host[:port] принадлежит активному тенанту (только https)."""
    if not origin:
        return False
    parts = urlsplit(origin)
    return parts.scheme == 'https' and (parts.hostname or '').lower() in tenant_hosts()


def cors_allow_tenant_origins(sender, request, **kwargs):
    """Обработчик corsheaders.signals.check_request_enabled."""
    return is_tenant_origin(request.headers.get('Origin'))


class TenantCsrfViewMiddleware(CsrfViewMiddleware):
    """CsrfViewMiddleware, который дополнительно доверяет Origin доменов активных тенантов."""

    def _origin_verified(self, request):
        return super()._origin_verified(request) or is_tenant_origin(request.META.get('HTTP_ORIGIN'))
