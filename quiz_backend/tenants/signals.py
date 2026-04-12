# tenants/signals.py

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _clear_cache():
    """Сбрасывает кэш тенантов в middleware."""
    try:
        from tenants.middleware import clear_tenant_cache
        clear_tenant_cache()
        logger.info('[Tenants] Tenant cache cleared after model change.')
    except Exception as e:
        logger.error(f'[Tenants] Failed to clear tenant cache: {e}')


def setup_signals():
    from tenants.models import Tenant

    @receiver(post_save, sender=Tenant)
    def on_tenant_save(sender, instance, **kwargs):
        _clear_cache()

    @receiver(post_delete, sender=Tenant)
    def on_tenant_delete(sender, instance, **kwargs):
        _clear_cache()
