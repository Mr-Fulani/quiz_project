"""
Сервис для работы с Django API
"""
import logging
import httpx
from typing import List, Dict, Optional, Any
from core.config import settings

logger = logging.getLogger(__name__)

class DjangoAPIService:
    """Сервис для взаимодействия с Django API"""
    
    def __init__(self):
        self.base_url = settings.DJANGO_API_BASE_URL
        self.timeout = 30.0
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Базовый метод для выполнения HTTP запросов"""
        url = f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                logger.error(f"Ошибка запроса к {url}: {e}")
                raise
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP ошибка {e.response.status_code} для {url}: {e.response.text}")
                raise
    
    async def get_topics(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получение списка тем"""
        params = {}
        if search:
            params['search'] = search
            
        try:
            data = await self._make_request("GET", "/api/simple/", params=params)
            # Для /api/simple/ возвращается список напрямую, а не объект с results
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Ошибка при получении тем: {e}")
            return []
    
    async def get_subtopics(self, topic_id: int) -> List[Dict[str, Any]]:
        """Получение подтем для конкретной темы"""
        try:
            data = await self._make_request("GET", f"/topics/{topic_id}/subtopics/")
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Ошибка при получении подтем для темы {topic_id}: {e}")
            return []
    
    async def get_user_profile(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получение профиля пользователя"""
        try:
            data = await self._make_request("GET", f"/users/{telegram_id}/")
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении профиля пользователя {telegram_id}: {e}")
            return None
    
    async def update_user_profile(self, telegram_id: int, profile_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Обновление профиля пользователя"""
        try:
            data = await self._make_request("PATCH", f"/users/{telegram_id}/", json=profile_data)
            return data
        except Exception as e:
            logger.error(f"Ошибка при обновлении профиля пользователя {telegram_id}: {e}")
            return None

# Создаем единственный экземпляр сервиса
django_api_service = DjangoAPIService() 