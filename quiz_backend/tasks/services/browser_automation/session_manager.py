"""
Менеджер сессий браузера для сохранения и переиспользования авторизаций.
"""
import json
import logging
from typing import Optional, Dict, Any, List
from django.utils import timezone
from django.db import connection
from asgiref.sync import sync_to_async
from datetime import timedelta

logger = logging.getLogger(__name__)


class BrowserSessionManager:
    """
    Управляет сессиями браузера для социальных сетей.
    Сохраняет cookies и другие данные сессии для переиспользования.
    """
    
    SESSION_EXPIRY_HOURS = 24 * 7  # 7 дней
    
    @staticmethod
    def save_session(
        credentials_obj,
        cookies: List[Dict[str, Any]],
        browser_type: str = 'playwright',
        additional_data: Dict[str, Any] = None
    ) -> bool:
        """
        Сохраняет сессию браузера в credentials.
        
        Args:
            credentials_obj: Объект SocialMediaCredentials
            cookies: Список cookies для сохранения
            browser_type: Тип браузера ('playwright' или 'selenium')
            additional_data: Дополнительные данные сессии (localStorage и т.д.)
            
        Returns:
            bool: True если сохранение успешно
        """
        try:
            if not credentials_obj.extra_data:
                credentials_obj.extra_data = {}
            
            credentials_obj.extra_data['browser_session'] = {
                'cookies': cookies,
                'browser_type': browser_type,
                'saved_at': timezone.now().isoformat(),
                'additional_data': additional_data or {}
            }
            
            # Обновляем browser_type в основном поле, если оно есть
            if hasattr(credentials_obj, 'browser_type'):
                credentials_obj.browser_type = browser_type
            
            # Сохраняем сессию (обрабатываем async контекст если нужно)
            def _save_sync_internal():
                """Внутренняя функция для синхронного сохранения"""
                from webhooks.models import SocialMediaCredentials
                # Перезагружаем объект из БД в синхронном контексте
                creds = SocialMediaCredentials.objects.get(id=credentials_obj.id)
                if not creds.extra_data:
                    creds.extra_data = {}
                creds.extra_data['browser_session'] = {
                    'cookies': cookies,
                    'browser_type': browser_type,
                    'saved_at': timezone.now().isoformat(),
                    'additional_data': additional_data or {}
                }
                fields_to_update = ['extra_data']
                if hasattr(creds, 'browser_type'):
                    creds.browser_type = browser_type
                    fields_to_update.append('browser_type')
                creds.save(update_fields=fields_to_update)
            
            try:
                # Проверяем, находимся ли мы в async контексте
                import asyncio
                try:
                    asyncio.get_running_loop()
                    # Мы в async контексте - запускаем в отдельном потоке
                    logger.debug("Обнаружен async контекст, сохраняем в отдельном потоке")
                    import concurrent.futures
                    import threading
                    
                    # Используем threading для избежания проблем с async
                    result = [None]
                    exception = [None]
                    
                    def run_in_thread():
                        try:
                            _save_sync_internal()
                            result[0] = True
                        except Exception as e:
                            exception[0] = e
                    
                    thread = threading.Thread(target=run_in_thread)
                    thread.start()
                    thread.join(timeout=10)
                    
                    if exception[0]:
                        raise exception[0]
                    if not result[0]:
                        raise Exception("Сохранение не завершилось")
                        
                except RuntimeError:
                    # Нет запущенного event loop - синхронный контекст
                    _save_sync_internal()
            except Exception as save_error:
                logger.error(f"Ошибка сохранения сессии: {save_error}", exc_info=True)
                raise
            
            logger.info(f"Сессия сохранена для {credentials_obj.platform}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения сессии: {e}", exc_info=True)
            return False
    
    @staticmethod
    def load_session(credentials_obj) -> Optional[Dict[str, Any]]:
        """
        Загружает сохраненную сессию из credentials.
        
        Args:
            credentials_obj: Объект SocialMediaCredentials
            
        Returns:
            Dict с данными сессии или None если сессия не найдена/истекла
        """
        try:
            if not credentials_obj.extra_data:
                return None
            
            session_data = credentials_obj.extra_data.get('browser_session')
            if not session_data:
                return None
            
            # Проверяем срок действия сессии
            saved_at_str = session_data.get('saved_at')
            if saved_at_str:
                try:
                    saved_at = timezone.datetime.fromisoformat(
                        saved_at_str.replace('Z', '+00:00')
                    )
                    if saved_at.tzinfo is None:
                        saved_at = timezone.make_aware(saved_at)
                    
                    expiry_time = saved_at + timedelta(hours=BrowserSessionManager.SESSION_EXPIRY_HOURS)
                    if timezone.now() > expiry_time:
                        logger.warning(f"Сессия для {credentials_obj.platform} истекла")
                        return None
                except (ValueError, TypeError) as e:
                    logger.warning(f"Ошибка парсинга даты сессии: {e}")
            
            logger.info(f"Сессия загружена для {credentials_obj.platform}")
            return session_data
            
        except Exception as e:
            logger.error(f"Ошибка загрузки сессии: {e}", exc_info=True)
            return None
    
    @staticmethod
    def clear_session(credentials_obj) -> bool:
        """
        Очищает сохраненную сессию.
        
        Args:
            credentials_obj: Объект SocialMediaCredentials
            
        Returns:
            bool: True если очистка успешна
        """
        try:
            if credentials_obj.extra_data and 'browser_session' in credentials_obj.extra_data:
                del credentials_obj.extra_data['browser_session']
                # Убеждаемся, что мы в синхронном контексте
                try:
                    connection.close()
                except:
                    pass
                credentials_obj.save(update_fields=['extra_data'])
                logger.info(f"Сессия очищена для {credentials_obj.platform}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка очистки сессии: {e}", exc_info=True)
            return False
    
    @staticmethod
    def is_session_valid(credentials_obj) -> bool:
        """
        Проверяет, валидна ли сохраненная сессия.
        
        Args:
            credentials_obj: Объект SocialMediaCredentials
            
        Returns:
            bool: True если сессия валидна
        """
        session = BrowserSessionManager.load_session(credentials_obj)
        return session is not None


