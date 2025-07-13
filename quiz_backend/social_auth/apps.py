from django.apps import AppConfig


class SocialAuthConfig(AppConfig):
    """
    Конфигурация приложения для социальной аутентификации.
    
    Обеспечивает авторизацию через различные социальные сети:
    - Telegram
    - GitHub (в будущем)
    - Google (в будущем)
    - VK (в будущем)
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'social_auth'
    verbose_name = 'Социальная аутентификация'
