"""
Сервис для работы с Django API
"""
import logging
import httpx
import json
from typing import List, Dict, Optional, Any
from core.config import settings

logger = logging.getLogger(__name__)

class DjangoAPIService:
    """Сервис для взаимодействия с Django API"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.timeout = httpx.Timeout(10.0, connect=5.0)
    
    async def _make_request(self, method: str, endpoint: str, headers: dict = None, **kwargs):
        """Базовый метод для выполнения HTTP запросов"""
        url = f'{self.base_url}{endpoint}'
        
        # Добавляем заголовок Host для внутренних запросов между контейнерами
        if headers is None:
            headers = {}
        
        # Если запрос идет к quiz_backend:8000 и X-Forwarded-Host не передан,
        # добавляем правильный Host заголовок для продакшена.
        if 'quiz_backend:8000' in self.base_url and 'X-Forwarded-Host' not in headers:
            headers['Host'] = 'mini.quiz-code.com'
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, headers=headers, **kwargs)
                response.raise_for_status()
                
                # ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ: Показываем, что именно приходит от Django
                response_data = response.json()
                logger.info(f"Ответ от Django API ({url}): {response_data}")
                
                return response_data
            except httpx.RequestError as e:
                logger.error(f"Ошибка запроса к {url}: {e}")
                raise
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Ошибка декодирования JSON ответа от {url}: {e}")
                logger.error(f"Тело ответа: {response.text}")
                raise
    
    async def get_topics(self, search: Optional[str] = None, language: str = 'en', telegram_id: Optional[int] = None, has_tasks: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Получение списка тем с учетом языка, прогресса пользователя и наличия задач"""
        params = {'language': language}
        if search:
            params['search'] = search
        if telegram_id:
            params['telegram_id'] = telegram_id
        if has_tasks is not None:
            params['has_tasks'] = 'true' if has_tasks else 'false'
            
        try:
            data = await self._make_request("GET", "/api/simple/", params=params)
            # Для /api/simple/ возвращается список напрямую, а не объект с results
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Ошибка при получении тем: {e}")
            return []
    
    async def get_subtopics(self, topic_id: int, language: str = 'en', has_tasks: Optional[bool] = None, telegram_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Получение подтем для конкретной темы с учетом языка и наличия задач"""
        params = {'language': language}
        if has_tasks is not None:
            params['has_tasks'] = 'true' if has_tasks else 'false'
        if telegram_id:
            params['telegram_id'] = telegram_id
        try:
            data = await self._make_request("GET", f"/api/{topic_id}/subtopics/", params=params)
            # API возвращает список напрямую, а не объект с results
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Ошибка при получении подтем для темы {topic_id}: {e}")
            return []
    
    async def get_topic_detail(self, topic_id: int, language: str = 'en') -> Optional[Dict[str, Any]]:
        """Получение детальной информации о теме с учетом языка"""
        try:
            data = await self._make_request("GET", f"/api/topics/{topic_id}/", params={'language': language})
            return data
        except Exception as e:
            logger.error(f"Ошибка при получении деталей темы {topic_id}: {e}")
            return None
    
    async def get_subtopic_detail(self, subtopic_id: int, language: str = 'en') -> Optional[Dict[str, Any]]:
        """Получение детальной информации о подтеме с учетом языка"""
        try:
            data = await self._make_request("GET", f"/api/subtopics/{subtopic_id}/", params={'language': language})
            return data
        except Exception as e:
            logger.error(f"Ошибка при получении деталей подтемы {subtopic_id}: {e}")
            return None
    
    async def get_tasks_for_subtopic(self, subtopic_id: int, language: str = 'en', telegram_id: Optional[int] = None, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получение задач для подтемы с учетом языка и уровня сложности"""
        try:
            params = {'language': language}
            if telegram_id:
                params['telegram_id'] = telegram_id
            if level: # Изменено: теперь передаем 'level', даже если он 'all'
                params['level'] = level
            data = await self._make_request("GET", f"/api/subtopics/{subtopic_id}/", params=params)
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Ошибка при получении задач для подтемы {subtopic_id}: {e}")
            return []
    
    def _prepare_user_data_for_post(self, user_data) -> dict:
        # Конвертируем объект WebAppUser в словарь для отправки в Django
        data = {
            'telegram_id': user_data.id,
            'username': user_data.username,
            'first_name': user_data.first_name,
            'last_name': user_data.last_name,
            'language_code': user_data.language_code,
            'photo_url': user_data.photo_url
        }
        logger.info(f"Подготовленные данные для отправки в Django: {data}")
        return data

    async def get_or_create_user_profile(
        self, user_data, host: str = None, scheme: str = None
    ) -> dict:
        # user_data здесь - это объект WebAppUser, а не словарь
        telegram_id = user_data.id
        logger.info(f"Начинаем получение/создание профиля для telegram_id={telegram_id}")

        # Формируем заголовки для корректной генерации URL на бэкенде
        headers = {}
        if host:
            headers['X-Forwarded-Host'] = host
        if scheme:
            headers['X-Forwarded-Proto'] = scheme
            
        try:
            # Сначала пытаемся получить профиль по GET запросу
            profile = await self._make_request(
                'GET',
                f'/api/accounts/miniapp-users/by-telegram/{telegram_id}/',
                headers=headers
            )
            logger.info(f"Найден существующий профиль для telegram_id={telegram_id}")
            return profile
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"Профиль для telegram_id={telegram_id} не найден, создаем новый.")
                try:
                    new_profile = await self._make_request(
                        'POST',
                        f'/api/accounts/miniapp-users/profile/by-telegram/',
                        headers=headers,
                        json=self._prepare_user_data_for_post(user_data)
                    )
                    logger.info(f"Успешно создан новый профиль для telegram_id={telegram_id}")
                    return new_profile
                except Exception as post_e:
                    logger.error(f"Ошибка при создании профиля для telegram_id={telegram_id}: {post_e}")
                    raise
            else:
                logger.error(f"Ошибка при получении профиля: {e}")
                raise
        except Exception as e:
            logger.error(f"Ошибка при получении/создании профиля: {e}")
            raise

    async def get_user_profile(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получение профиля пользователя"""
        try:
            data = await self._make_request("GET", f"/api/accounts/profile/by-telegram/{telegram_id}/")
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Профиль для telegram_id={telegram_id} не найден (404).")
                return None
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении профиля пользователя {telegram_id}: {e}")
            return None
    
    async def update_user_profile(self, telegram_id: int, profile_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Обновление профиля пользователя"""
        try:
            data = await self._make_request("PATCH", f"/api/accounts/profile/by-telegram/{telegram_id}/update/", json=profile_data)
            return data
        except Exception as e:
            logger.error(f"Ошибка при обновлении профиля пользователя {telegram_id}: {e}")
            return None

    async def get_top_users_mini_app(
        self, language: str = 'en', host: str = None, scheme: str = None
    ) -> List[Dict[str, Any]]:
        """
        Получение списка топ-пользователей Mini App из Django API.
        """
        try:
            params = {'language': language}
            headers = {}
            if host:
                headers['X-Forwarded-Host'] = host
            if scheme:
                headers['X-Forwarded-Proto'] = scheme
                
            data = await self._make_request(
                "GET", "/api/accounts/miniapp-users/top/", params=params, headers=headers
            )
            return data  # API MiniAppTopUsersListView возвращает список напрямую
        except Exception as e:
            logger.error(f"Ошибка при получении топ-пользователей Mini App: {e}")
            return []

    async def get_user_statistics(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение статистики пользователя Mini App по telegram_id.
        """
        try:
            params = {'telegram_id': telegram_id}
            data = await self._make_request("GET", "/api/accounts/miniapp-users/statistics/", params=params)
            return data
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователя {telegram_id}: {e}")
            return None

# Создаем единственный экземпляр сервиса
django_api_service = DjangoAPIService(settings.DJANGO_API_BASE_URL) 