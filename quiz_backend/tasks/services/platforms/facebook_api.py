"""
Интеграция с Facebook Graph API.
Документация: https://developers.facebook.com/docs/graph-api/
"""
import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FacebookAPI:
    """
    Класс для работы с Facebook Graph API.
    Позволяет создавать посты с фотографиями на Facebook странице.
    """
    
    BASE_URL = "https://graph.facebook.com/v18.0"
    
    def __init__(self, access_token: str, page_id: str):
        """
        Инициализация API клиента.
        
        Args:
            access_token: Page Access Token для Facebook API
            page_id: ID Facebook страницы
        """
        self.access_token = access_token
        self.page_id = page_id
    
    def create_photo_post(self, image_url: str, message: str, link: str) -> Optional[Dict]:
        """
        Создает пост с фото на Facebook странице.
        
        Args:
            image_url: URL изображения (должен быть публично доступен)
            message: Текст поста (описание задачи)
            link: Ссылка на задачу на вашем сайте
            
        Returns:
            Dict с данными созданного поста или None при ошибке
            
        Raises:
            Exception: При ошибке API запроса
        """
        url = f"{self.BASE_URL}/{self.page_id}/photos"
        
        params = {
            "url": image_url,
            "caption": message,
            "link": link,
            "access_token": self.access_token
        }
        
        logger.info(f"Создание фото-поста в Facebook: page={self.page_id}")
        
        try:
            response = requests.post(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                post_id = data.get('id')
                post_url = f"https://www.facebook.com/{post_id}"
                logger.info(f"✅ Пост успешно создан: {post_id}")
                
                # Добавляем URL поста в ответ
                data['post_url'] = post_url
                return data
            else:
                error_msg = f"Facebook API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except requests.exceptions.Timeout:
            logger.error("Facebook API timeout")
            raise Exception("Facebook API timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"Facebook API request error: {e}")
            raise Exception(f"Facebook API request error: {str(e)}")
    
    def create_feed_post(self, message: str, link: str) -> Optional[Dict]:
        """
        Создает текстовый пост со ссылкой на Facebook странице.
        
        Args:
            message: Текст поста
            link: Ссылка на задачу
            
        Returns:
            Dict с данными созданного поста
        """
        url = f"{self.BASE_URL}/{self.page_id}/feed"
        
        params = {
            "message": message,
            "link": link,
            "access_token": self.access_token
        }
        
        logger.info(f"Создание текстового поста в Facebook: page={self.page_id}")
        
        try:
            response = requests.post(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                post_id = data.get('id')
                logger.info(f"✅ Текстовый пост успешно создан: {post_id}")
                return data
            else:
                error_msg = f"Facebook API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"Facebook API error: {e}")
            raise Exception(str(e))
    
    def get_page_info(self) -> Optional[Dict]:
        """
        Получает информацию о странице.
        Полезно для проверки прав доступа.
        
        Returns:
            Dict с информацией о странице
        """
        url = f"{self.BASE_URL}/{self.page_id}"
        
        params = {
            "fields": "id,name,access_token",
            "access_token": self.access_token
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения информации о странице: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка запроса информации о странице: {e}")
            return None

