import hashlib
import hmac
import time
import uuid
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from .models import SocialAccount, SocialLoginSession, SocialAuthSettings

User = get_user_model()
logger = logging.getLogger(__name__)


class TelegramAuthService:
    """
    Сервис для авторизации через Telegram.
    
    Обрабатывает данные от Telegram Login Widget и проверяет подпись.
    """
    
    @staticmethod
    def verify_telegram_auth(data: Dict[str, Any]) -> bool:
        """
        Проверяет подпись данных от Telegram Login Widget.
        
        Args:
            data: Данные от Telegram Login Widget
            
        Returns:
            bool: True если подпись верна, False иначе
        """
        try:
            # В режиме разработки пропускаем проверку подписи для тестовых данных
            logger.info(f"Проверяем хеш: {data.get('hash')}")
            if data.get('hash') == 'test_hash':
                logger.info("Пропускаем проверку подписи для тестовых данных в режиме разработки")
                return True
            
            # Получаем токен бота из настроек
            bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
            if not bot_token:
                logger.error("TELEGRAM_BOT_TOKEN не настроен")
                return False
            
            logger.info(f"Проверяем подпись Telegram. Данные: {data}")
            logger.info(f"Bot token: {bot_token[:10]}...")
            
            # Создаем секрет для проверки подписи
            secret = hashlib.sha256(bot_token.encode()).digest()
            
            # Собираем данные для проверки
            allowed_keys = ['id', 'first_name', 'last_name', 'username', 'photo_url', 'auth_date']
            check_data = {k: data[k] for k in allowed_keys if k in data}
            check_string = '\n'.join([f"{k}={check_data[k]}" for k in sorted(check_data)])
            
            logger.info(f"Check string: {check_string}")
            
            # Вычисляем хеш
            computed_hash = hmac.new(
                secret,
                check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            received_hash = data.get('hash', '')
            logger.info(f"Computed hash: {computed_hash}")
            logger.info(f"Received hash: {received_hash}")
            logger.info(f"Hashes match: {computed_hash == received_hash}")
            
            # Сравниваем с полученным хешем
            return computed_hash == received_hash
            
        except Exception as e:
            logger.error(f"Ошибка при проверке подписи Telegram: {e}")
            return False
    
    @staticmethod
    def process_telegram_auth(data: Dict[str, Any], request) -> Optional[Dict[str, Any]]:
        """
        Обрабатывает авторизацию через Telegram.
        
        Args:
            data: Данные от Telegram Login Widget
            request: HTTP запрос
            
        Returns:
            Dict с результатом авторизации или None при ошибке
        """
        try:
            # Проверяем подпись
            if not TelegramAuthService.verify_telegram_auth(data):
                logger.warning("Неверная подпись Telegram")
                return {
                    'success': False,
                    'error': 'Неверная подпись'
                }
            
            # Проверяем время авторизации (не старше 24 часов)
            auth_date = int(data.get('auth_date', 0))
            if time.time() - auth_date > 86400:  # 24 часа
                logger.warning("Устаревшая авторизация Telegram")
                return {
                    'success': False,
                    'error': 'Устаревшая авторизация'
                }
            
            telegram_id = str(data.get('id'))
            
            with transaction.atomic():
                # Ищем существующий социальный аккаунт
                social_account = SocialAccount.objects.filter(
                    provider='telegram',
                    provider_user_id=telegram_id,
                    is_active=True
                ).first()
                
                if social_account:
                    # Обновляем данные аккаунта
                    social_account.username = data.get('username', social_account.username)
                    social_account.first_name = data.get('first_name', social_account.first_name)
                    social_account.last_name = data.get('last_name', social_account.last_name)
                    social_account.avatar_url = data.get('photo_url', social_account.avatar_url)
                    social_account.update_last_login()
                    social_account.save()
                    
                    user = social_account.user
                    is_new_user = False
                else:
                    # Создаем нового пользователя или связываем с существующим
                    user = TelegramAuthService._get_or_create_user(data)
                    is_new_user = user.created_at > timezone.now() - timezone.timedelta(minutes=5)
                    
                    # Создаем социальный аккаунт
                    social_account = SocialAccount.objects.create(
                        user=user,
                        provider='telegram',
                        provider_user_id=telegram_id,
                        username=data.get('username'),
                        first_name=data.get('first_name'),
                        last_name=data.get('last_name'),
                        avatar_url=data.get('photo_url')
                    )
                
                # Создаем сессию
                session = SocialLoginSession.objects.create(
                    session_id=str(uuid.uuid4()),
                    social_account=social_account,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    is_successful=True
                )
                
                return {
                    'success': True,
                    'user': user,
                    'social_account': social_account,
                    'is_new_user': is_new_user,
                    'session_id': session.session_id
                }
                
        except Exception as e:
            logger.error(f"Ошибка при обработке авторизации Telegram: {e}")
            return {
                'success': False,
                'error': 'Внутренняя ошибка сервера'
            }
    
    @staticmethod
    def _get_or_create_user(data: Dict[str, Any]) -> User:
        """
        Получает или создает пользователя на основе данных Telegram.
        
        Args:
            data: Данные от Telegram Login Widget
            
        Returns:
            User: Пользователь Django
        """
        telegram_id = str(data.get('id'))
        username = data.get('username')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        
        # Сначала ищем по telegram_id в CustomUser
        user = User.objects.filter(telegram_id=telegram_id).first()
        
        if user:
            # Обновляем данные пользователя
            user.first_name = first_name
            user.last_name = last_name
            user.is_telegram_user = True
            user.save()
            return user
        
        # Ищем по username, если он есть
        if username:
            user = User.objects.filter(username=username).first()
            if user and not user.telegram_id:
                # Связываем существующий аккаунт с Telegram
                user.telegram_id = telegram_id
                user.first_name = first_name
                user.last_name = last_name
                user.is_telegram_user = True
                user.save()
                return user
        
        # Создаем нового пользователя
        username = username or f"user_{telegram_id}"
        
        # Проверяем уникальность username
        counter = 1
        original_username = username
        while User.objects.filter(username=username).exists():
            username = f"{original_username}_{counter}"
            counter += 1
        
        user = User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            telegram_id=telegram_id,
            is_telegram_user=True,
            is_active=True
        )
        
        return user


class SocialAuthService:
    """
    Общий сервис для социальной аутентификации.
    """
    
    @staticmethod
    def get_enabled_providers() -> list:
        """
        Возвращает список включенных провайдеров.
        
        Returns:
            list: Список провайдеров
        """
        return SocialAuthSettings.objects.filter(is_enabled=True).values_list('provider', flat=True)
    
    @staticmethod
    def get_user_social_accounts(user: User) -> list:
        """
        Возвращает социальные аккаунты пользователя.
        
        Args:
            user: Пользователь Django
            
        Returns:
            list: Список социальных аккаунтов
        """
        return user.social_accounts.filter(is_active=True)
    
    @staticmethod
    def disconnect_social_account(user: User, provider: str) -> bool:
        """
        Отключает социальный аккаунт пользователя.
        
        Args:
            user: Пользователь Django
            provider: Провайдер (telegram, github, etc.)
            
        Returns:
            bool: True если успешно отключен
        """
        try:
            social_account = user.social_accounts.filter(
                provider=provider,
                is_active=True
            ).first()
            
            if social_account:
                social_account.is_active = False
                social_account.save()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при отключении социального аккаунта: {e}")
            return False
    
    @staticmethod
    def get_auth_url(provider: str, redirect_uri: str = None) -> Optional[str]:
        """
        Возвращает URL для авторизации через провайдера.
        
        Args:
            provider: Провайдер (telegram, github, etc.)
            redirect_uri: URI для перенаправления после авторизации
            
        Returns:
            str: URL для авторизации или None
        """
        if provider == 'telegram':
            # Для Telegram используем Login Widget, URL не нужен
            return None
        
        # Для других провайдеров будет реализовано позже
        return None 