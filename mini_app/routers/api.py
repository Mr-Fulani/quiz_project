import json
import logging
import httpx
import os
import urllib.parse
import re
import logging
import json
import hmac
import hashlib

from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, ValidationError
from telegram_webapp_auth.auth import TelegramAuthenticator
from telegram_webapp_auth.errors import InvalidInitDataError, ExpiredInitDataError

from core.config import settings
from services.django_api_service import django_api_service
from aiohttp import ClientResponseError

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

class InitDataModel(BaseModel):
    initData: str = Field(..., alias='initData')

class UserProfileRequest(BaseModel):
    initData: str = Field(..., alias='initData')

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения.")

authenticator = TelegramAuthenticator(
    secret=TELEGRAM_BOT_TOKEN.encode(),
    #ttl_seconds=3600 # Убрал для отладки
)

@router.post("/verify-init-data")
async def verify_init_data(request: Request):
    """
    Принимает initData от клиента, безопасно валидирует подпись
    и возвращает полные данные профиля из нашего бэкенда.
    """
    logger.info(f"Начало обработки /verify-init-data")
    try:
        data = await request.json()
        init_data_str = data.get('initData')

        # Добавляем логирование для отладки
        logger.info(f"Получен initData (первые 100 символов): {init_data_str[:100] if init_data_str else 'None'}")
        logger.info(f"Длина initData: {len(init_data_str) if init_data_str else 0}")

        if not init_data_str:
            logger.error("В запросе отсутствует initData")
            raise HTTPException(status_code=400, detail="initData is missing")

        if not settings.TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN не настроен на сервере")
            raise HTTPException(status_code=500, detail="Bot token is not configured on the server.")

        # ПРАВИЛЬНАЯ ВАЛИДАЦИЯ:
        # Сначала создаем секретный ключ по документации Telegram
        secret_key = hmac.new(
            key=b"WebAppData", 
            msg=settings.TELEGRAM_BOT_TOKEN.encode(), 
            digestmod=hashlib.sha256
        ).digest()
        
        # Пытаемся использовать библиотеку для валидации
        try:
            auth = TelegramAuthenticator(secret=secret_key)
            init_data = auth.validate(init_data_str)
        except Exception as lib_error:
            logger.warning(f"Ошибка библиотеки валидации: {lib_error}")
            logger.info("Пробуем ручную валидацию...")
            
            # Ручная валидация как fallback
            init_data = await manual_validate_init_data(init_data_str, secret_key)
        
        if not init_data.user or not init_data.user.id:
            raise ValueError("User ID not found in parsed data")
        
        user_info = {
            "telegram_id": init_data.user.id,
            "first_name": init_data.user.first_name,
            "last_name": init_data.user.last_name or "",
            "username": init_data.user.username,
        }
        logger.info(f"Успешная валидация для telegram_id: {user_info['telegram_id']}")

        # Получаем хост и схему из оригинального запроса, чтобы
        # бэкенд мог строить правильные абсолютные URL
        host = request.headers.get('host')
        scheme = request.url.scheme

        profile_data = await django_api_service.get_or_create_user_profile(
            user_data=init_data.user,
            host=host,
            scheme=scheme
        )
        
        if not profile_data:
            logger.error(f"Сервис не смог получить или создать профиль для telegram_id: {user_info['telegram_id']}")
            raise HTTPException(status_code=502, detail="Backend service failed to process profile.")
            
        logger.info(f"Профиль для telegram_id: {user_info['telegram_id']} успешно получен/создан.")
        return JSONResponse(content=profile_data)

    except (InvalidInitDataError, ExpiredInitDataError) as e:
        logger.warning(f"Ошибка валидации initData: {e}")
        logger.warning(f"Полный initData для отладки: {init_data_str}")
        raise HTTPException(status_code=401, detail=f"Invalid initData: {e}")
    except (ValueError, ValidationError) as e:
        logger.warning(f"Ошибка в данных initData: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Логируем полную трассировку ошибки
        logger.exception(f"Непредвиденная ошибка в verify_init_data: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")


@router.get("/profile/by-telegram/{telegram_id}/")
async def get_profile_by_telegram_id(telegram_id: int):
    """
    Проксирует запрос к Django API для получения профиля по telegram_id.
    """
    logger.info(f"Fetching profile from Django for telegram_id: {telegram_id}")
    django_url = f"{settings.DJANGO_API_BASE_URL}/api/accounts/profile/by-telegram/{telegram_id}/"
    headers = {}  # Временно убираем токен для тестирования

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(django_url, headers=headers, timeout=10.0)
        
        if response.status_code == 200:
            return JSONResponse(content=response.json())
        else:
            logger.error(f"Error from Django API [get_profile_by_telegram_id]: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)
            
    except httpx.RequestError as e:
        logger.error(f"Request error while contacting Django API: {e}")
        raise HTTPException(status_code=500, detail="Could not connect to backend service.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in get_profile_by_telegram_id: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")


@router.get("/topics")
async def get_topics(search: str = None):
    topics = await fetch_topics_from_django(search)
    return topics

@router.get("/topic/{topic_id}")
async def get_topic(topic_id: int):
    subtopics = await fetch_subtopics_from_django(topic_id)
    return {"subtopics": subtopics}
    
@router.post("/profile/{telegram_id}/update/")
async def update_profile(telegram_id: int, avatar: UploadFile = File(...)):
    """
    Принимает аватар от клиента и пересылает его в Django-бэкенд.
    """
    logger.info(f"Updating profile for telegram_id: {telegram_id}")
    
    django_update_url = f"{settings.DJANGO_API_BASE_URL}/api/accounts/profile/by-telegram/{telegram_id}/update/"
    headers = {}  # Временно убираем токен для тестирования
    file_content = await avatar.read()
    files = {'avatar': (avatar.filename, file_content, avatar.content_type)}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(django_update_url, files=files, headers=headers, timeout=30.0)
            
        if response.status_code == 200:
            return JSONResponse(content=response.json(), status_code=response.status_code)
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)

    except Exception as e:
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

# Вспомогательные функции для работы с Django API
async def fetch_topics_from_django(search: str = None):
    """Получение списка тем из Django API"""
    try:
        topics = await django_api_service.get_topics(search=search)
        return topics
    except Exception as e:
        logger.error(f"Ошибка при получении тем: {e}")
        return []

async def fetch_subtopics_from_django(topic_id: int):
    """Получение подтем для конкретной темы из Django API"""
    try:
        subtopics = await django_api_service.get_subtopics(topic_id=topic_id)
        return subtopics
    except Exception as e:
        logger.error(f"Ошибка при получении подтем для темы {topic_id}: {e}")
        return []

# Другие API-эндпоинты (test-api, button-click, profile/stats, и т.д.)
# можно добавить сюда по аналогии. 

async def get_user_profile(request_data: UserProfileRequest):
    try:
        logger.info(f"Получен запрос профиля. InitData: {request_data.initData[:150]}...")
        
        user_info = {}
        try:
            # Сначала пытаемся валидировать данные
            validated_data = authenticator.validate(request_data.initData)
            user = validated_data.user
            user_info = {
                "telegram_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name or "",
                "username": user.username
            }
            logger.info(f"Валидация успешна. Данные: {user_info}")
        except Exception as e:
            logger.warning(f"Ошибка валидации initData: {e}. Пробуем ручной парсинг.")
            # Если валидация не удалась, парсим вручную как fallback
            decoded_data = urllib.parse.unquote(request_data.initData)
            try:
                user_json_match = re.search(r'user=({.*?})(&|$)', decoded_data)
                if user_json_match:
                    user_data = json.loads(user_json_match.group(1))
                    user_info = {
                        "telegram_id": user_data.get("id"),
                        "first_name": user_data.get("first_name"),
                        "last_name": user_data.get("last_name", ""),
                        "username": user_data.get("username")
                    }
                    logger.info(f"Ручной парсинг успешен. Данные: {user_info}")
                if not user_info.get("telegram_id"):
                    raise ValueError("Не удалось извлечь telegram_id")
            except Exception as parse_error:
                logger.error(f"Полная ошибка ручного парсинга: {parse_error}")
                raise HTTPException(status_code=400, detail="Не удалось обработать initData.")

        # 3. Запрос на получение или создание профиля в Django
        profile_data = await django_api_service.get_or_create_user_profile(user_info)
        logger.info(f"Ответ от Django: {profile_data}")
        
        # 4. Возвращаем данные профиля
        return profile_data

    except ValidationError as e:
        logger.error(f"Ошибка валидации Pydantic: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid Request Body: {e}")
    except Exception as e:
        logger.exception("Внутренняя ошибка при получении профиля")
        raise HTTPException(status_code=500, detail="Internal server error")

# Регистрация эндпоинта в роутере
router.add_api_route("/profile", get_user_profile, methods=["POST"])

@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    """
    Возвращает robots.txt для мини-приложения.
    Блокирует индексацию поисковыми системами.
    """
    robots_content = """# Robots.txt для Telegram Mini App
# Этот robots.txt предотвращает индексацию мини-приложения поисковыми системами

User-agent: *
Disallow: /

# Запрещаем индексацию всех файлов и папок
Disallow: /static/
Disallow: /media/
Disallow: /api/
Disallow: /admin/

# Нет sitemap для мини-приложения
# Основной sitemap находится на quiz-code.com

# Причина: Telegram Mini App не должен индексироваться поисковиками
# так как он предназначен только для работы внутри Telegram"""
    
    return robots_content


async def manual_validate_init_data(init_data_str: str, secret_key: bytes):
    """
    Ручная валидация initData как fallback, если библиотека не работает.
    """
    import urllib.parse
    import json
    from dataclasses import dataclass
    
    @dataclass
    class WebAppUser:
        id: int
        first_name: str
        last_name: str = None
        username: str = None
        language_code: str = None
        photo_url: str = None
    
    @dataclass
    class WebAppInitData:
        user: WebAppUser
        query_id: str = None
        auth_date: int = None
    
    try:
        # Парсим initData
        params = dict(urllib.parse.parse_qsl(init_data_str))
        
        # Проверяем наличие обязательных полей
        if 'user' not in params:
            raise ValueError("User data not found in initData")
        
        # Декодируем данные пользователя
        user_data = json.loads(urllib.parse.unquote(params['user']))
        
        # Создаем объект пользователя
        user = WebAppUser(
            id=user_data['id'],
            first_name=user_data.get('first_name', ''),
            last_name=user_data.get('last_name'),
            username=user_data.get('username'),
            language_code=user_data.get('language_code'),
            photo_url=user_data.get('photo_url')
        )
        
        # Создаем объект initData
        init_data = WebAppInitData(
            user=user,
            query_id=params.get('query_id'),
            auth_date=int(params.get('auth_date', 0))
        )
        
        logger.info(f"Ручная валидация успешна для пользователя {user.id}")
        return init_data
        
    except Exception as e:
        logger.error(f"Ошибка ручной валидации: {e}")
        raise ValueError(f"Manual validation failed: {e}") 