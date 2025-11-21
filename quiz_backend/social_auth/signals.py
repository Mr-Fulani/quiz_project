"""
Сигналы для приложения social_auth.

Обеспечивают автоматическую синхронизацию данных между SocialAccount и CustomUser.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='social_auth.SocialAccount')
def sync_social_fields_on_save(sender, instance, created, **kwargs):
    """
    Автоматически синхронизирует поля социальных сетей в CustomUser при сохранении SocialAccount.
    
    Когда создается или обновляется SocialAccount, данные из него подтягиваются
    в соответствующие поля пользователя (telegram, github, etc).
    """
    try:
        # Импортируем внутри функции чтобы избежать циклических импортов
        from social_auth.services import TelegramAuthService
        
        user = instance.user
        
        if user and hasattr(user, 'social_accounts'):
            # Синхронизируем поля социальных сетей
            TelegramAuthService._sync_social_fields_from_accounts(user)
            logger.debug(f"Автоматически синхронизированы поля социальных сетей для пользователя {getattr(user, 'username', 'unknown')} из {instance.provider}")
    except Exception as e:
        logger.warning(f"Ошибка при автоматической синхронизации полей социальных сетей: {e}")

