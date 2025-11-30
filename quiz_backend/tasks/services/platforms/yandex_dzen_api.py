"""
Интеграция с Яндекс Дзен Platform API.
Документация: https://yandex.ru/dev/zen/doc/
"""
import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class YandexDzenAPI:
    """
    Класс для работы с Яндекс Дзен Platform API.
    Позволяет создавать статьи в канале Яндекс Дзен.
    """
    
    BASE_URL = "https://api.zen.yandex.com/v1"
    
    def __init__(self, access_token: str):
        """
        Инициализация API клиента.
        
        Args:
            access_token: OAuth токен для Яндекс Дзен API
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"OAuth {access_token}",
            "Content-Type": "application/json"
        }
    
    def create_article(self, channel_id: str, title: str, content: str,
                      image_url: str, link: str, publish: bool = True) -> Optional[Dict]:
        """
        Создает статью в Яндекс Дзен.
        
        Args:
            channel_id: ID канала в Яндекс Дзен
            title: Заголовок статьи
            content: Содержание статьи (текст вопроса и объяснение)
            image_url: URL изображения для статьи
            link: Ссылка на задачу на вашем сайте
            publish: Опубликовать сразу (True) или сохранить как черновик (False)
            
        Returns:
            Dict с данными созданной статьи или None при ошибке
            
        Raises:
            Exception: При ошибке API запроса
        """
        url = f"{self.BASE_URL}/channels/{channel_id}/articles"
        
        # Формируем контент статьи в HTML
        html_content = f"""
        <figure>
            <img src="{image_url}" alt="{title}" />
        </figure>
        
        <p>{content}</p>
        
        <p><a href="{link}">Проверьте свои знания и решите эту задачу →</a></p>
        """
        
        payload = {
            "title": title,
            "content": html_content.strip(),
            "status": "published" if publish else "draft"
        }
        
        logger.info(f"Создание статьи в Яндекс Дзен: channel={channel_id}, title={title[:30]}...")
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                article_id = data.get('id')
                logger.info(f"✅ Статья успешно создана: {article_id}")
                return data
            else:
                error_msg = f"Yandex Dzen API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except requests.exceptions.Timeout:
            logger.error("Yandex Dzen API timeout")
            raise Exception("Yandex Dzen API timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"Yandex Dzen API request error: {e}")
            raise Exception(f"Yandex Dzen API request error: {str(e)}")
    
    def get_channels(self) -> Optional[Dict]:
        """
        Получает список каналов пользователя.
        Полезно для получения channel_id.
        
        Returns:
            Dict со списком каналов
        """
        url = f"{self.BASE_URL}/channels"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения каналов: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка запроса каналов: {e}")
            return None

