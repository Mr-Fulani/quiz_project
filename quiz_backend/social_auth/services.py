import hashlib
import hmac
import time
import uuid
import logging
import urllib.request
import urllib.parse
import os
import requests
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
                    # Получаем пользователя из social_account сразу
                    user = social_account.user
                    is_new_user = False
                    logger.info(f"Найден существующий социальный аккаунт для telegram_id={telegram_id}, пользователь: {user.username}, is_active={user.is_active}")
                    
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
                    
                    # Синхронизируем поля социальных сетей из SocialAccount
                    if TelegramAuthService._sync_social_fields_from_accounts(user):
                        user_updated = True
                    
                    if user_updated:
                        user.save()
                        logger.info(f"Данные пользователя обновлены: {user.username}, first_name={user.first_name}, last_name={user.last_name}")
                    
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
                            changed_social_fields = []  # Инициализируем список измененных полей
                            
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
                            
                            # Синхронизируем поля социальных сетей из CustomUser в MiniAppUser
                            # Это обеспечивает что данные соцсетей подтягиваются везде где используется одна БД
                            if user:
                                user.refresh_from_db()
                                social_fields_updated = False
                                
                                # Список полей социальных сетей для синхронизации
                                # Исключаем telegram, так как он управляется через SocialAccount
                                social_fields = ['github', 'instagram', 'facebook', 'linkedin', 'youtube', 'website']
                                
                                for field in social_fields:
                                    custom_user_value = getattr(user, field, None)
                                    mini_app_value = getattr(mini_app_user, field, None)
                                    
                                    # Обновляем только если в CustomUser есть значение и оно отличается
                                    if custom_user_value and custom_user_value.strip():
                                        if not mini_app_value or mini_app_value.strip() != custom_user_value.strip():
                                            setattr(mini_app_user, field, custom_user_value)
                                            changed_social_fields.append(field)
                                            social_fields_updated = True
                                            logger.info(f"Синхронизировано поле {field} для MiniAppUser (telegram_id={telegram_id}): {custom_user_value}")
                                
                                if social_fields_updated:
                                    mini_app_updated = True
                            
                            if mini_app_updated:
                                # Сохраняем только измененные поля для оптимизации
                                update_fields_list = []
                                if changed_social_fields:
                                    update_fields_list.extend(changed_social_fields)
                                if data.get('first_name') and data.get('first_name') != mini_app_user.first_name:
                                    update_fields_list.append('first_name')
                                if data.get('last_name') and data.get('last_name') != mini_app_user.last_name:
                                    update_fields_list.append('last_name')
                                if photo_url and photo_url != mini_app_user.telegram_photo_url:
                                    update_fields_list.append('telegram_photo_url')
                                
                                if update_fields_list:
                                    mini_app_user.save(update_fields=update_fields_list)
                                else:
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
                    
                    # Синхронизируем поля социальных сетей из SocialAccount в CustomUser
                    TelegramAuthService._sync_social_fields_from_accounts(user)
                    
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
                                changed_social_fields = []  # Инициализируем список измененных полей
                                
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
                                
                                # Синхронизируем поля социальных сетей из CustomUser в MiniAppUser
                                # Это обеспечивает что данные соцсетей подтягиваются везде где используется одна БД
                                if user:
                                    user.refresh_from_db()
                                    social_fields_updated = False
                                    
                                    # Список полей социальных сетей для синхронизации
                                    social_fields = ['telegram', 'github', 'instagram', 'facebook', 'linkedin', 'youtube', 'website']
                                    
                                    for field in social_fields:
                                        custom_user_value = getattr(user, field, None)
                                        mini_app_value = getattr(mini_app_user, field, None)
                                        
                                        # Обновляем только если в CustomUser есть значение и оно отличается
                                        if custom_user_value and custom_user_value.strip():
                                            if not mini_app_value or mini_app_value.strip() != custom_user_value.strip():
                                                setattr(mini_app_user, field, custom_user_value)
                                                changed_social_fields.append(field)
                                                social_fields_updated = True
                                                logger.info(f"Синхронизировано поле {field} для MiniAppUser (telegram_id={telegram_id}): {custom_user_value}")
                                    
                                    if social_fields_updated:
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
                
                # Финальная синхронизация полей социальных сетей перед возвратом
                # Это гарантирует что поля всегда актуальны
                try:
                    user.refresh_from_db()
                    TelegramAuthService._sync_social_fields_from_accounts(user)
                except Exception as sync_error:
                    logger.warning(f"Ошибка при финальной синхронизации полей социальных сетей: {sync_error}")
                
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
    def _sync_social_fields_from_accounts(user: User) -> bool:
        """
        Синхронизирует поля социальных сетей в CustomUser из SocialAccount.
        
        Если у пользователя есть социальные аккаунты, их данные подтягиваются
        в соответствующие поля пользователя (telegram, github, etc).
        
        Args:
            user: Пользователь Django (CustomUser)
            
        Returns:
            bool: True если были внесены изменения, False иначе
        """
        if not user or not hasattr(user, 'social_accounts'):
            return False
        
        updated = False
        
        try:
            # Получаем все активные социальные аккаунты
            social_accounts = user.social_accounts.filter(is_active=True)
            
            for account in social_accounts:
                if account.provider == 'telegram' and account.username:
                    # Для Telegram: username идет в поле telegram
                    telegram_username = account.username.strip()
                    # Убираем @ если есть
                    if telegram_username.startswith('@'):
                        telegram_username = telegram_username[1:]
                    
                    # Всегда обновляем если есть username в SocialAccount
                    # Это обеспечивает синхронизацию данных между SocialAccount и CustomUser
                    current_telegram = user.telegram.strip() if user.telegram else ''
                    if current_telegram != telegram_username:
                        user.telegram = telegram_username
                        updated = True
                        logger.info(f"Синхронизировано поле telegram для пользователя {user.username}: {telegram_username} (было: {current_telegram or 'пусто'})")
                
                elif account.provider == 'github' and account.username:
                    # Для GitHub: всегда используем username для формирования URL
                    # URL GitHub всегда должен быть вида https://github.com/{username}
                    github_username = account.username.strip()
                    
                    # Формируем URL с username (не используем email!)
                    github_url = f"https://github.com/{github_username}"
                    
                    # Всегда обновляем если есть данные в SocialAccount
                    current_github = user.github.strip() if user.github else ''
                    if current_github != github_url:
                        user.github = github_url
                        updated = True
                        logger.info(f"Синхронизировано поле github для пользователя {user.username}: {github_url}")
                
                # Для других провайдеров можно добавить аналогичную логику
                # elif account.provider == 'instagram' and account.username:
                #     ...
            
            if updated:
                user.save(update_fields=['telegram', 'github', 'instagram', 'facebook', 'linkedin', 'youtube'])
                logger.info(f"Поля социальных сетей синхронизированы для пользователя {user.username}")
            
        except Exception as e:
            logger.warning(f"Ошибка при синхронизации полей социальных сетей для пользователя {user.username}: {e}")
        
        return updated
    
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
        
        # Пытаемся найти существующего пользователя по email
        # Ищем среди пользователей, у которых есть SocialAccount с email (например, GitHub)
        # Это помогает связать существующие аккаунты на сайте или через GitHub с Telegram
        # ВАЖНО: Telegram Login Widget не предоставляет email, поэтому мы ищем среди всех пользователей
        # с email, которые еще не связаны с Telegram. Это может быть неидеально, но помогает связать
        # аккаунты для пользователей, которые уже зарегистрированы через GitHub или сайт.
        try:
            # Сначала проверяем email через SocialAccount (например, GitHub аккаунты)
            # Ищем только среди пользователей, у которых еще нет Telegram SocialAccount
            social_accounts_with_email = SocialAccount.objects.filter(
                email__isnull=False,
                provider='github'  # Ограничиваем поиск только GitHub аккаунтами
            ).exclude(email='').select_related('user')
            
            # Получаем список пользователей, у которых уже есть Telegram SocialAccount
            users_with_telegram = set(
                SocialAccount.objects.filter(provider='telegram')
                .values_list('user_id', flat=True)
            )
            
            # Проверяем пользователей с GitHub аккаунтами
            for social_account in social_accounts_with_email:
                existing_user = social_account.user
                
                # Пропускаем, если у пользователя уже есть Telegram SocialAccount
                if existing_user.id in users_with_telegram:
                    continue
                
                # Проверяем, что у пользователя нет telegram_id или он другой
                if not existing_user.telegram_id or str(existing_user.telegram_id) != telegram_id:
                    # Проверяем, что пользователь активен
                    if existing_user.is_active:
                        logger.info(f"Найден пользователь по email через GitHub SocialAccount: {existing_user.username} (id={existing_user.id}), email={social_account.email}")
                        logger.info(f"Сохраняем существующую информацию пользователя: статистика, настройки, логотип")
                        
                        # ВАЖНО: Обновляем только пустые поля или дополняем информацию
                        # НЕ перезаписываем существующие данные (статистика, логотип и т.д.)
                        updated = False
                        
                        # Связываем с telegram_id
                        existing_user.telegram_id = telegram_id
                        if not existing_user.is_telegram_user:
                            existing_user.is_telegram_user = True
                            updated = True
                        
                        # Обновляем имя только если оно пустое
                        if first_name and not existing_user.first_name:
                            existing_user.first_name = first_name
                            updated = True
                        
                        # Обновляем фамилию только если она пустая
                        if last_name and not existing_user.last_name:
                            existing_user.last_name = last_name
                            updated = True
                        
                        # Загружаем аватарку только если её нет
                        if photo_url and not existing_user.avatar:
                            if TelegramAuthService._download_avatar_from_url(photo_url, existing_user):
                                updated = True
                                logger.info(f"Аватарка загружена для существующего пользователя {existing_user.username}")
                        
                        if updated:
                            existing_user.save()
                            logger.info(f"Пользователь {existing_user.username} успешно связан с telegram_id={telegram_id} через email={social_account.email}")
                        
                        return existing_user
        except Exception as email_search_error:
            logger.warning(f"Ошибка при поиске пользователя по email через SocialAccount: {email_search_error}")
        
        # Также проверяем email напрямую в User
        # (для пользователей, зарегистрированных напрямую на сайте)
        try:
            # Получаем список пользователей, у которых уже есть Telegram SocialAccount
            users_with_telegram = set(
                SocialAccount.objects.filter(provider='telegram')
                .values_list('user_id', flat=True)
            )
            
            users_with_email = User.objects.filter(
                email__isnull=False
            ).exclude(email='').exclude(id__in=users_with_telegram)
            
            for existing_user in users_with_email:
                # Проверяем, что у пользователя нет telegram_id или он другой
                if not existing_user.telegram_id or str(existing_user.telegram_id) != telegram_id:
                    # Проверяем, что пользователь активен
                    if existing_user.is_active:
                        logger.info(f"Найден пользователь по email в User: {existing_user.username} (id={existing_user.id}), email={existing_user.email}")
                        logger.info(f"Сохраняем существующую информацию пользователя: статистика, настройки, логотип")
                        
                        # ВАЖНО: Обновляем только пустые поля
                        updated = False
                        
                        # Связываем с telegram_id
                        existing_user.telegram_id = telegram_id
                        if not existing_user.is_telegram_user:
                            existing_user.is_telegram_user = True
                            updated = True
                        
                        # Обновляем имя только если оно пустое
                        if first_name and not existing_user.first_name:
                            existing_user.first_name = first_name
                            updated = True
                        
                        # Обновляем фамилию только если она пустая
                        if last_name and not existing_user.last_name:
                            existing_user.last_name = last_name
                            updated = True
                        
                        # Загружаем аватарку только если её нет
                        if photo_url and not existing_user.avatar:
                            if TelegramAuthService._download_avatar_from_url(photo_url, existing_user):
                                updated = True
                                logger.info(f"Аватарка загружена для существующего пользователя {existing_user.username}")
                        
                        if updated:
                            existing_user.save()
                            logger.info(f"Пользователь {existing_user.username} успешно связан с telegram_id={telegram_id} через email={existing_user.email}")
                        
                        return existing_user
        except Exception as email_user_search_error:
            logger.warning(f"Ошибка при поиске пользователя по email в User: {email_user_search_error}")
        
        # Пытаемся найти существующего пользователя по username из Telegram
        # Это помогает связать существующие аккаунты на сайте с Telegram
        if telegram_username and telegram_username.strip():
            existing_user = User.objects.filter(username__iexact=telegram_username).first()
            if existing_user:
                # Если найден пользователь без telegram_id или с другим telegram_id, связываем его
                if not existing_user.telegram_id or str(existing_user.telegram_id) != telegram_id:
                    logger.info(f"Связывание существующего пользователя {existing_user.username} с telegram_id={telegram_id}")
                    logger.info(f"Сохраняем существующую информацию пользователя: статистика, настройки, логотип")
                    
                    # ВАЖНО: Обновляем только пустые поля
                    updated = False
                    
                    existing_user.telegram_id = telegram_id
                    if not existing_user.is_telegram_user:
                        existing_user.is_telegram_user = True
                        updated = True
                    
                    if first_name and not existing_user.first_name:
                        existing_user.first_name = first_name
                        updated = True
                    if last_name and not existing_user.last_name:
                        existing_user.last_name = last_name
                        updated = True
                    
                    # Загружаем аватарку только если её нет
                    if photo_url and not existing_user.avatar:
                        if TelegramAuthService._download_avatar_from_url(photo_url, existing_user):
                            updated = True
                    
                    if updated:
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


class GitHubAuthService:
    """
    Сервис для авторизации через GitHub.
    
    Обрабатывает OAuth 2.0 авторизацию через GitHub.
    """
    
    GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
    GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
    GITHUB_USER_API_URL = "https://api.github.com/user"
    
    @staticmethod
    def get_github_settings() -> Optional[SocialAuthSettings]:
        """
        Получает настройки GitHub из базы данных или переменных окружения.
        
        Returns:
            SocialAuthSettings: Настройки GitHub или None
        """
        try:
            # Сначала пытаемся получить из базы данных
            settings = SocialAuthSettings.objects.filter(
                provider='github',
                is_enabled=True
            ).first()
            
            if settings:
                return settings
            
            # Если нет в БД, пытаемся получить из переменных окружения
            client_id = os.getenv('SOCIAL_AUTH_GITHUB_KEY') or os.getenv('GITHUB_CLIENT_ID')
            client_secret = os.getenv('SOCIAL_AUTH_GITHUB_SECRET') or os.getenv('GITHUB_CLIENT_SECRET')
            
            if client_id and client_secret:
                # Создаем временный объект настроек
                settings = SocialAuthSettings(
                    provider='github',
                    client_id=client_id,
                    client_secret=client_secret,
                    is_enabled=True
                )
                return settings
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении настроек GitHub: {e}")
            return None
    
    @staticmethod
    def get_auth_url(redirect_uri: str, state: str = None) -> Optional[str]:
        """
        Генерирует URL для авторизации через GitHub.
        
        Args:
            redirect_uri: URI для перенаправления после авторизации
            state: Опциональный параметр состояния для защиты от CSRF
            
        Returns:
            str: URL для авторизации или None
        """
        try:
            settings = GitHubAuthService.get_github_settings()
            if not settings:
                logger.error("Настройки GitHub не найдены")
                return None
            
            params = {
                'client_id': settings.client_id,
                'redirect_uri': redirect_uri,
                'scope': 'user:email',
                'response_type': 'code'
            }
            
            if state:
                params['state'] = state
            
            url = f"{GitHubAuthService.GITHUB_AUTH_URL}?{urllib.parse.urlencode(params)}"
            logger.info(f"🔗 Сгенерирован URL для GitHub авторизации: {url}")
            logger.info(f"🔍 Параметры запроса к GitHub:")
            logger.info(f"  - client_id: {settings.client_id}")
            logger.info(f"  - redirect_uri: {redirect_uri}")
            logger.info(f"  - state: {state}")
            logger.info(f"⚠️ ВАЖНО: redirect_uri должен точно совпадать с настройками в GitHub OAuth App!")
            return url
            
        except Exception as e:
            logger.error(f"Ошибка при генерации URL для GitHub авторизации: {e}")
            return None
    
    @staticmethod
    def exchange_code_for_token(code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """
        Обменивает код авторизации на access token.
        
        Args:
            code: Код авторизации от GitHub
            redirect_uri: URI для перенаправления (должен совпадать с тем, что был при авторизации)
            
        Returns:
            Dict с токеном или None при ошибке
        """
        try:
            settings = GitHubAuthService.get_github_settings()
            if not settings:
                logger.error("Настройки GitHub не найдены для обмена кода на токен")
                return None
            
            response = requests.post(
                GitHubAuthService.GITHUB_TOKEN_URL,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                json={
                    'client_id': settings.client_id,
                    'client_secret': settings.client_secret,
                    'code': code,
                    'redirect_uri': redirect_uri
                },
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Ошибка при обмене кода на токен: {response.status_code}, {response.text}")
                return None
            
            data = response.json()
            
            if 'error' in data:
                logger.error(f"GitHub вернул ошибку: {data.get('error')}, {data.get('error_description')}")
                return None
            
            access_token = data.get('access_token')
            if not access_token:
                logger.error("Access token не получен от GitHub")
                return None
            
            return {
                'access_token': access_token,
                'token_type': data.get('token_type', 'bearer'),
                'scope': data.get('scope', '')
            }
            
        except Exception as e:
            logger.error(f"Ошибка при обмене кода на токен GitHub: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    @staticmethod
    def get_user_info(access_token: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о пользователе из GitHub API.
        
        Args:
            access_token: Access token от GitHub
            
        Returns:
            Dict с информацией о пользователе или None при ошибке
        """
        try:
            # Получаем основную информацию о пользователе
            response = requests.get(
                GitHubAuthService.GITHUB_USER_API_URL,
                headers={
                    'Authorization': f'token {access_token}',
                    'Accept': 'application/json'
                },
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Ошибка при получении информации о пользователе: {response.status_code}, {response.text}")
                return None
            
            user_data = response.json()
            
            # Получаем email пользователя (если не публичный)
            email = user_data.get('email')
            if not email:
                # Пытаемся получить email через отдельный запрос
                try:
                    email_response = requests.get(
                        'https://api.github.com/user/emails',
                        headers={
                            'Authorization': f'token {access_token}',
                            'Accept': 'application/json'
                        },
                        timeout=10
                    )
                    if email_response.status_code == 200:
                        emails = email_response.json()
                        # Берем первый primary email
                        primary_email = next((e['email'] for e in emails if e.get('primary')), None)
                        if primary_email:
                            email = primary_email
                except Exception as e:
                    logger.warning(f"Не удалось получить email пользователя: {e}")
            
            return {
                'id': str(user_data.get('id')),
                'login': user_data.get('login'),  # username
                'name': user_data.get('name', '').split(' ', 1) if user_data.get('name') else ['', ''],
                'email': email,
                'avatar_url': user_data.get('avatar_url'),
                'bio': user_data.get('bio'),
                'location': user_data.get('location'),
                'company': user_data.get('company'),
                'blog': user_data.get('blog'),
                'public_repos': user_data.get('public_repos', 0),
                'followers': user_data.get('followers', 0),
                'following': user_data.get('following', 0)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователе GitHub: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    @staticmethod
    def process_github_auth(code: str, redirect_uri: str, request) -> Optional[Dict[str, Any]]:
        """
        Обрабатывает авторизацию через GitHub.
        
        Args:
            code: Код авторизации от GitHub
            redirect_uri: URI для перенаправления
            request: HTTP запрос
            
        Returns:
            Dict с результатом авторизации или None при ошибке
        """
        try:
            # Обмениваем код на токен
            token_data = GitHubAuthService.exchange_code_for_token(code, redirect_uri)
            if not token_data:
                return {
                    'success': False,
                    'error': 'Не удалось получить токен от GitHub'
                }
            
            access_token = token_data['access_token']
            
            # Получаем информацию о пользователе
            user_info = GitHubAuthService.get_user_info(access_token)
            if not user_info:
                return {
                    'success': False,
                    'error': 'Не удалось получить информацию о пользователе'
                }
            
            github_id = user_info['id']
            github_username = user_info['login']
            
            logger.info(f"Обработка авторизации GitHub для github_id={github_id}, username={github_username}")
            
            with transaction.atomic():
                # ВАЖНО: Сначала проверяем, авторизован ли уже пользователь
                # Если пользователь уже авторизован - связываем GitHub с его текущим аккаунтом
                current_user = None
                if hasattr(request, 'user') and request.user.is_authenticated:
                    current_user = request.user
                    logger.info(f"Пользователь уже авторизован: {current_user.username} (id={current_user.id})")
                
                # Ищем существующий социальный аккаунт GitHub
                social_account = SocialAccount.objects.filter(
                    provider='github',
                    provider_user_id=github_id,
                    is_active=True
                ).first()
                
                if social_account:
                    # Получаем пользователя из social_account
                    user = social_account.user
                    is_new_user = False
                    logger.info(f"Найден существующий социальный аккаунт GitHub для github_id={github_id}, пользователь: {user.username}")
                    
                    # Обновляем данные аккаунта
                    updated = False
                    if github_username and github_username != social_account.username:
                        social_account.username = github_username
                        updated = True
                    if user_info.get('email') and user_info['email'] != social_account.email:
                        social_account.email = user_info['email']
                        updated = True
                    if user_info.get('name') and user_info['name'][0]:
                        first_name = user_info['name'][0]
                        if first_name != social_account.first_name:
                            social_account.first_name = first_name
                            updated = True
                    if user_info.get('name') and len(user_info['name']) > 1 and user_info['name'][1]:
                        last_name = user_info['name'][1]
                        if last_name != social_account.last_name:
                            social_account.last_name = last_name
                            updated = True
                    if user_info.get('avatar_url') and user_info['avatar_url'] != social_account.avatar_url:
                        social_account.avatar_url = user_info['avatar_url']
                        updated = True
                    
                    # Обновляем токен
                    if access_token != social_account.access_token:
                        social_account.access_token = access_token
                        updated = True
                    
                    social_account.update_last_login()
                    if updated:
                        social_account.save()
                    
                    # Обновляем данные пользователя
                    user_updated = False
                    if user_info.get('name') and user_info['name'][0] and user_info['name'][0] != user.first_name:
                        user.first_name = user_info['name'][0]
                        user_updated = True
                    if user_info.get('name') and len(user_info['name']) > 1 and user_info['name'][1] and user_info['name'][1] != user.last_name:
                        user.last_name = user_info['name'][1]
                        user_updated = True
                    
                    # Загружаем аватарку если есть
                    avatar_url = user_info.get('avatar_url')
                    if avatar_url and not user.avatar:
                        if TelegramAuthService._download_avatar_from_url(avatar_url, user):
                            user_updated = True
                    
                    # Синхронизируем поля социальных сетей
                    if TelegramAuthService._sync_social_fields_from_accounts(user):
                        user_updated = True
                    
                    if user_updated:
                        user.save()
                        
                else:
                    # SocialAccount не найден - ищем существующего пользователя или создаем нового
                    user = None
                    
                    # ВАЖНО: Сначала пытаемся найти существующего пользователя по email или username
                    # даже если пользователь не авторизован
                    email = user_info.get('email', '')
                    github_username = user_info.get('login', '')
                    
                    logger.info(f"🔍 Поиск существующего пользователя: email='{email}', github_username='{github_username}'")
                    
                    # ДЛЯ ОТЛАДКИ: Выводим всех пользователей с email для проверки
                    all_users_with_email = User.objects.exclude(email='').exclude(email__isnull=True)[:10]
                    logger.info(f"🔍 Всего пользователей с email в базе (первые 10): {all_users_with_email.count()}")
                    for u in all_users_with_email:
                        logger.info(f"  - id={u.id}, username='{u.username}', email='{u.email}'")
                    
                    # Поиск по email (проверяем, что email не пустой и не None)
                    if email and email.strip():
                        email_normalized = email.strip()
                        logger.info(f"🔍 Ищем пользователя по email: '{email_normalized}'")
                        
                        # Пробуем поиск (case-insensitive, без учета регистра)
                        found_user = User.objects.filter(email__iexact=email_normalized).first()
                        if found_user:
                            user = found_user
                            logger.info(f"✅ Найден существующий пользователь по email: {user.username} (id={user.id}, email={user.email})")
                        else:
                            logger.warning(f"❌ Пользователь по email '{email_normalized}' не найден")
                            # ДЛЯ ОТЛАДКИ: Проверяем, есть ли такой email в базе вообще
                            all_matching = User.objects.filter(email__iexact=email_normalized)
                            logger.info(f"🔍 DEBUG: Количество пользователей с таким email (точное совпадение): {all_matching.count()}")
                            if all_matching.exists():
                                for u in all_matching:
                                    logger.info(f"  DEBUG: Найден пользователь id={u.id}, username={u.username}, email='{u.email}', is_active={u.is_active}")
                    else:
                        logger.warning(f"⚠️ Email не предоставлен GitHub или пустой: email='{email}'")
                    
                    # Если не нашли по email - ищем по username (проверяем, что username не пустой)
                    if not user and github_username and github_username.strip():
                        username_normalized = github_username.strip()
                        logger.info(f"🔍 Ищем пользователя по username: '{username_normalized}'")
                        
                        # Пробуем точный поиск (case-insensitive)
                        found_user = User.objects.filter(username__iexact=username_normalized).first()
                        if found_user:
                            user = found_user
                            logger.info(f"✅ Найден существующий пользователь по username: {user.username} (id={user.id}, email={user.email})")
                        else:
                            logger.warning(f"❌ Пользователь по username '{username_normalized}' не найден")
                            # ДЛЯ ОТЛАДКИ: Проверяем, есть ли такой username в базе вообще
                            all_matching = User.objects.filter(username__iexact=username_normalized)
                            logger.info(f"🔍 DEBUG: Количество пользователей с таким username (точное совпадение): {all_matching.count()}")
                            if all_matching.exists():
                                for u in all_matching:
                                    logger.info(f"  DEBUG: Найден пользователь id={u.id}, username={u.username}, email='{u.email}', is_active={u.is_active}")
                    elif not user and not github_username:
                        logger.warning(f"⚠️ GitHub username не предоставлен (пустой или None)")
                    
                    if not user:
                        logger.info(f"📝 Пользователь не найден по email/username - будет создан новый")
                    
                    # Если пользователь уже авторизован и нашли другого пользователя по email/username
                    if current_user and user and current_user.id != user.id:
                        logger.warning(f"⚠️ Конфликт: пользователь {current_user.username} (id={current_user.id}) авторизован, но найден другой пользователь {user.username} (id={user.id}) по email/username")
                        # Используем авторизованного пользователя
                        user = current_user
                        logger.info(f"Используем авторизованного пользователя: {user.username} (id={user.id})")
                    
                    # Если пользователь уже авторизован и не нашли другого по email/username
                    if current_user and not user:
                        user = current_user
                        logger.info(f"Используем авторизованного пользователя (другого не найдено): {user.username} (id={user.id})")
                    
                    # Если нашли существующего пользователя - обновляем его данные
                    if user:
                        is_new_user = False
                        logger.info(f"Связываем GitHub аккаунт с существующим пользователем: {user.username} (id={user.id})")
                        
                        # ВАЖНО: Сохраняем все существующие данные пользователя
                        # Обновляем только пустые поля или дополнительные данные
                        user_updated = False
                        
                        # Обновляем email только если он пустой
                        if email and not user.email:
                            user.email = email
                            user_updated = True
                        
                        # Обновляем имя только если оно пустое
                        # В user_info['name'] - это список [first_name, last_name]
                        name_parts = user_info.get('name', ['', ''])
                        first_name = name_parts[0] if len(name_parts) > 0 else ''
                        last_name = name_parts[1] if len(name_parts) > 1 else ''
                        
                        if first_name and not user.first_name:
                            user.first_name = first_name
                            user_updated = True
                        
                        if last_name and not user.last_name:
                            user.last_name = last_name
                            user_updated = True
                        
                        # Загружаем аватарку только если её нет
                        avatar_url = user_info.get('avatar_url')
                        if avatar_url and not user.avatar:
                            if TelegramAuthService._download_avatar_from_url(avatar_url, user):
                                user_updated = True
                        
                        # Обновляем GitHub URL в профиле
                        github_url = f"https://github.com/{github_username}"
                        if github_url and not user.github:
                            user.github = github_url
                            user_updated = True
                        
                        if user_updated:
                            user.save()
                            logger.info(f"Обновлены данные пользователя {user.username} при связывании с GitHub")
                    
                    else:
                        # Пользователь не найден - создаем нового через _get_or_create_user
                        logger.info(f"Пользователь не найден, создаем нового для github_id={github_id}, github_username={github_username}")
                        user = GitHubAuthService._get_or_create_user(user_info, current_user)
                        is_new_user = user.created_at > timezone.now() - timezone.timedelta(minutes=5)
                        logger.info(f"Создан/найден пользователь: {user.username} (id={user.id}), is_new_user={is_new_user}")
                    
                    # Создаем или обновляем социальный аккаунт
                    # В user_info['name'] - это список [first_name, last_name]
                    name_parts = user_info.get('name', ['', ''])
                    default_first_name = name_parts[0] if len(name_parts) > 0 and name_parts[0] else ''
                    default_last_name = name_parts[1] if len(name_parts) > 1 and name_parts[1] else ''
                    
                    social_account, created = SocialAccount.objects.get_or_create(
                        user=user,
                        provider='github',
                        provider_user_id=github_id,
                        defaults={
                            'username': github_username,
                            'email': user_info.get('email'),
                            'first_name': default_first_name,
                            'last_name': default_last_name,
                            'avatar_url': user_info.get('avatar_url'),
                            'access_token': access_token
                        }
                    )
                    
                    # Если аккаунт уже существовал, обновляем его данные
                    if not created:
                        updated = False
                        # В user_info['name'] - это список [first_name, last_name]
                        name_parts = user_info.get('name', ['', ''])
                        first_name = name_parts[0] if len(name_parts) > 0 and name_parts[0] else ''
                        last_name = name_parts[1] if len(name_parts) > 1 and name_parts[1] else ''
                        
                        if github_username and github_username != social_account.username:
                            social_account.username = github_username
                            updated = True
                        if user_info.get('email') and user_info['email'] != social_account.email:
                            social_account.email = user_info['email']
                            updated = True
                        if first_name and first_name != social_account.first_name:
                            social_account.first_name = first_name
                            updated = True
                        if last_name and last_name != social_account.last_name:
                            social_account.last_name = last_name
                            updated = True
                        if user_info.get('avatar_url') and user_info['avatar_url'] != social_account.avatar_url:
                            social_account.avatar_url = user_info['avatar_url']
                            updated = True
                        
                        if access_token != social_account.access_token:
                            social_account.access_token = access_token
                            updated = True
                        
                        if updated:
                            social_account.update_last_login()
                            social_account.save()
                    
                    # Синхронизируем поля социальных сетей
                    TelegramAuthService._sync_social_fields_from_accounts(user)
                    
                    # Автоматически связываем с существующими пользователями
                    try:
                        linked_count = social_account.auto_link_existing_users()
                        if linked_count > 0:
                            logger.info(f"Автоматически связано {linked_count} пользователей для github_id={github_id}")
                            user.refresh_from_db()
                            social_account.refresh_from_db()
                            
                    except Exception as e:
                        logger.warning(f"Ошибка при автоматическом связывании для github_id={github_id}: {e}")
                
                # Убеждаемся что пользователь активен
                user.refresh_from_db()
                if not user.is_active:
                    logger.error(f"Пользователь {user.username} не активен после авторизации GitHub!")
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
                
                logger.info(f"Авторизация GitHub успешна: user={user.username}, github_id={github_id}, session_id={session.session_id}")
                
                return {
                    'success': True,
                    'user': user,
                    'social_account': social_account,
                    'is_new_user': is_new_user,
                    'session_id': session.session_id
                }
                
        except Exception as e:
            logger.error(f"Ошибка при обработке авторизации GitHub: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': 'Внутренняя ошибка сервера'
            }
    
    @staticmethod
    def _get_or_create_user(user_info: Dict[str, Any], current_user: User = None) -> User:
        """
        Получает или создает пользователя на основе данных GitHub.
        
        ВАЖНО: При поиске/создании пользователя сохраняет всю существующую информацию
        (статистику, логотип, настройки и т.д.), дополняя только недостающие данные.
        
        Args:
            user_info: Данные о пользователе от GitHub API
            current_user: Опционально - уже авторизованный пользователь для связывания
            
        Returns:
            User: Пользователь Django
        """
        github_id = user_info['id']
        github_username = user_info['login']
        # В user_info['name'] - это список [first_name, last_name]
        name_parts = user_info.get('name', ['', ''])
        first_name = name_parts[0] if len(name_parts) > 0 and name_parts[0] else ''
        last_name = name_parts[1] if len(name_parts) > 1 and name_parts[1] else ''
        email = user_info.get('email', '')
        avatar_url = user_info.get('avatar_url', '')
        
        logger.info(f"Поиск/создание пользователя для github_id={github_id}, github_username={github_username}")
        
        # Если передан текущий пользователь - используем его
        if current_user:
            logger.info(f"Используется текущий авторизованный пользователь: {current_user.username} (id={current_user.id})")
            return current_user
        
        # Сначала пытаемся найти существующего пользователя по email (если есть)
        if email:
            user = User.objects.filter(email=email).first()
            if user:
                logger.info(f"Найден пользователь по email: {user.username} (id={user.id})")
                logger.info(f"Сохраняем существующую информацию пользователя: статистика, настройки, логотип")
                
                # ВАЖНО: Обновляем только пустые поля или дополняем информацию
                # НЕ перезаписываем существующие данные (статистика, логотип и т.д.)
                updated = False
                
                # Обновляем имя только если оно пустое
                if first_name and not user.first_name:
                    user.first_name = first_name
                    updated = True
                
                # Обновляем фамилию только если она пустая
                if last_name and not user.last_name:
                    user.last_name = last_name
                    updated = True
                
                # Загружаем аватарку только если её нет
                if avatar_url and not user.avatar:
                    TelegramAuthService._download_avatar_from_url(avatar_url, user)
                    updated = True
                
                # Обновляем GitHub URL в профиле если его нет
                github_url = f"https://github.com/{github_username}"
                if github_url and not user.github:
                    user.github = github_url
                    updated = True
                
                if updated:
                    user.save()
                    logger.info(f"Обновлены дополнительные данные пользователя {user.username} при связывании с GitHub")
                
                return user
        
        # Пытаемся найти по username
        if github_username:
            user = User.objects.filter(username=github_username).first()
            if user:
                logger.info(f"Найден пользователь по username: {user.username} (id={user.id})")
                logger.info(f"Сохраняем существующую информацию пользователя: статистика, настройки, логотип")
                
                # ВАЖНО: Обновляем только пустые поля
                updated = False
                
                # Обновляем email только если он пустой
                if email and not user.email:
                    user.email = email
                    updated = True
                
                # Обновляем имя только если оно пустое
                if first_name and not user.first_name:
                    user.first_name = first_name
                    updated = True
                
                # Обновляем фамилию только если она пустая
                if last_name and not user.last_name:
                    user.last_name = last_name
                    updated = True
                
                # Загружаем аватарку только если её нет
                if avatar_url and not user.avatar:
                    TelegramAuthService._download_avatar_from_url(avatar_url, user)
                    updated = True
                
                # Обновляем GitHub URL в профиле если его нет
                github_url = f"https://github.com/{github_username}"
                if github_url and not user.github:
                    user.github = github_url
                    updated = True
                
                if updated:
                    user.save()
                    logger.info(f"Обновлены дополнительные данные пользователя {user.username} при связывании с GitHub")
                
                return user
        
        # Если не нашли существующего пользователя, создаем нового
        # Генерируем уникальный username
        base_username = github_username or f"github_{github_id}"
        
        # Проверяем уникальность username
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1
            if counter > 1000:
                username = f"github_user_{github_id}_{int(time.time())}"
                break
        
        logger.info(f"Создание нового пользователя: username={username}, github_id={github_id}, github_username={github_username}")
        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )
        
        # Загружаем аватарку если есть
        if avatar_url:
            TelegramAuthService._download_avatar_from_url(avatar_url, user)
        
        logger.info(f"Пользователь создан: id={user.id}, username={user.username}, github_id={github_id}")
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
    def get_auth_url(provider: str, redirect_uri: str = None, state: str = None) -> Optional[str]:
        """
        Возвращает URL для авторизации через провайдера.
        
        Args:
            provider: Провайдер (telegram, github, etc.)
            redirect_uri: URI для перенаправления после авторизации
            state: Опциональный параметр состояния для защиты от CSRF (для OAuth)
            
        Returns:
            str: URL для авторизации или None
        """
        if provider == 'telegram':
            # Для Telegram используем Login Widget, URL не нужен
            return None
        
        if provider == 'github':
            if not redirect_uri:
                return None
            return GitHubAuthService.get_auth_url(redirect_uri, state)
        
        # Для других провайдеров будет реализовано позже
        return None 