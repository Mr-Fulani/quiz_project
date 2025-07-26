from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Управление пользователями'

    def ready(self):
        """
        Подключает сигналы при запуске приложения.
        Этот метод вызывается при инициализации Django.
        """
        try:
            import accounts.signals  # noqa
        except ImportError:
            pass
