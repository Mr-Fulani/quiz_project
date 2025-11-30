"""
Интеграция с Pinterest API v5.
Документация: https://developers.pinterest.com/docs/api/v5/
"""
import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PinterestAPI:
    """
    Класс для работы с Pinterest API v5.
    Позволяет создавать пины на досках Pinterest.
    """
    
    BASE_URL = "https://api.pinterest.com/v5"
    
    def __init__(self, access_token: str):
        """
        Инициализация API клиента.
        
        Args:
            access_token: OAuth 2.0 access token для Pinterest API
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def create_pin(self, board_id: str, image_url: str, title: str, 
                   description: str, link: str) -> Optional[Dict]:
        """
        Создает пин (публикацию) в Pinterest.
        
        Args:
            board_id: ID доски Pinterest (формат: "user_id/board_name" или числовой ID)
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
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                pin_id = data.get('id')
                logger.info(f"✅ Пин успешно создан: {pin_id}")
                return data
            else:
                error_data = response.json() if response.text else {}
                error_code = error_data.get('code')
                error_message = error_data.get('message', response.text)
                
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
    
    def get_boards(self) -> Optional[Dict]:
        """
        Получает список досок пользователя.
        Полезно для получения board_id.
        
        Returns:
            Dict со списком досок
        """
        url = f"{self.BASE_URL}/boards"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения досок: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка запроса досок: {e}")
            return None

