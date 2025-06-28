import json
import logging
import httpx
import os
import urllib.parse
import re

from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from telegram_webapp_auth.auth import TelegramAuthenticator
from telegram_webapp_auth.errors import InvalidInitDataError, ExpiredInitDataError

from core.config import settings
from services.django_api import DjangoAPIService
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
    try:
        data = await request.json()
        init_data_str = data.get('initData')
        if not init_data_str:
            raise HTTPException(status_code=400, detail="initData is missing")
        if not settings.TELEGRAM_BOT_TOKEN:
             raise HTTPException(status_code=500, detail="Bot token is not configured on the server.")

        try:
            secret_key = generate_secret_key(settings.TELEGRAM_BOT_TOKEN)
            authenticator = TelegramAuthenticator(secret_key)
            
            init_data = authenticator.validate(init_data_str)
            
            if not init_data.user or not init_data.user.id:
                raise ValueError("User ID not found in parsed data")
            
            telegram_id = init_data.user.id

        except (InvalidInitDataError, ExpiredInitDataError) as e:
            raise HTTPException(status_code=401, detail=f"Invalid initData: {e}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Could not extract user ID from initData")

        logger.info(f"Successfully validated initData. Extracted telegram_id: {telegram_id}")

        profile_response = await get_profile_by_telegram_id(telegram_id)
        
        if isinstance(profile_response, JSONResponse):
             profile_data = json.loads(profile_response.body.decode('utf-8'))
             return JSONResponse(content=profile_data, status_code=200)
        else:
            return profile_response

    except Exception as e:
        logger.error(f"Error in verify_init_data: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")


@router.get("/profile/by-telegram/{telegram_id}/")
async def get_profile_by_telegram_id(telegram_id: int):
    """
    Проксирует запрос к Django API для получения профиля по telegram_id.
    """
    logger.info(f"Fetching profile from Django for telegram_id: {telegram_id}")
    django_url = f"{settings.DJANGO_API_BASE_URL}/api/accounts/profile/by-telegram/{telegram_id}/"
    headers = {'Authorization': f'Token {settings.DJANGO_API_TOKEN}'}

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
    headers = {'Authorization': f'Token {settings.DJANGO_API_TOKEN}'}
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

# Другие API-эндпоинты (test-api, button-click, profile/stats, и т.д.)
# можно добавить сюда по аналогии. 

async def get_user_profile(request_data: UserProfileRequest, django_api: DjangoAPIService = Depends()):
    try:
        logger.info(f"Получен запрос профиля. InitData длина: {len(request_data.initData)}")
        logger.info(f"InitData начало: {request_data.initData[:100]}...")
        
        # Временно отключаем валидацию для отладки
        # TODO: Включить валидацию после отладки
        try:
            user_data = authenticator.validate(request_data.initData)
            telegram_id = user_data.user.id if hasattr(user_data, 'user') else user_data['id']
            logger.info(f"Валидация прошла успешно. Telegram ID: {telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка валидации: {e}")
            # Извлекаем telegram_id из URL-декодированных данных
            try:
                # Ищем telegram_id в строке напрямую с помощью регулярного выражения
                # Формат: user=%7B%22id%22%3A7662576714%2C%22first_name%22...
                id_match = re.search(r'%22id%22%3A(\d+)', request_data.initData)
                if id_match:
                    telegram_id = int(id_match.group(1))
                    logger.info(f"Извлечен реальный telegram_id из данных: {telegram_id}")
                else:
                    # Попробуем альтернативный способ
                    decoded_data = urllib.parse.unquote(request_data.initData)
                    id_match2 = re.search(r'"id":(\d+)', decoded_data)
                    if id_match2:
                        telegram_id = int(id_match2.group(1))
                        logger.info(f"Извлечен telegram_id альтернативным способом: {telegram_id}")
                    else:
                        telegram_id = 123456789
                        logger.info(f"Не удалось извлечь ID, используем тестовый: {telegram_id}")
            except Exception as parse_error:
                logger.error(f"Ошибка парсинга initData: {parse_error}")
                telegram_id = 123456789
                logger.info(f"Используем тестовый telegram_id: {telegram_id}")

        # 3. Запрос полного профиля пользователя у Django бэкенда
        profile_data = await django_api.get_user_profile(telegram_id)
        logger.info(f"Получен профиль от Django: {profile_data is not None}")
        
        # 4. Возвращаем данные профиля
        return profile_data or {
            "telegram_id": telegram_id,
            "first_name": "Test User",
            "last_name": "",
            "username": None,
            "avatar": None,
            "points": 0,
            "rating": 0,
            "quizzes_completed": 0,
            "success_rate": 0.0,
            "progress": [],
            "status": "test_user"
        }

    except ValidationError as e:
        logger.error(f"Ошибка валидации InitData: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid InitData: {e}")
    except Exception as e:
        logger.exception("Внутренняя ошибка при получении профиля")
        raise HTTPException(status_code=500, detail="Internal server error")

# Регистрация эндпоинта в роутере
router.add_api_route("/profile", get_user_profile, methods=["POST"]) 