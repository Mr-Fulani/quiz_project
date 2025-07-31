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
    lang: str = Query(default='en', description="Language code")
):
    logger.info(f"Rendering index page with language: {lang}")
    
    # Устанавливаем язык в сервисе локализации
    localization_service.set_language(lang)
    
    # Получаем темы с учетом языка
    topics = await django_api_service.get_topics(search=search, language=lang)
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts(lang)
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "topics": topics,
        "translations": translations,
        "current_language": lang,
        "supported_languages": localization_service.get_supported_languages()
    })

@router.get("/profile", response_class=HTMLResponse)
async def profile(
    request: Request,
    lang: str = Query(default='en', description="Language code")
):
    logger.info(f"Rendering profile page with language: {lang}")
    
    # Устанавливаем язык в сервисе локализации
    localization_service.set_language(lang)
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts(lang)
    
    return templates.TemplateResponse("profile.html", {
        "request": request, 
        "user": None,
        "translations": translations,
        "current_language": lang,
        "supported_languages": localization_service.get_supported_languages()
    })

@router.get("/achievements", response_class=HTMLResponse)
async def achievements(
    request: Request,
    lang: str = Query(default='en', description="Language code")
):
    logger.info(f"Rendering achievements page with language: {lang}")
    
    # Устанавливаем язык в сервисе локализации
    localization_service.set_language(lang)
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts(lang)
    
    return templates.TemplateResponse("achievements.html", {
        "request": request,
        "translations": translations,
        "current_language": lang,
        "supported_languages": localization_service.get_supported_languages()
    })

@router.get("/statistics", response_class=HTMLResponse)
async def statistics(
    request: Request,
    lang: str = Query(default='en', description="Language code")
):
    logger.info(f"Rendering statistics page with language: {lang}")
    
    # Устанавливаем язык в сервисе локализации
    localization_service.set_language(lang)
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts(lang)
    
    return templates.TemplateResponse("statistics.html", {
        "request": request,
        "translations": translations,
        "current_language": lang,
        "supported_languages": localization_service.get_supported_languages()
    })

@router.get("/settings", response_class=HTMLResponse)
async def settings(
    request: Request,
    lang: str = Query(default='en', description="Language code")
):
    logger.info(f"Rendering settings page with language: {lang}")
    
    # Устанавливаем язык в сервисе локализации
    localization_service.set_language(lang)
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts(lang)
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "translations": translations,
        "current_language": lang,
        "supported_languages": localization_service.get_supported_languages()
    })

@router.get("/topic/{topic_id}", response_class=HTMLResponse)
async def topic_detail(
    request: Request, 
    topic_id: int,
    lang: str = Query(default='en', description="Language code")
):
    logger.info(f"Rendering topic detail page for topic_id: {topic_id} with language: {lang}")
    
    # Устанавливаем язык в сервисе локализации
    localization_service.set_language(lang)
    
    # Получаем подтемы с учетом языка
    subtopics = await django_api_service.get_subtopics(topic_id=topic_id, language=lang)
    
    # Получаем информацию о теме
    topics = await django_api_service.get_topics(language=lang)
    topic = None
    for t in topics:
        if t.get('id') == topic_id:
            topic = t
            break
    
    if not topic:
        topic = {"id": topic_id, "name": f"Тема {topic_id}", "description": ""}
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts(lang)
    
    return templates.TemplateResponse("topic_detail.html", {
        "request": request, 
        "topic": topic, 
        "subtopics": subtopics,
        "translations": translations,
        "current_language": lang,
        "supported_languages": localization_service.get_supported_languages()
    })

@router.get("/subtopic/{subtopic_id}", response_class=HTMLResponse)
async def subtopic_tasks(
    request: Request, 
    subtopic_id: int,
    lang: str = Query(default='en', description="Language code")
):
    logger.info(f"Rendering subtopic tasks page for subtopic_id: {subtopic_id} with language: {lang}")
    
    # Устанавливаем язык в сервисе локализации
    localization_service.set_language(lang)
    
    # Получаем задачи для подтемы
    tasks = await django_api_service.get_tasks_for_subtopic(subtopic_id=subtopic_id, language=lang)
    
    # Получаем информацию о подтеме
    subtopic_info = None
    if tasks:
        subtopic_info = {
            'name': tasks[0].get('subtopic_name', f'Подтема {subtopic_id}'),
            'topic_name': tasks[0].get('topic_name', 'Тема')
        }
    else:
        subtopic_info = {
            'name': f'Подтема {subtopic_id}',
            'topic_name': 'Тема'
        }
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts(lang)
    
    return templates.TemplateResponse("subtopic_tasks.html", {
        "request": request, 
        "subtopic": subtopic_info,
        "tasks": tasks,
        "translations": translations,
        "current_language": lang,
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