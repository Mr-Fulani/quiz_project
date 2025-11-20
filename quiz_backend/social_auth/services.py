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
            # В режиме разработки пропускаем проверку подписи для мок данных
            if (getattr(settings, 'MOCK_TELEGRAM_AUTH', False) and 
                data.get('hash') in ['test_hash', 'mock_hash_for_development']):
                logger.info("Пропущена проверка подписи для мок данных")
                return True
            
            # Получаем токен бота из настроек
            bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
            if not bot_token:
                logger.error("TELEGRAM_BOT_TOKEN не настроен в settings")
                return False
            
            # Проверяем наличие обязательных полей
            if 'hash' not in data or not data.get('hash'):
                logger.error("Отсутствует hash в данных от Telegram")
                return False
            
            if 'auth_date' not in data:
                logger.error("Отсутствует auth_date в данных от Telegram")
                return False
            
            # Создаем секрет для проверки подписи
            secret = hashlib.sha256(bot_token.encode()).digest()
            
            # Собираем данные для проверки (только те поля, которые есть в данных)
            # Важно: включаем только те поля, которые присутствуют в исходных данных
            allowed_keys = ['id', 'first_name', 'last_name', 'username', 'photo_url', 'auth_date']
            check_data = {}
            for k in allowed_keys:
                if k in data and data[k] is not None and data[k] != '':
                    # Преобразуем в строку, как требует Telegram
                    check_data[k] = str(data[k])
            
            # Telegram требует сортировку ключей по алфавиту
            check_string = '\n'.join([
                f"{k}={check_data[k]}" for k in sorted(check_data.keys())
            ])
            
            logger.info(f"Check string для проверки подписи: {check_string}")
            
            # Вычисляем хеш
            computed_hash = hmac.new(
                secret,
                check_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            received_hash = data.get('hash', '')
            
            logger.info(f"Computed hash: {computed_hash[:20]}..., received hash: {received_hash[:20]}...")
            
            # Сравниваем с полученным хешем
            is_valid = computed_hash == received_hash
            
            if not is_valid:
                logger.warning(f"Неверная подпись Telegram. Computed: {computed_hash}, Received: {received_hash}")
                logger.warning(f"Данные для проверки: {check_data}")
            
            return is_valid
            
        except Exception as e:
            import traceback
            logger.error(f"Ошибка при проверке подписи Telegram: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
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
            logger.info(f"Проверка подписи Telegram для данных: id={data.get('id')}, auth_date={data.get('auth_date')}")
            if not TelegramAuthService.verify_telegram_auth(data):
                logger.warning("Неверная подпись Telegram - авторизация отклонена")
                logger.warning(f"Полученные данные: {data}")
                return {
                    'success': False,
                    'error': 'Неверная подпись. Проверьте настройки бота в BotFather.'
                }
            logger.info("Подпись Telegram успешно проверена")
            
            # Проверяем время авторизации (не старше 24 часов)
            auth_date = data.get('auth_date')
            if auth_date:
                auth_date = int(auth_date)
                if time.time() - auth_date > 86400:  # 24 часа
                    logger.warning("Устаревшая авторизация Telegram")
                    return {
                        'success': False,
                        'error': 'Устаревшая авторизация'
                    }
            else:
                logger.warning("Отсутствует auth_date в данных Telegram")
                return {
                    'success': False,
                    'error': 'Некорректные данные авторизации'
                }
            
            telegram_id = str(data.get('id'))
            
            if not telegram_id or telegram_id == 'None':
                logger.error("Отсутствует или неверный telegram_id в данных")
                return {
                    'success': False,
                    'error': 'Некорректные данные авторизации'
                }
            
            logger.info(f"Обработка авторизации для telegram_id={telegram_id}")
            
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
                    logger.info(f"Найден существующий социальный аккаунт для telegram_id={telegram_id}, пользователь: {user.username}, is_active={user.is_active}")
                else:
                    # Создаем нового пользователя или связываем с существующим
                    user = TelegramAuthService._get_or_create_user(data)
                    is_new_user = user.created_at > timezone.now() - timezone.timedelta(minutes=5)
                    logger.info(f"Создан/найден пользователь для telegram_id={telegram_id}, username: {user.username}, is_active={user.is_active}, is_new={is_new_user}")
                    
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
                    
                    # Автоматически связываем с существующими пользователями
                    try:
                        linked_count = social_account.auto_link_existing_users()
                        if linked_count > 0:
                            logger.info(f"Автоматически связано {linked_count} пользователей для telegram_id={telegram_id}")
                            # Обновляем объект user после связывания
                            user.refresh_from_db()
                            # Обновляем социальный аккаунт
                            social_account.refresh_from_db()
                            logger.info(f"Пользователь после связывания: {user.username}, is_active={user.is_active}")
                    except Exception as e:
                        logger.warning(f"Ошибка при автоматическом связывании для telegram_id={telegram_id}: {e}")
                
                # Убеждаемся что пользователь активен перед возвратом
                user.refresh_from_db()
                if not user.is_active:
                    logger.error(f"Пользователь {user.username} не активен после авторизации!")
                    return {
                        'success': False,
                        'error': 'Аккаунт неактивен'
                    }
                
                # Создаем сессию
                session = SocialLoginSession.objects.create(
                    session_id=str(uuid.uuid4()),
                    social_account=social_account,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    is_successful=True
                )
                
                logger.info(f"Авторизация успешна: user={user.username}, telegram_id={telegram_id}, session_id={session.session_id}")
                
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
        telegram_id = str(data.get('id', ''))
        if not telegram_id or telegram_id == 'None':
            raise ValueError("telegram_id обязателен для создания пользователя")
        
        username = data.get('username') or ''
        first_name = data.get('first_name', '') or ''
        last_name = data.get('last_name', '') or ''
        
        logger.info(f"Поиск/создание пользователя для telegram_id={telegram_id}, username={username}")
        
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
        if username and username.strip():
            user = User.objects.filter(username=username).first()
            if user and (not user.telegram_id or user.telegram_id != telegram_id):
                # Связываем существующий аккаунт с Telegram
                logger.info(f"Связывание существующего пользователя {user.username} с telegram_id={telegram_id}")
                user.telegram_id = telegram_id
                user.first_name = first_name or user.first_name
                user.last_name = last_name or user.last_name
                user.is_telegram_user = True
                user.save()
                return user
        
        # Создаем нового пользователя
        # Генерируем username если его нет
        if not username or not username.strip():
            username = f"user_{telegram_id}"
        
        # Проверяем уникальность username
        counter = 1
        original_username = username
        while User.objects.filter(username=username).exists():
            username = f"{original_username}_{counter}"
            counter += 1
            if counter > 1000:  # Защита от бесконечного цикла
                username = f"user_{telegram_id}_{int(time.time())}"
                break
        
        logger.info(f"Создание нового пользователя: username={username}, telegram_id={telegram_id}")
        user = User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            telegram_id=telegram_id,
            is_telegram_user=True,
            is_active=True
        )
        
        logger.info(f"Пользователь создан: id={user.id}, username={user.username}, telegram_id={user.telegram_id}")
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