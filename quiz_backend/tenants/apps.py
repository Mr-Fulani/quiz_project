# tenants/apps.py

from django.apps import AppConfig


class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tenants'
    verbose_name = 'Тенанты'

    def ready(self):
        from corsheaders.signals import check_request_enabled
        from tenants.origins import cors_allow_tenant_origins
        from tenants.signals import setup_signals
        setup_signals()
        check_request_enabled.connect(cors_allow_tenant_origins, dispatch_uid='tenants_cors_origins')
