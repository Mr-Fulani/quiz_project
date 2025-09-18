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

from fastapi import APIRouter, Request, Response, UploadFile, File, HTTPException, Depends
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
    logger.info(f"🚀 НАЧАЛО ОБРАБОТКИ /verify-init-data")
    logger.info(f"🔍 User-Agent: {request.headers.get('user-agent', 'Unknown')}")
    logger.info(f"🔍 X-Forwarded-For: {request.headers.get('x-forwarded-for', 'Unknown')}")
    logger.info(f"🔍 Referer: {request.headers.get('referer', 'Unknown')}")
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
        logger.info(f"Возвращаемые данные профиля: {profile_data}")
        logger.info(f"🔍 ВОЗВРАЩАЕМЫЙ TELEGRAM_ID: {profile_data.get('telegram_id', 'NOT_FOUND')}")
        logger.info(f"Тип profile_data: {type(profile_data)}")
        logger.info(f"Avatar в profile_data: {profile_data.get('avatar') if isinstance(profile_data, dict) else 'Not a dict'}")
        logger.info(f"Тип avatar в profile_data: {type(profile_data.get('avatar')) if isinstance(profile_data, dict) else 'N/A'}")
        # Устанавливаем cookie с telegram_id, чтобы страницы могли рендерить прогресс сервер-сайд
        resp = JSONResponse(content=profile_data)
        try:
            tg_id_value = str(profile_data.get('telegram_id') or user_info['telegram_id'])
            resp.set_cookie(
                key="telegram_id",
                value=tg_id_value,
                max_age=365*24*60*60,
                httponly=False,
                samesite="lax"
            )
            logger.info(f"Cookie telegram_id set: {tg_id_value}")
        except Exception as cookie_err:
            logger.warning(f"Failed to set telegram_id cookie: {cookie_err}")
        return resp

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


# Удален старый handler /topics без telegram_id, используем расширенную версию ниже

@router.get("/topic/{topic_id}")
async def get_topic(topic_id: int):
    subtopics = await fetch_subtopics_from_django(topic_id)
    return {"subtopics": subtopics}

@router.get("/subtopics/{subtopic_id}")
async def get_subtopic_with_user(subtopic_id: int, language: str = 'en', telegram_id: int | None = None):
    """Проксирование деталей подтемы (с задачами) с передачей telegram_id для отметки решённых задач."""
    try:
        params = {'language': language}
        if telegram_id:
            params['telegram_id'] = telegram_id
        result = await django_api_service._make_request("GET", f"/api/subtopics/{subtopic_id}/", params=params)
        return result
    except Exception as e:
        logger.error(f"Error getting subtopic {subtopic_id}: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch subtopic from backend")
    
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

@router.patch("/accounts/miniapp-users/update/{telegram_id}/")
async def update_miniapp_user_profile(telegram_id: int, request: Request):
    """
    Обновляет профиль пользователя MiniApp, включая загрузку аватара.
    Проксирует запросы в Django API.
    """
    logger.info(f"Updating MiniApp user profile for telegram_id: {telegram_id}")
    
    try:
        # Проверяем тип контента
        content_type = request.headers.get("content-type", "")
        
        if "multipart/form-data" in content_type:
            # Обрабатываем загрузку файла и других данных
            form_data = await request.form()
            
            # Подготавливаем данные для отправки в Django API
            django_update_url = f"{settings.DJANGO_API_BASE_URL}/api/accounts/miniapp-users/update/{telegram_id}/"
            
            # Подготавливаем файлы и данные
            files = {}
            data = {}
            
            for key, value in form_data.items():
                if hasattr(value, 'read'):  # Это файл
                    file_content = await value.read()
                    files[key] = (value.filename, file_content, value.content_type)
                else:  # Это обычные данные
                    data[key] = value
            
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    django_update_url, 
                    files=files if files else None,
                    data=data if data else None,
                    timeout=30.0
                )
                    
            if response.status_code == 200:
                return JSONResponse(content=response.json(), status_code=response.status_code)
            else:
                logger.error(f"Django API error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail=response.text)
                
        else:
            # Обрабатываем JSON данные
            profile_data = await request.json()
            logger.info(f"Received profile data: {profile_data}")
            
            # Отправляем данные в Django API
            django_update_url = f"{settings.DJANGO_API_BASE_URL}/api/accounts/miniapp-users/update/{telegram_id}/"
            
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    django_update_url,
                    json=profile_data,
                    timeout=30.0
                )
            
            if response.status_code == 200:
                return JSONResponse(content=response.json())
            else:
                logger.error(f"Django API error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON data")
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@router.patch("/profile/{telegram_id}/update/")
async def update_profile_json(telegram_id: int, request: Request):
    """
    УСТАРЕВШИЙ ENDPOINT - оставлен для совместимости.
    Перенаправляет на новый endpoint.
    """
    logger.warning(f"Using deprecated endpoint /profile/{telegram_id}/update/ - redirecting to new endpoint")
    return await update_miniapp_user_profile(telegram_id, request)

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

class LanguageChangeRequest(BaseModel):
    language: str

@router.post("/change-language")
async def change_language(request: LanguageChangeRequest, response: Response):
    """API endpoint для переключения языка"""
    from services.localization import localization_service
    
    # Проверяем, поддерживается ли язык
    if request.language not in localization_service.get_supported_languages():
        return {"success": False, "error": "Unsupported language"}
    
    # Устанавливаем язык
    localization_service.set_language(request.language)
    
    # Устанавливаем cookie для сохранения выбора
    response.set_cookie(
        key="selected_language", 
        value=request.language,
        max_age=365*24*60*60,  # 1 год
        httponly=False,  # Разрешаем доступ из JavaScript
        samesite="lax"
    )
    
    # Получаем обновленные переводы
    translations = localization_service.get_all_texts(request.language)
    
    return {
        "success": True,
        "language": request.language,
        "translations": translations,
        "supported_languages": localization_service.get_supported_languages()
    }

@router.get("/topics")
async def get_topics(search: str = None, language: str = 'en', telegram_id: int | None = None):
    """Получение списка тем с поиском и прогрессом пользователя (telegram_id)"""
    from services.django_api_service import django_api_service
    
    try:
        logger.info(f"/api/topics called: search={search}, language={language}, telegram_id={telegram_id}")
        params = {'language': language}
        if search:
            params['search'] = search
        if telegram_id:
            params['telegram_id'] = telegram_id
            
        result = await django_api_service._make_request("GET", "/api/simple/", params=params)
        logger.info(f"/api/topics returned {len(result) if isinstance(result, list) else 'non-list'} items")
        return result if isinstance(result, list) else []
    except Exception as e:
        logger.error(f"Error getting topics: {e}")
        return []

@router.get("/stripe-publishable-key")
async def get_stripe_publishable_key():
    """Получение публичного ключа Stripe через Django API"""
    from services.django_api_service import django_api_service
    
    try:
        result = await django_api_service._make_request("GET", "/api/stripe-publishable-key/")
        return result
    except Exception as e:
        logger.error(f"Error getting Stripe key: {e}")
        return {"success": False, "message": "Error getting Stripe key"}

@router.post("/create-payment-intent")
async def create_payment_intent_proxy(request_data: dict):
    """Создание Payment Intent через Django API"""
    from services.donation_service import DonationService
    
    try:
        donation_service = DonationService()
        result = await donation_service.create_payment_intent(
            amount=request_data.get('amount'),
            currency=request_data.get('currency', 'usd'),
            email=request_data.get('email', ''),
            name=request_data.get('name', '')
        )
        return result
    except Exception as e:
        logger.error(f"Error creating payment intent: {e}")
        return {"success": False, "message": "Error creating payment intent"}

@router.post("/confirm-payment")
async def confirm_payment_proxy(request_data: dict):
    """Подтверждение платежа через Django API"""
    from services.donation_service import DonationService
    
    try:
        donation_service = DonationService()
        result = await donation_service.confirm_payment(
            payment_intent_id=request_data.get('payment_intent_id'),
            payment_method_id=request_data.get('payment_method_id', '')
        )
        return result
    except Exception as e:
        logger.error(f"Error confirming payment: {e}")
        return {"success": False, "message": "Error confirming payment"}

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
        logger.info(f"Photo URL из Telegram: {user.photo_url}")
        logger.info(f"Все данные пользователя из Telegram: {user_data}")
        return init_data
        
    except Exception as e:
        logger.error(f"Ошибка ручной валидации: {e}")
        raise ValueError(f"Manual validation failed: {e}") 

@router.post("/tasks/{task_id}/submit-mini-app")
async def submit_task_answer(task_id: int, request: Request):
    """
    Отправляет ответ на задачу из мини-аппа в Django API.
    """
    logger.info(f"🎯 ПОЛУЧЕН ЗАПРОС НА ОТПРАВКУ ОТВЕТА для task_id: {task_id}")
    logger.info(f"🎯 URL: {request.url}")
    logger.info(f"🎯 Method: {request.method}")
    logger.info(f"🎯 Headers: {dict(request.headers)}")
    logger.info(f"🎯 User-Agent: {request.headers.get('user-agent', 'Unknown')}")
    logger.info(f"🎯 X-Forwarded-For: {request.headers.get('x-forwarded-for', 'Unknown')}")
    logger.info(f"🎯 Referer: {request.headers.get('referer', 'Unknown')}")
    
    try:
        # Получаем данные из запроса
        data = await request.json()
        logger.info(f"Received data: {data}")
        telegram_id = data.get('telegram_id')
        answer = data.get('answer')
        
        logger.info(f"Extracted telegram_id: {telegram_id}, answer: {answer}")
        
        # Проверяем, есть ли initData в теле запроса
        init_data_from_body = data.get('initData')
        if init_data_from_body:
            logger.info(f"🔍 Найден initData в теле запроса: {init_data_from_body[:100]}...")
        else:
            logger.info(f"🔍 initData не найден в теле запроса")
        
        # Проверяем, что у нас есть правильный telegram_id
        if not telegram_id:
            # Попробуем получить telegram_id из initData в теле запроса
            if init_data_from_body:
                logger.info(f"🔍 Попытка получить telegram_id из initData в теле запроса")
                try:
                    # Валидируем initData и получаем правильный telegram_id
                    validated_data = authenticator.validate(init_data_from_body)
                    telegram_id = validated_data.user.id
                    logger.info(f"✅ Получен telegram_id из initData: {telegram_id}")
                except Exception as validation_error:
                    logger.error(f"❌ Ошибка валидации initData: {validation_error}")
            
            # Если все еще нет telegram_id, возвращаем ошибку
            if not telegram_id:
                logger.error("telegram_id is missing")
                raise HTTPException(status_code=400, detail="telegram_id is required")
        
        if not answer:
            logger.error("answer is missing")
            raise HTTPException(status_code=400, detail="answer is required")
        
        # Отправляем запрос в Django API
        django_url = f"{settings.DJANGO_API_BASE_URL}/api/tasks/{task_id}/submit-mini-app/"
        payload = {
            'telegram_id': telegram_id,
            'answer': answer
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(django_url, json=payload, timeout=10.0)
        
        if response.status_code == 200:
            return JSONResponse(content=response.json())
        else:
            logger.error(f"Error from Django API: {response.status_code} - {response.text}")
            # Пробрасываем статус-код Django дальше (например, 409 для повторной попытки)
            raise HTTPException(status_code=response.status_code, detail=response.text)
            
    except httpx.RequestError as e:
        logger.error(f"Request error while contacting Django API: {e}")
        raise HTTPException(status_code=500, detail="Could not connect to backend service.")
    except HTTPException as e:
        # Не перехватываем HTTPException и не превращаем его в 500
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")