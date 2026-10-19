from django.http import JsonResponse


def current_tenant(request):
    """Публичные данные текущего тенанта (по домену запроса) — для мини-аппа и фронтенда."""
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'detail': 'Тенант не определён'}, status=404)
    return JsonResponse({
        'slug': tenant.slug,
        'name': tenant.name,
        'site_name': tenant.site_name or tenant.name,
        'domain': tenant.domain,
        'site_url': tenant.site_url,
        'mini_app_url': tenant.mini_app_url,
        'bot_username': tenant.bot_username,
        'bot_link': tenant.bot_link,
        'mini_app_link': tenant.mini_app_link,
    })
