import logging

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from services.django_api_service import django_api_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def index(request: Request, search: str = None):
    logger.info("Rendering index page")
    topics = await django_api_service.get_topics(search=search)
    return templates.TemplateResponse("index.html", {"request": request, "topics": topics})

@router.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    logger.info("Rendering profile page shell.")
    return templates.TemplateResponse("profile.html", {"request": request, "user": None})

@router.get("/achievements", response_class=HTMLResponse)
async def achievements(request: Request):
    logger.info("Rendering achievements page")
    # Добавить логику, если нужно
    return templates.TemplateResponse("achievements.html", {"request": request})

@router.get("/statistics", response_class=HTMLResponse)
async def statistics(request: Request):
    logger.info("Rendering statistics page")
    # Добавить логику, если нужно
    return templates.TemplateResponse("statistics.html", {"request": request})

@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    logger.info("Rendering settings page")
    return templates.TemplateResponse("settings.html", {"request": request})

@router.get("/topic/{topic_id}", response_class=HTMLResponse)
async def topic_detail(request: Request, topic_id: int):
    logger.info(f"Rendering topic detail page for topic_id: {topic_id}")
    subtopics = await django_api_service.get_subtopics(topic_id=topic_id)
    # Нужна логика для получения имени темы
    topic_name = "Тема" # Заглушка
    return templates.TemplateResponse("topic_detail.html", {"request": request, "topic_name": topic_name, "subtopics": subtopics})

# Загрузка аватара останется здесь, так как она связана со страницей профиля
@router.post("/profile/{telegram_id}/update/", response_class=HTMLResponse)
async def update_profile(request: Request, telegram_id: int, avatar: UploadFile = File(...)):
    # Эта логика должна быть перенесена в api.py, но она принимает form-data, а не JSON.
    # Оставим ее пока здесь для простоты, но в идеале ее надо переделать.
    logger.info(f"Updating profile for telegram_id: {telegram_id}")
    # ... (логика проксирования на Django)
    pass 