# tenants/apps.py

from django.apps import AppConfig


class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tenants'
    verbose_name = 'Тенанты'

    def ready(self):
        from tenants.signals import setup_signals
        setup_signals()
