import logging

from fastapi import APIRouter, Request, UploadFile, File, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from services.django_api_service import django_api_service
from services.localization import localization_service

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
    
    # Получаем темы с учетом языка
    topics = await django_api_service.get_topics(search=search, language=current_language)
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "topics": topics,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages()
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
        "supported_languages": localization_service.get_supported_languages()
    })

@router.get("/achievements", response_class=HTMLResponse)
async def achievements(
    request: Request,
    lang: str = Query(default=None, description="Language code")
):
    # Язык уже установлен middleware, но можно переопределить через query параметр
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    logger.info(f"Rendering achievements page with language: {current_language}")
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("achievements.html", {
        "request": request,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages()
    })

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
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("statistics.html", {
        "request": request,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages()
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
        "supported_languages": localization_service.get_supported_languages()
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
    subtopics = await django_api_service.get_subtopics(topic_id=topic_id, language=current_language)
    
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
        "supported_languages": localization_service.get_supported_languages()
    })

@router.get("/subtopic/{subtopic_id}/tasks", response_class=HTMLResponse)
async def subtopic_tasks(
    request: Request,
    subtopic_id: int,
    lang: str = Query(default=None, description="Language code")
):
    # Язык уже установлен middleware, но можно переопределить через query параметр
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    logger.info(f"Rendering subtopic tasks page for subtopic_id: {subtopic_id} with language: {current_language}")
    
    # Получаем данные подтемы
    subtopic_data = await django_api_service.get_subtopic_detail(subtopic_id=subtopic_id, language=current_language)
    
    # Получаем задачи для подтемы
    tasks = await django_api_service.get_tasks_for_subtopic(subtopic_id=subtopic_id, language=current_language)
    
    # Получаем данные родительской темы
    topic_data = None
    if subtopic_data and 'topic' in subtopic_data:
        topic_data = await django_api_service.get_topic_detail(topic_id=subtopic_data['topic'], language=current_language)
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("subtopic_tasks.html", {
        "request": request,
        "subtopic": subtopic_data,
        "topic": topic_data,
        "tasks": tasks,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages()
    })

# Загрузка аватара останется здесь, так как она связана со страницей профиля
@router.post("/profile/{telegram_id}/update/", response_class=HTMLResponse)
async def update_profile(request: Request, telegram_id: int, avatar: UploadFile = File(...)):
    # Эта логика должна быть перенесена в api.py, но она принимает form-data, а не JSON.
    # Оставим ее пока здесь для простоты, но в идеале ее надо переделать.
    logger.info(f"Updating profile for telegram_id: {telegram_id}")
    # ... (логика проксирования на Django)
    pass 