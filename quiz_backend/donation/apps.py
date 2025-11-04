from django.apps import AppConfig


class DonationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'donation'
    verbose_name = 'Donation'
    
    def ready(self):
        """
        Импортируем signals при инициализации приложения.
        """
        import donation.signals  # noqa: F401 