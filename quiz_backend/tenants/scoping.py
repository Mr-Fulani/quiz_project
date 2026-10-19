"""
Фильтрация настроек/интеграций по тенанту в фоновом коде (Celery, сервисы публикации).

У вебхуков, учётных данных соцсетей и ссылок поле tenant nullable: записи без тенанта
считаются общими для всех тенантов (так они работали до мультитенантности).
Записи другого тенанта не используются никогда.
"""
from django.db.models import Q


def for_tenant_or_shared(queryset, tenant):
    """Записи тенанта и общие (tenant=None); записи других тенантов исключены."""
    if tenant is None:
        return queryset.filter(tenant__isnull=True)
    return queryset.filter(Q(tenant=tenant) | Q(tenant__isnull=True))
