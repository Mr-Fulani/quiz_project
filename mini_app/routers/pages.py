import logging
import time

from fastapi import APIRouter, Request, UploadFile, File, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from services.django_api_service import django_api_service
from services.localization import localization_service
from utils.cache_buster import get_js_url, get_css_url # Импортируем get_js_url и get_css_url

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request, 
    search: str = None,
    lang: str = Query(default=None, description="Language code")
):
    # Язык уже установлен middleware, но можно переопределить через query параметр
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    logger.info(f"Rendering index page with language: {current_language}")
    
    # Получаем telegram_id из заголовков/куки, если доступен
    telegram_id = request.headers.get('X-Telegram-User-Id')
    if not telegram_id:
        telegram_id = request.cookies.get('telegram_id')
    if telegram_id:
        telegram_id = int(telegram_id)
    
    # Получаем темы с учетом языка и telegram_id для прогресса, фильтруем только темы с задачами
    topics = await django_api_service.get_topics(search=search, language=current_language, telegram_id=telegram_id, has_tasks=True)
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "topics": topics,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages(),
        "tasks_js_url": get_js_url('tasks.js'),
        "localization_js_url": get_js_url('localization.js'),
        "share_app_js_url": get_js_url('share-app.js'),
        "donation_js_url": get_js_url('donation.js'),
        "styles_css_url": get_css_url('styles.css'),
        "share_app_css_url": get_css_url('share-app.css'),
        "donation_css_url": get_css_url('donation.css'),
        "search_js_url": get_js_url('search.js'),
        "topic_cards_js_url": get_js_url('topic-cards.js'),
    })

@router.get("/profile", response_class=HTMLResponse)
async def profile(
    request: Request,
    lang: str = Query(default=None, description="Language code")
):
    # Язык уже установлен middleware, но можно переопределить через query параметр
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    logger.info(f"Rendering profile page with language: {current_language}")
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages(),
        "tasks_js_url": get_js_url('tasks.js'),
        "localization_js_url": get_js_url('localization.js'),
        "share_app_js_url": get_js_url('share-app.js'),
        "donation_js_url": get_js_url('donation.js'),
        "styles_css_url": get_css_url('styles.css'),
        "share_app_css_url": get_css_url('share-app.css'),
        "donation_css_url": get_css_url('donation.css'),
        "profile_js_url": get_js_url('profile.js'),
    })

@router.get("/top_users", response_class=HTMLResponse)
async def top_users(
    request: Request,
    lang: str = Query(default=None, description="Language code")
):
    # Язык уже установлен middleware, но можно переопределить через query параметр
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    try:
        logger.info(f"Rendering top_users page with language: {current_language}")
        
        # Получаем переводы для текущего языка
        translations = localization_service.get_all_texts()
        
        # Получаем список топ-пользователей Mini App
        top_users_data = await django_api_service.get_top_users_mini_app(language=current_language)
        
        logger.info(f"Получены данные топ-пользователей: {top_users_data}")
        
        if not top_users_data: # Если список пуст, передаем пустой список и выводим сообщение
            logger.warning("Список топ-пользователей пуст или не содержит данных.")
            top_users_data = [] # Убедимся, что это список
        
        return templates.TemplateResponse("top_users.html", {
            "request": request,
            "translations": translations,
            "current_language": current_language,
            "supported_languages": localization_service.get_supported_languages(),
            "top_users": top_users_data, # Передаем данные топ-пользователей в шаблон
            "tasks_js_url": get_js_url('tasks.js'),
            "localization_js_url": get_js_url('localization.js'),
            "share_app_js_url": get_js_url('share-app.js'),
            "donation_js_url": get_js_url('donation.js'),
            "styles_css_url": get_css_url('styles.css'),
            "share_app_css_url": get_css_url('share-app.css'),
            "donation_css_url": get_css_url('donation.css'),
            "top_users_css_url": get_css_url('top_users.css'),
        })
    except Exception as e:
        logger.error(f"Ошибка при рендеринге страницы топ-пользователей: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/statistics", response_class=HTMLResponse)
async def statistics(
    request: Request,
    lang: str = Query(default=None, description="Language code")
):
    # Язык уже установлен middleware, но можно переопределить через query параметр
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    logger.info(f"Rendering statistics page with language: {current_language}")
    
    # Получаем telegram_id из заголовков/куки, если доступен
    telegram_id = request.headers.get('X-Telegram-User-Id')
    if not telegram_id:
        telegram_id = request.cookies.get('telegram_id')
    if telegram_id:
        telegram_id = int(telegram_id)
    
    # Получаем статистику пользователя, если telegram_id доступен
    user_statistics = None
    if telegram_id:
        try:
            user_statistics = await django_api_service.get_user_statistics(telegram_id)
            logger.info(f"Получена статистика для пользователя {telegram_id}: {user_statistics}")
        except Exception as e:
            logger.error(f"Ошибка при получении статистики для пользователя {telegram_id}: {e}")
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("statistics.html", {
        "request": request,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages(),
        "user_statistics": user_statistics,
        "telegram_id": telegram_id,
        "tasks_js_url": get_js_url('tasks.js'),
        "localization_js_url": get_js_url('localization.js'),
        "share_app_js_url": get_js_url('share-app.js'),
        "donation_js_url": get_js_url('donation.js'),
        "styles_css_url": get_css_url('styles.css'),
        "share_app_css_url": get_css_url('share-app.css'),
        "donation_css_url": get_css_url('donation.css'),
        "statistics_js_url": get_js_url('statistics.js'),
    })

@router.get("/settings", response_class=HTMLResponse)
async def settings(
    request: Request,
    lang: str = Query(default=None, description="Language code")
):
    # Язык уже установлен middleware, но можно переопределить через query параметр
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    logger.info(f"Rendering settings page with language: {current_language}")
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages(),
        "tasks_js_url": get_js_url('tasks.js'),
        "localization_js_url": get_js_url('localization.js'),
        "share_app_js_url": get_js_url('share-app.js'),
        "donation_js_url": get_js_url('donation.js'),
        "styles_css_url": get_css_url('styles.css'),
        "share_app_css_url": get_css_url('share-app.css'),
        "donation_css_url": get_css_url('donation.css'),
    })

@router.get("/topic/{topic_id}", response_class=HTMLResponse)
async def topic_detail(
    request: Request,
    topic_id: int,
    lang: str = Query(default=None, description="Language code")
):
    # Язык уже установлен middleware, но можно переопределить через query параметр
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    logger.info(f"Rendering topic detail page for topic_id: {topic_id} with language: {current_language}")
    
    # Получаем данные темы
    topic_data = await django_api_service.get_topic_detail(topic_id=topic_id, language=current_language)
    # Передаем telegram_id, чтобы сериализатор вернул solved_counts для прогресса
    telegram_id = request.headers.get('X-Telegram-User-Id') or request.cookies.get('telegram_id')
    if telegram_id:
        telegram_id = int(telegram_id)
    subtopics = await django_api_service.get_subtopics(topic_id=topic_id, language=current_language, has_tasks=True, telegram_id=telegram_id)
    
    # Получаем список всех тем для навигации
    topics = await django_api_service.get_topics(language=current_language)
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("topic_detail.html", {
        "request": request,
        "topic": topic_data,
        "subtopics": subtopics,
        "topics": topics,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages(),
        "tasks_js_url": get_js_url('tasks.js'),
        "localization_js_url": get_js_url('localization.js'),
        "share_app_js_url": get_js_url('share-app.js'),
        "donation_js_url": get_js_url('donation.js'),
        "styles_css_url": get_css_url('styles.css'),
        "share_app_css_url": get_css_url('share-app.css'),
        "donation_css_url": get_css_url('donation.css'),
        "topic_detail_js_url": get_js_url('topic-detail.js'),
    })

@router.get("/subtopic/{subtopic_id}/tasks", response_class=HTMLResponse)
async def subtopic_tasks(
    request: Request,
    subtopic_id: int,
    lang: str = Query(default=None, description="Language code"),
    level: str = Query(default=None, description="Difficulty filter: easy|medium|hard")
):
    logger.info(f"subtopic_tasks: Получен запрос для subtopic_id={subtopic_id}, lang={lang}, level={level}")
    logger.info(f"subtopic_tasks: request.query_params = {request.query_params}")
    logger.info(f"subtopic_tasks: request.cookies = {dict(request.cookies)}")
    
    # Язык уже установлен middleware, но можно переопределить через query параметр
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    logger.info(f"Rendering subtopic tasks page for subtopic_id: {subtopic_id} with language: {current_language}")
    
    # Получаем telegram_id из заголовков/куки, если доступен
    telegram_id = request.headers.get('X-Telegram-User-Id')
    if not telegram_id:
        telegram_id = request.cookies.get('telegram_id')
    if telegram_id:
        telegram_id = int(telegram_id)
    logger.info(f"subtopic_tasks: Определен telegram_id={telegram_id}")
    
    # Получаем данные подтемы
    subtopic_data = await django_api_service.get_subtopic_detail(subtopic_id=subtopic_id, language=current_language)
    
    # Нормализуем уровень из query-параметра или cookie
    level_normalized = (level or '').strip().lower()
    if level_normalized not in {"easy", "medium", "hard", "all"}:
        logger.info(f"subtopic_tasks: level_normalized не найден в query ({level}), ищем в cookie...")
        cookie_level = request.cookies.get(f"level_filter_{subtopic_id}")
        if cookie_level:
            level_normalized = cookie_level.strip().lower()
            logger.info(f"subtopic_tasks: Найден level_normalized из cookie: {level_normalized}")

    # Получаем задачи для подтемы, передавая уровень сложности в сервис Django API
    tasks = await django_api_service.get_tasks_for_subtopic(subtopic_id=subtopic_id, language=current_language, telegram_id=telegram_id, level=level_normalized)
    logger.info(f"subtopic_tasks: Получено {len(tasks)} задач после фильтрации Django API")

    # Локальная фильтрация больше не нужна, так как Django API должен возвращать уже отфильтрованные задачи
    # if level_normalized in {"easy", "medium", "hard"}:
    #     logger.info(f"subtopic_tasks: Фильтруем задачи по уровню: {level_normalized}")
    #     tasks = [t for t in tasks if (t.get('difficulty') or '').lower() == level_normalized]
    # else:
    #     logger.info(f"subtopic_tasks: Фильтрация по уровню не применена, level_normalized: {level_normalized}")
    
    # Получаем данные родительской темы
    topic_data = None
    if subtopic_data and 'topic' in subtopic_data:
        topic_data = await django_api_service.get_topic_detail(topic_id=subtopic_data['topic'], language=current_language)
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    response = templates.TemplateResponse("subtopic_tasks.html", {
        "request": request,
        "subtopic": subtopic_data,
        "topic": topic_data,
        "tasks": tasks,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages(),
        "tasks_js_url": get_js_url('tasks.js'),
        "localization_js_url": get_js_url('localization.js'),
        "share_app_js_url": get_js_url('share-app.js'),
        "donation_js_url": get_js_url('donation.js'),
        "styles_css_url": get_css_url('styles.css'),
        "share_app_css_url": get_css_url('share-app.css'),
        "donation_css_url": get_css_url('donation.css'),
    })
    # Сбрасываем временную cookie уровня, чтобы не влияла на последующие переходы
    return response

# Загрузка аватара останется здесь, так как она связана со страницей профиля
@router.post("/profile/{telegram_id}/update/", response_class=HTMLResponse)
async def update_profile(request: Request, telegram_id: int, avatar: UploadFile = File(...)):
    # Эта логика должна быть перенесена в api.py, но она принимает form-data, а не JSON.
    # Оставим ее пока здесь для простоты, но в идеале ее надо переделать.
    logger.info(f"Updating profile for telegram_id: {telegram_id}")
    # ... (логика проксирования на Django)
    pass 