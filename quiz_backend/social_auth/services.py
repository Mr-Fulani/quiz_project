import hashlib
import hmac
import time
import uuid
import logging
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.core.files.base import ContentFile
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
                    updated = False
                    if data.get('username') and data.get('username') != social_account.username:
                        social_account.username = data.get('username')
                        updated = True
                    if data.get('first_name') and data.get('first_name') != social_account.first_name:
                        social_account.first_name = data.get('first_name')
                        updated = True
                    if data.get('last_name') and data.get('last_name') != social_account.last_name:
                        social_account.last_name = data.get('last_name')
                        updated = True
                    if data.get('photo_url') and data.get('photo_url') != social_account.avatar_url:
                        social_account.avatar_url = data.get('photo_url')
                        updated = True
                    
                    social_account.update_last_login()
                    if updated:
                        social_account.save()
                        logger.info(f"Данные SocialAccount обновлены: username={social_account.username}, first_name={social_account.first_name}, last_name={social_account.last_name}")
                    
                    # Также обновляем данные пользователя и аватарку
                    user_updated = False
                    if data.get('first_name') and data.get('first_name') != user.first_name:
                        user.first_name = data.get('first_name')
                        user_updated = True
                    if data.get('last_name') and data.get('last_name') != user.last_name:
                        user.last_name = data.get('last_name')
                        user_updated = True
                    
                    # Загружаем аватарку если есть photo_url и у пользователя еще нет аватарки
                    photo_url = data.get('photo_url')
                    if photo_url and not user.avatar:
                        if TelegramAuthService._download_avatar_from_url(photo_url, user):
                            user_updated = True
                    
                    if user_updated:
                        user.save()
                        logger.info(f"Данные пользователя обновлены: {user.username}, first_name={user.first_name}, last_name={user.last_name}")
                    
                    user = social_account.user
                    is_new_user = False
                    logger.info(f"Найден существующий социальный аккаунт для telegram_id={telegram_id}, пользователь: {user.username}, is_active={user.is_active}")
                    
                    # Автоматически связываем с существующими пользователями если связи еще не установлены
                    try:
                        linked_count = social_account.auto_link_existing_users()
                        if linked_count > 0:
                            logger.info(f"Автоматически связано {linked_count} пользователей для существующего social_account telegram_id={telegram_id}")
                            social_account.refresh_from_db()
                    except Exception as e:
                        logger.warning(f"Ошибка при автоматическом связывании для существующего social_account telegram_id={telegram_id}: {e}")
                    
                    # После обновления существующего social_account также устанавливаем обратную связь MiniAppUser -> CustomUser
                    # и объединяем статистику если MiniAppUser был связан
                    try:
                        from accounts.models import MiniAppUser
                        from tasks.models import MiniAppTaskStatistics
                        
                        # Обновляем social_account чтобы получить свежие связи
                        social_account.refresh_from_db()
                        
                        # Проверяем есть ли связанный MiniAppUser
                        if hasattr(social_account, 'mini_app_user') and social_account.mini_app_user:
                            mini_app_user = social_account.mini_app_user
                            
                            # Устанавливаем linked_custom_user если не установлен
                            if not mini_app_user.linked_custom_user:
                                mini_app_user.linked_custom_user = user
                                mini_app_user.save(update_fields=['linked_custom_user'])
                                logger.info(f"Установлена связь MiniAppUser (telegram_id={telegram_id}) -> CustomUser (id={user.id}, username={user.username})")
                            
                            # Обновляем данные MiniAppUser из Telegram
                            mini_app_updated = False
                            if data.get('first_name') and data.get('first_name') != mini_app_user.first_name:
                                mini_app_user.first_name = data.get('first_name')
                                mini_app_updated = True
                            if data.get('last_name') and data.get('last_name') != mini_app_user.last_name:
                                mini_app_user.last_name = data.get('last_name')
                                mini_app_updated = True
                            
                            # Обновляем telegram_photo_url если есть
                            photo_url = data.get('photo_url')
                            if photo_url and photo_url != mini_app_user.telegram_photo_url:
                                mini_app_user.telegram_photo_url = photo_url
                                mini_app_updated = True
                            
                            if mini_app_updated:
                                mini_app_user.save()
                                logger.info(f"Обновлены данные MiniAppUser для telegram_id={telegram_id}")
                            
                            # Объединяем статистику Mini App с основной статистикой
                            try:
                                # Находим всю статистику MiniAppUser которая еще не связана
                                unlinked_stats = MiniAppTaskStatistics.objects.filter(
                                    mini_app_user=mini_app_user,
                                    linked_statistics__isnull=True
                                )
                                
                                if unlinked_stats.exists():
                                    merged_count = 0
                                    with transaction.atomic():
                                        for mini_app_stat in unlinked_stats:
                                            try:
                                                mini_app_stat.merge_to_main_statistics(user)
                                                merged_count += 1
                                                logger.info(f"Объединена статистика задачи {mini_app_stat.task_id} для пользователя {user.username}")
                                            except Exception as merge_error:
                                                logger.warning(f"Ошибка при объединении статистики задачи {mini_app_stat.task_id}: {merge_error}")
                                    
                                    if merged_count > 0:
                                        logger.info(f"Успешно объединено {merged_count} записей статистики Mini App с основной статистикой для пользователя {user.username}")
                            except Exception as stats_error:
                                logger.warning(f"Ошибка при объединении статистики Mini App для telegram_id={telegram_id}: {stats_error}")
                        
                    except ImportError as import_error:
                        logger.warning(f"Не удалось импортировать модели для связывания MiniAppUser: {import_error}")
                    except Exception as linking_error:
                        logger.warning(f"Ошибка при установке связи MiniAppUser -> CustomUser для telegram_id={telegram_id}: {linking_error}")
                else:
                    # Создаем нового пользователя или связываем с существующим
                    user = TelegramAuthService._get_or_create_user(data)
                    is_new_user = user.created_at > timezone.now() - timezone.timedelta(minutes=5)
                    logger.info(f"Создан/найден пользователь для telegram_id={telegram_id}, username: {user.username}, is_active={user.is_active}, is_new={is_new_user}")
                    
                    # Создаем или обновляем социальный аккаунт
                    # username из Telegram должен идти в SocialAccount.username, а не в User.username
                    social_account, created = SocialAccount.objects.get_or_create(
                        user=user,
                        provider='telegram',
                        provider_user_id=telegram_id,
                        defaults={
                            'username': data.get('username'),
                            'first_name': data.get('first_name'),
                            'last_name': data.get('last_name'),
                            'avatar_url': data.get('photo_url')
                        }
                    )
                    
                    # Обновляем данные если аккаунт уже существовал
                    if not created:
                        updated = False
                        if data.get('username') and data.get('username') != social_account.username:
                            social_account.username = data.get('username')
                            updated = True
                        if data.get('first_name') and data.get('first_name') != social_account.first_name:
                            social_account.first_name = data.get('first_name')
                            updated = True
                        if data.get('last_name') and data.get('last_name') != social_account.last_name:
                            social_account.last_name = data.get('last_name')
                            updated = True
                        if data.get('photo_url') and data.get('photo_url') != social_account.avatar_url:
                            social_account.avatar_url = data.get('photo_url')
                            updated = True
                        
                        if updated:
                            social_account.update_last_login()
                            social_account.save()
                            logger.info(f"Данные SocialAccount обновлены для пользователя {user.username}")
                    
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
                        
                        # После auto_link_existing_users устанавливаем обратную связь MiniAppUser -> CustomUser
                        # и объединяем статистику если MiniAppUser был связан
                        try:
                            from accounts.models import MiniAppUser
                            from tasks.models import MiniAppTaskStatistics
                            
                            # Проверяем есть ли связанный MiniAppUser
                            if hasattr(social_account, 'mini_app_user') and social_account.mini_app_user:
                                mini_app_user = social_account.mini_app_user
                                
                                # Устанавливаем linked_custom_user если не установлен
                                if not mini_app_user.linked_custom_user:
                                    mini_app_user.linked_custom_user = user
                                    mini_app_user.save(update_fields=['linked_custom_user'])
                                    logger.info(f"Установлена связь MiniAppUser (telegram_id={telegram_id}) -> CustomUser (id={user.id}, username={user.username})")
                                
                                # Обновляем данные MiniAppUser из Telegram
                                mini_app_updated = False
                                if data.get('first_name') and data.get('first_name') != mini_app_user.first_name:
                                    mini_app_user.first_name = data.get('first_name')
                                    mini_app_updated = True
                                if data.get('last_name') and data.get('last_name') != mini_app_user.last_name:
                                    mini_app_user.last_name = data.get('last_name')
                                    mini_app_updated = True
                                
                                # Обновляем telegram_photo_url если есть
                                photo_url = data.get('photo_url')
                                if photo_url and photo_url != mini_app_user.telegram_photo_url:
                                    mini_app_user.telegram_photo_url = photo_url
                                    mini_app_updated = True
                                
                                if mini_app_updated:
                                    mini_app_user.save()
                                    logger.info(f"Обновлены данные MiniAppUser для telegram_id={telegram_id}")
                                
                                # Объединяем статистику Mini App с основной статистикой
                                try:
                                    # Находим всю статистику MiniAppUser которая еще не связана
                                    unlinked_stats = MiniAppTaskStatistics.objects.filter(
                                        mini_app_user=mini_app_user,
                                        linked_statistics__isnull=True
                                    )
                                    
                                    if unlinked_stats.exists():
                                        merged_count = 0
                                        with transaction.atomic():
                                            for mini_app_stat in unlinked_stats:
                                                try:
                                                    mini_app_stat.merge_to_main_statistics(user)
                                                    merged_count += 1
                                                    logger.info(f"Объединена статистика задачи {mini_app_stat.task_id} для пользователя {user.username}")
                                                except Exception as merge_error:
                                                    logger.warning(f"Ошибка при объединении статистики задачи {mini_app_stat.task_id}: {merge_error}")
                                        
                                        if merged_count > 0:
                                            logger.info(f"Успешно объединено {merged_count} записей статистики Mini App с основной статистикой для пользователя {user.username}")
                                except Exception as stats_error:
                                    logger.warning(f"Ошибка при объединении статистики Mini App для telegram_id={telegram_id}: {stats_error}")
                            
                        except ImportError as import_error:
                            logger.warning(f"Не удалось импортировать модели для связывания MiniAppUser: {import_error}")
                        except Exception as linking_error:
                            logger.warning(f"Ошибка при установке связи MiniAppUser -> CustomUser для telegram_id={telegram_id}: {linking_error}")
                            
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
    def _download_avatar_from_url(photo_url: str, user: User) -> bool:
        """
        Загружает аватарку из URL и сохраняет в поле avatar пользователя.
        
        Args:
            photo_url: URL аватарки из Telegram
            user: Пользователь Django
            
        Returns:
            bool: True если аватарка успешно загружена, False иначе
        """
        if not photo_url or not photo_url.strip():
            return False
        
        try:
            
            # Загружаем изображение
            req = urllib.request.Request(photo_url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                image_data = response.read()
                
                # Определяем расширение файла
                content_type = response.headers.get('Content-Type', '')
                ext = 'jpg'  # по умолчанию
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = 'jpg'
                elif 'png' in content_type:
                    ext = 'png'
                elif 'webp' in content_type:
                    ext = 'webp'
                else:
                    # Пытаемся определить по URL
                    parsed_url = urllib.parse.urlparse(photo_url)
                    path = parsed_url.path.lower()
                    if path.endswith('.png'):
                        ext = 'png'
                    elif path.endswith('.webp'):
                        ext = 'webp'
                    elif path.endswith('.jpg') or path.endswith('.jpeg'):
                        ext = 'jpg'
                
                # Создаем имя файла
                filename = f"telegram_avatar_{user.telegram_id}_{int(time.time())}.{ext}"
                
                # Сохраняем в поле avatar
                user.avatar.save(filename, ContentFile(image_data), save=True)
                logger.info(f"Аватарка загружена из Telegram для пользователя {user.username}: {filename}")
                return True
                
        except Exception as e:
            logger.warning(f"Не удалось загрузить аватарку из {photo_url}: {e}")
            return False
    
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
        
        # username из Telegram идет в SocialAccount, а не в User.username
        telegram_username = data.get('username') or ''
        first_name = data.get('first_name', '') or ''
        last_name = data.get('last_name', '') or ''
        photo_url = data.get('photo_url', '') or ''
        
        logger.info(f"Поиск/создание пользователя для telegram_id={telegram_id}, telegram_username={telegram_username}, first_name={first_name}, last_name={last_name}")
        
        # Сначала ищем по telegram_id в CustomUser
        user = User.objects.filter(telegram_id=telegram_id).first()
        
        if user:
            # Обновляем данные пользователя
            updated = False
            if first_name and first_name != user.first_name:
                user.first_name = first_name
                updated = True
            if last_name and last_name != user.last_name:
                user.last_name = last_name
                updated = True
            if not user.is_telegram_user:
                user.is_telegram_user = True
                updated = True
            
            # Загружаем аватарку если есть photo_url и у пользователя еще нет аватарки
            if photo_url and not user.avatar:
                if TelegramAuthService._download_avatar_from_url(photo_url, user):
                    updated = True
                    logger.info(f"Аватарка загружена для существующего пользователя {user.username}")
            # Опционально: можно обновлять аватарку при каждом входе если нужно
            # elif photo_url and user.avatar:
            #     if TelegramAuthService._download_avatar_from_url(photo_url, user):
            #         updated = True
            
            if updated:
                user.save()
                logger.info(f"Данные пользователя обновлены: {user.username}, first_name={user.first_name}, last_name={user.last_name}")
            
            return user
        
        # Пытаемся найти существующего пользователя по username из Telegram
        # Это помогает связать существующие аккаунты на сайте с Telegram
        if telegram_username and telegram_username.strip():
            existing_user = User.objects.filter(username=telegram_username).first()
            if existing_user:
                # Если найден пользователь без telegram_id или с другим telegram_id, связываем его
                if not existing_user.telegram_id or str(existing_user.telegram_id) != telegram_id:
                    logger.info(f"Связывание существующего пользователя {existing_user.username} с telegram_id={telegram_id}")
                    existing_user.telegram_id = telegram_id
                    if first_name and first_name != existing_user.first_name:
                        existing_user.first_name = first_name
                    if last_name and last_name != existing_user.last_name:
                        existing_user.last_name = last_name
                    if not existing_user.is_telegram_user:
                        existing_user.is_telegram_user = True
                    
                    # Загружаем аватарку если есть
                    if photo_url and not existing_user.avatar:
                        TelegramAuthService._download_avatar_from_url(photo_url, existing_user)
                    
                    existing_user.save()
                    logger.info(f"Пользователь {existing_user.username} успешно связан с telegram_id={telegram_id}")
                    return existing_user
        
        # Если не нашли существующего пользователя, создаем нового
        # Генерируем уникальный username для User
        # ВАЖНО: username из Telegram идет в SocialAccount.username, а не в User.username
        # Для User.username генерируем уникальное имя на основе first_name/last_name или telegram_id
        if first_name and last_name:
            # Используем first_name + last_name
            base_username = f"{first_name}_{last_name}".lower().replace(' ', '_')
            # Убираем спецсимволы, оставляем только буквы, цифры и подчеркивания
            base_username = ''.join(c for c in base_username if c.isalnum() or c == '_')
            # Ограничиваем длину
            if len(base_username) > 30:
                base_username = base_username[:30]
        elif first_name:
            base_username = first_name.lower().replace(' ', '_')
            base_username = ''.join(c for c in base_username if c.isalnum() or c == '_')
            if len(base_username) > 30:
                base_username = base_username[:30]
        elif telegram_username:
            # Используем telegram username как основу, но добавим префикс чтобы избежать конфликтов
            base_username = f"tg_{telegram_username}"
        else:
            base_username = f"user_{telegram_id}"
        
        # Проверяем уникальность username
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1
            if counter > 1000:  # Защита от бесконечного цикла
                username = f"user_{telegram_id}_{int(time.time())}"
                break
        
        logger.info(f"Создание нового пользователя: username={username}, telegram_id={telegram_id}, telegram_username={telegram_username}")
        user = User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            telegram_id=telegram_id,
            is_telegram_user=True,
            is_active=True
        )
        
        # Загружаем аватарку если есть
        if photo_url:
            TelegramAuthService._download_avatar_from_url(photo_url, user)
        
        logger.info(f"Пользователь создан: id={user.id}, username={user.username}, telegram_id={user.telegram_id}, first_name={user.first_name}, last_name={user.last_name}")
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