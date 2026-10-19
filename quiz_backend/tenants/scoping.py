"""
Фильтрация настроек/интеграций по тенанту в фоновом коде (Celery, сервисы публикации).

У вебхуков, учётных данных соцсетей и ссылок поле tenant nullable: записи без тенанта
считаются общими для всех тенантов (так они работали до мультитенантности).
Записи другого тенанта не используются никогда.
"""
from django.conf import settings
from django.db.models import Q


def bot_token_for(tenant):
    """
    Токен Telegram-бота тенанта; глобальный TELEGRAM_BOT_TOKEN — если у тенанта он не задан
    (так же выбирает бот, см. bot/tenancy.py). Каналы тенанта администрирует его бот.
    """
    return (getattr(tenant, 'bot_token', None) or '') or (settings.TELEGRAM_BOT_TOKEN or '')


def for_tenant_or_shared(queryset, tenant):
    """Записи тенанта и общие (tenant=None); записи других тенантов исключены."""
    if tenant is None:
        return queryset.filter(tenant__isnull=True)
    return queryset.filter(Q(tenant=tenant) | Q(tenant__isnull=True))


def site_host(request):
    """Хост основного сайта тенанта: для запросов с мини-аппа — домен сайта того же тенанта."""
    host = request.get_host()
    tenant = getattr(request, 'tenant', None)
    if tenant and tenant.mini_app_domain and host.split(':')[0] == tenant.mini_app_domain:
        return tenant.domain
    return host


def public_host(request):
    """Публичный хост для абсолютных ссылок: мини-апп тенанта, иначе его сайт, иначе хост запроса."""
    tenant = getattr(request, 'tenant', None)
    if tenant:
        return tenant.mini_app_domain or tenant.domain
    return request.get_host()


def site_url_for(tenant):
    """Адрес сайта тенанта (https://domain); без тенанта — PUBLIC_URL или SITE_URL из .env."""
    if tenant and tenant.domain:
        return tenant.site_url
    return (getattr(settings, 'PUBLIC_URL', '') or getattr(settings, 'SITE_URL', '') or '').rstrip('/')
