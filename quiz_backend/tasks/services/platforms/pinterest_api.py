"""
Интеграция с Pinterest API v5.
Документация: https://developers.pinterest.com/docs/api/v5/
"""
import os
import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PinterestAPI:
    """
    Класс для работы с Pinterest API v5.
    Позволяет создавать пины на досках Pinterest.
    
    Для Trial доступа использует Sandbox API (api-sandbox.pinterest.com).
    Для Production доступа использует Production API (api.pinterest.com).
    """
    
    # Определяем базовый URL в зависимости от окружения
    # Для Trial доступа нужно использовать Sandbox API
    _USE_SANDBOX = os.getenv('PINTEREST_USE_SANDBOX', 'true').lower() == 'true'
    
    if _USE_SANDBOX:
        BASE_URL = "https://api-sandbox.pinterest.com/v5"
        logger.info("Используется Pinterest Sandbox API (для Trial доступа)")
    else:
        BASE_URL = "https://api.pinterest.com/v5"
        logger.info("Используется Pinterest Production API")
    
    def __init__(self, access_token: str):
        """
        Инициализация API клиента.
        
        Args:
            access_token: OAuth 2.0 access token для Pinterest API
        """
        # Очищаем токен от пробелов и лишних символов
        self.access_token = access_token.strip()
        
        # Проверяем, что токен не пустой
        if not self.access_token:
            raise ValueError("Access token не может быть пустым")
        
        # Логируем первые и последние символы токена для диагностики (без полного токена)
        token_preview = f"{self.access_token[:10]}...{self.access_token[-10:]}" if len(self.access_token) > 20 else "***"
        logger.info(f"Инициализация Pinterest API с токеном: {token_preview}")
        logger.info(f"Используется API endpoint: {self.BASE_URL}")
        
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def create_pin(self, board_id: str, image_url: str, title: str, 
                   description: str, link: str) -> Optional[Dict]:
        """
        Создает пин (публикацию) в Pinterest.
        
        Args:
            board_id: ID доски Pinterest (только числовой ID, например "1234567890123456789")
            image_url: URL изображения (должен быть публично доступен)
            title: Заголовок пина (до 100 символов)
            description: Описание пина (до 500 символов)
            link: Ссылка на задачу на вашем сайте
            
        Returns:
            Dict с данными созданного пина или None при ошибке
            
        Raises:
            Exception: При ошибке API запроса
        """
        url = f"{self.BASE_URL}/pins"
        
        # Pinterest API v5 требует числовой board_id
        # Если передан строковый формат (например "username/board-name"), 
        # нужно получить числовой ID через get_boards()
        if board_id and not board_id.isdigit():
            logger.warning(f"Board ID в строковом формате '{board_id}'. Пытаемся получить числовой ID...")
            numeric_id = self._get_numeric_board_id(board_id)
            if numeric_id:
                board_id = numeric_id
                logger.info(f"Найден числовой ID доски: {board_id}")
            else:
                raise Exception(
                    f"Не удалось найти числовой ID для доски '{board_id}'. "
                    f"Используйте команду 'python manage.py get_pinterest_boards' для получения правильного ID."
                )
        
        # Обрезаем текст до лимитов Pinterest
        title = title[:100]
        description = description[:500]
        
        payload = {
            "board_id": board_id,
            "title": title,
            "description": description,
            "link": link,
            "media_source": {
                "source_type": "image_url",
                "url": image_url
            }
        }
        
        logger.info(f"Создание пина в Pinterest: board={board_id}, title={title[:30]}...")
        logger.debug(f"URL: {url}, Headers: Authorization=Bearer ***")
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            # Логируем детали ответа для диагностики
            logger.debug(f"Pinterest API response: status={response.status_code}, headers={dict(response.headers)}")
            
            if response.status_code == 201:
                data = response.json()
                pin_id = data.get('id')
                board_id_from_pin = data.get('board_id')
                board_name_from_pin = data.get('board_name')
                
                logger.info(f"✅ Пин успешно создан: {pin_id}")
                
                # Если получили информацию о доске из ответа, сохраняем её
                if board_id_from_pin and board_name_from_pin:
                    logger.debug(f"Получена информация о доске из ответа создания пина: {board_name_from_pin} ({board_id_from_pin})")
                
                return data
            else:
                error_data = response.json() if response.text else {}
                error_code = error_data.get('code')
                error_message = error_data.get('message', response.text)
                
                # Обработка ошибки 401 - неверный или истекший токен
                if response.status_code == 401:
                    # Логируем полный ответ для диагностики
                    logger.error(
                        f"❌ Pinterest API 401: Authentication failed. "
                        f"API Endpoint: {self.BASE_URL} "
                        f"Токен: {self.access_token[:10]}...{self.access_token[-10:] if len(self.access_token) > 20 else ''} "
                        f"Полный ответ API: {response.text[:500]}"
                    )
                    
                    # Проверяем, может быть проблема в формате токена
                    if "invalid" in error_message.lower() or "expired" in error_message.lower():
                        raise Exception(
                            f"Pinterest API error 401: Токен неверный или истек. "
                            f"Получите новый токен через OAuth: /auth/pinterest/authorize/ "
                            f"Убедитесь, что PINTEREST_USE_SANDBOX установлен правильно в .env. "
                            f"Детали: {error_message}"
                        )
                    else:
                        sandbox_note = ""
                        solution = ""
                        if "sandbox" in self.BASE_URL:
                            sandbox_note = " Используется Sandbox API."
                            solution = (
                                "\n\n🔧 РЕШЕНИЕ:\n"
                                "1. Убедитесь, что в .env установлено: PINTEREST_USE_SANDBOX=true\n"
                                "2. Получите НОВЫЙ токен через OAuth: http://localhost:8001/auth/pinterest/authorize/\n"
                                "   (старый токен может быть для Production API)\n"
                                "3. После получения нового токена попробуйте опубликовать снова"
                            )
                        else:
                            solution = (
                                "\n\n🔧 РЕШЕНИЕ:\n"
                                "1. Получите новый токен через OAuth: http://localhost:8001/auth/pinterest/authorize/\n"
                                "2. Убедитесь, что токен имеет права pins:write и boards:write"
                            )
                        
                        raise Exception(
                            f"Pinterest API error 401: Authentication failed.{sandbox_note}\n"
                            f"Возможные причины:\n"
                            f"1) Токен истек\n"
                            f"2) Токен был получен для другого API (Sandbox/Production)\n"
                            f"3) Токен не имеет нужных прав (pins:write, boards:write)\n"
                            f"{solution}\n"
                            f"Детали: {error_message}"
                        )
                
                # Обработка ошибки 403 - Trial доступ требует Sandbox API
                if response.status_code == 403:
                    if "Trial access" in error_message or "Sandbox" in error_message:
                        logger.error(
                            f"❌ Pinterest API 403: Trial доступ требует использования Sandbox API. "
                            f"Установите PINTEREST_USE_SANDBOX=true в .env файле."
                        )
                        raise Exception(
                            f"Pinterest API error 403: Apps with Trial access may not create Pins in production. "
                            f"Используйте Sandbox API. Установите PINTEREST_USE_SANDBOX=true в .env файле. "
                            f"Детали: {error_message}"
                        )
                    else:
                        logger.error(f"❌ Pinterest API 403: {error_message}")
                        raise Exception(f"Pinterest API error 403: {error_message}")
                
                # Специальная обработка для неодобренного приложения
                if error_code == 3 or "consumer type is not supported" in error_message:
                    logger.warning(
                        f"⚠️ Pinterest приложение еще не одобрено для Trial доступа. "
                        f"Статус: 'Доступ к Trial на рассмотрении'. "
                        f"После одобрения можно будет создавать приватные пины. "
                        f"Ошибка: {error_message}"
                    )
                    raise Exception(
                        f"Application not approved yet: {error_message}. "
                        f"Дождитесь одобрения Trial доступа от Pinterest (1-3 дня). "
                        f"После одобрения можно создавать приватные пины."
                    )
                
                error_msg = f"Pinterest API error {response.status_code}: {error_message}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except requests.exceptions.Timeout:
            logger.error("Pinterest API timeout")
            raise Exception("Pinterest API timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"Pinterest API request error: {e}")
            raise Exception(f"Pinterest API request error: {str(e)}")
    
    def get_user_info(self) -> Optional[Dict]:
        """
        Получает информацию о текущем пользователе.
        
        Returns:
            Dict с информацией о пользователе или None при ошибке
        """
        url = f"{self.BASE_URL}/user_account"
        
        try:
            logger.debug(f"Запрос информации о пользователе Pinterest: {url}")
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения информации о пользователе: {response.status_code} - {response.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"Ошибка запроса информации о пользователе: {e}")
            return None
    
    def get_pins(self, page_size: int = 250) -> Optional[Dict]:
        """
        Получает список пинов пользователя для извлечения board_id.
        
        Args:
            page_size: Количество пинов на странице (максимум 250)
        
        Returns:
            Dict со списком пинов в формате {'items': [...], 'bookmark': '...'}
        """
        url = f"{self.BASE_URL}/pins"
        all_items = []
        bookmark = None
        page = 1
        max_pages = 5  # Ограничение для безопасности
        
        while page <= max_pages:
            params = {}
            if bookmark:
                params['bookmark'] = bookmark
            
            try:
                logger.debug(f"Запрос списка пинов Pinterest (страница {page}): {url}")
                response = requests.get(url, headers=self.headers, params=params if params else None, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    all_items.extend(items)
                    
                    logger.info(f"Получено пинов на странице {page}: {len(items)} (всего: {len(all_items)})")
                    
                    bookmark = data.get('bookmark')
                    if not bookmark:
                        break
                    
                    page += 1
                else:
                    logger.error(f"Ошибка получения пинов (страница {page}): {response.status_code} - {response.text[:200]}")
                    if page == 1:
                        return None
                    break
                    
            except Exception as e:
                logger.error(f"Ошибка запроса пинов (страница {page}): {e}", exc_info=True)
                if page == 1:
                    return None
                break
        
        if all_items:
            logger.info(f"✅ Всего получено пинов: {len(all_items)}")
            return {'items': all_items}
        else:
            logger.warning("⚠️ Pinterest API вернул пустой список пинов")
            return {'items': []}
    
    def get_boards(self, page_size: int = 250, get_all: bool = True) -> Optional[Dict]:
        """
        Получает список досок пользователя с поддержкой пагинации.
        Использует простой запрос к /boards как в оригинальной версии.
        
        Args:
            page_size: Количество досок на странице (максимум 250)
            get_all: Если True, получает все доски через пагинацию
        
        Returns:
            Dict со списком досок в формате {'items': [...], 'bookmark': '...'}
            Если get_all=True, возвращает все доски в одном списке items
        """
        url = f"{self.BASE_URL}/boards"
        all_items = []
        bookmark = None
        page = 1
        max_pages = 10  # Ограничение на количество страниц для безопасности
        
        while page <= max_pages:
            # Простой запрос без параметров (как в оригинальной версии)
            # Если нужна пагинация, добавляем bookmark
            params = {}
            if bookmark:
                params['bookmark'] = bookmark
            
            try:
                logger.debug(f"Запрос списка досок Pinterest (страница {page}): {url}")
                response = requests.get(url, headers=self.headers, params=params if params else None, timeout=30)
                
                logger.debug(f"Pinterest API response: status={response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    all_items.extend(items)
                    
                    logger.info(f"Получено досок на странице {page}: {len(items)} (всего: {len(all_items)})")
                    
                    if items:
                        logger.debug(f"Примеры досок на странице {page}: {[board.get('name') for board in items[:3]]}")
                    
                    # Проверяем, есть ли следующая страница
                    bookmark = data.get('bookmark')
                    if not bookmark or not get_all:
                        # Нет следующей страницы или не нужно получать все
                        break
                    
                    page += 1
                else:
                    error_text = response.text[:500] if response.text else "Нет текста ошибки"
                    logger.error(f"Ошибка получения досок (страница {page}): {response.status_code} - {error_text}")
                    if page == 1:
                        return None
                    break
                    
            except Exception as e:
                logger.error(f"Ошибка запроса досок (страница {page}): {e}", exc_info=True)
                if page == 1:
                    return None
                break
        
        if all_items:
            logger.info(f"✅ Всего получено досок: {len(all_items)}")
            return {'items': all_items}
        else:
            logger.warning("⚠️ Pinterest API вернул пустой список досок")
            return {'items': []}
    
    def _get_boards_by_username(self, username: str, page_size: int = 250, get_all: bool = True) -> Optional[Dict]:
        """
        Получает доски через endpoint /users/{username}/boards.
        
        Args:
            username: Username пользователя Pinterest
            page_size: Количество досок на странице
            get_all: Если True, получает все доски через пагинацию
        
        Returns:
            Dict со списком досок
        """
        all_items = []
        bookmark = None
        page = 1
        max_pages = 10
        
        url = f"{self.BASE_URL}/users/{username}/boards"
        
        while page <= max_pages:
            params = {
                'page_size': min(page_size, 250),
                'privacy': 'all'
            }
            
            if bookmark:
                params['bookmark'] = bookmark
            
            try:
                logger.debug(f"Запрос досок через /users/{username}/boards (страница {page}): {url}, params: {params}")
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    all_items.extend(items)
                    
                    logger.info(f"Получено досок через /users/{username}/boards на странице {page}: {len(items)} (всего: {len(all_items)})")
                    
                    if items:
                        logger.debug(f"Примеры досок: {[board.get('name') for board in items[:3]]}")
                    
                    bookmark = data.get('bookmark')
                    if not bookmark or not get_all:
                        break
                    
                    page += 1
                else:
                    error_text = response.text[:500] if response.text else "Нет текста ошибки"
                    logger.error(f"Ошибка получения досок через /users/{username}/boards: {response.status_code} - {error_text}")
                    break
                    
            except Exception as e:
                logger.error(f"Ошибка запроса досок через /users/{username}/boards: {e}", exc_info=True)
                break
        
        if all_items:
            logger.info(f"✅ Всего получено досок через /users/{username}/boards: {len(all_items)}")
            return {'items': all_items}
        else:
            logger.warning(f"⚠️ Не удалось получить доски через /users/{username}/boards")
            return {'items': []}
    
    def _get_numeric_board_id(self, board_slug: str) -> Optional[str]:
        """
        Получает числовой ID доски по строковому формату (username/board-name).
        
        Args:
            board_slug: Строковый формат доски (например "username/board-name")
            
        Returns:
            Числовой ID доски или None, если не найдена
        """
        boards_data = self.get_boards()
        if not boards_data:
            return None
        
        items = boards_data.get('items', [])
        for board in items:
            # Проверяем разные возможные форматы идентификации доски
            board_id = board.get('id')
            board_name = board.get('name', '').lower().replace(' ', '-')
            owner_username = board.get('owner', {}).get('username', '')
            
            # Формируем возможные варианты строкового формата
            if owner_username and board_name:
                possible_slug = f"{owner_username}/{board_name}"
                if possible_slug == board_slug.lower():
                    return str(board_id)
            
            # Также проверяем только по имени доски
            if board_name and board_slug.lower().endswith(f"/{board_name}"):
                return str(board_id)
        
        return None

