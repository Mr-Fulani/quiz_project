from django import template
from django.db.models import Count, Q
from tasks.models import TaskStatistics

register = template.Library()


@register.simple_tag(takes_context=True)
def get_popular_topics(context, limit=4):
    """
    Template tag to get popular topics based on statistics for the current tenant.
    """
    request = context.get('request')
    tenant = getattr(request, 'tenant', None) if request else None

    qs = TaskStatistics.objects.values('task__topic__name').annotate(
        total_attempts=Count('id'),
    ).filter(task__topic__isnull=False)

    if tenant:
        qs = qs.filter(task__tenant=tenant)
    else:
        # Если тенант не определен, не показываем ничего для безопасности
        return []

    qs = qs.order_by('-total_attempts')[:limit]

    topic_stats = list(qs)
    max_attempts = topic_stats[0]['total_attempts'] if topic_stats else 0

    popular_topics = []
    for i, stat in enumerate(topic_stats):
        pct = round((stat['total_attempts'] / max_attempts) * 100) if max_attempts > 0 else 0
        popular_topics.append({
            'id': i + 1,
            'name': stat['task__topic__name'].capitalize(),
            'popularity_percentage': pct
        })

    return popular_topics