# tenants/branding.py
"""Данные тенанта для писем: название, email поддержки, ссылки на ресурсы (всё из админки)."""

from django.utils.translation import get_language


def email_branding(tenant, lang=None):
    """
    Контекст для шаблонов писем.

    site_name — название сайта тенанта (или домен), support_email — contact_email тенанта
    или email из «Данных владельца», social_links — активные «Ресурсы платформы».
    """
    if tenant is None:
        return {'site_name': '', 'support_email': '', 'social_links': []}

    from blog.models import PlatformResource, TenantInfo

    lang = lang or get_language() or 'en'
    info = TenantInfo.objects.filter(tenant=tenant).first()
    resources = PlatformResource.objects.filter(tenant=tenant, is_active=True).order_by('order')
    return {
        'site_name': tenant.site_name or tenant.name or tenant.domain,
        'support_email': tenant.contact_email or (info.email if info else ''),
        'social_links': [
            {'title': getattr(r, f'title_{lang}', None) or r.title_en, 'url': r.url}
            for r in resources
        ],
    }
