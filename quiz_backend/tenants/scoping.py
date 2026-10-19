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
