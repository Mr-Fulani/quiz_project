import logging
import time

from fastapi import APIRouter, Request, UploadFile, File, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services.django_api_service import django_api_service
from services.localization import localization_service
from utils.cache_buster import get_js_url, get_css_url # Импортируем get_js_url и get_css_url
from core.config import settings as app_settings  # Импортируем настройки с алиасом

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request, 
    search: str = None,
    lang: str = Query(default=None, description="Language code"),
    tgWebAppStartParam: str = Query(default=None, alias="tgWebAppStartParam")
):
    # Обработка deep link
    if tgWebAppStartParam and tgWebAppStartParam.startswith("topic_"):
        try:
            topic_id = int(tgWebAppStartParam.split("_")[1])
            # Устанавливаем язык перед редиректом
            if lang:
                localization_service.set_language(lang)
            current_language = localization_service.get_language()
            return RedirectResponse(url=f"/topic/{topic_id}?lang={current_language}")
        except (ValueError, IndexError):
            logger.warning(f"Некорректный параметр deep link: {tgWebAppStartParam}")

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
        "share_topic_js_url": get_js_url('share-topic.js'),
        "share_topic_css_url": get_css_url('share-topic.css'),
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
        "share_topic_js_url": get_js_url('share-topic.js'),
        "share_topic_css_url": get_css_url('share-topic.css'),
    })

@router.get("/user_profile/{telegram_id}", response_class=HTMLResponse)
async def user_profile(
    request: Request,
    telegram_id: int,
    lang: str = Query(default=None, description="Language code")
):
    """
    Страница просмотра профиля другого пользователя.
    
    Отображает публичный или приватный профиль в зависимости от настроек пользователя.
    """
    # Язык уже установлен middleware, но можно переопределить через query параметр
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    logger.info(f"Rendering user profile page for telegram_id={telegram_id} with language: {current_language}")
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("user_profile.html", {
        "request": request,
        "telegram_id": telegram_id,
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
        "user_profile_css_url": get_css_url('user_profile.css'),
        "user_profile_js_url": get_js_url('user_profile.js'),
        "share_topic_js_url": get_js_url('share-topic.js'),
        "share_topic_css_url": get_css_url('share-topic.css'),
    })

@router.get("/top_users", response_class=HTMLResponse)
async def top_users(
    request: Request,
    lang: str = Query(default=None, description="Language code"),
    gender: str = Query(default=None, description="Gender filter"),
    age: str = Query(default=None, description="Age filter"),
    language_pref: str = Query(default=None, description="Programming language filter"),
    online_only: str = Query(default=None, description="Online users only filter")
):
    # Язык уже установлен middleware, но можно переопределить через query параметр
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    try:
        logger.info(f"Rendering top_users page with language: {current_language}")
        
        # Получаем переводы для текущего языка
        translations = localization_service.get_all_texts()
        
        # Получаем список топ-пользователей Mini App, передавая хост для правильных URL аватарок
        host = request.headers.get('x-forwarded-host') or request.headers.get('host')
        scheme = request.headers.get('x-forwarded-proto') or request.url.scheme
        logger.info(f"[DEBUG] top_users: host={host}, scheme={scheme}, all_headers={dict(request.headers)}")
        logger.info(f"[DEBUG] top_users filters: gender={gender}, age={age}, language_pref={language_pref}, online_only={online_only}")
        logger.info(f"[DEBUG] top_users query_params: {request.query_params}")
        top_users_data = await django_api_service.get_top_users_mini_app(
            language=current_language, host=host, scheme=scheme,
            gender=gender, age=age, language_pref=language_pref, online_only=online_only
        )
        
        # Получаем список языков программирования для фильтра
        programming_languages = await django_api_service.get_programming_languages()
        
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
            "programming_languages": programming_languages, # Передаем языки программирования для фильтра
            "tasks_js_url": get_js_url('tasks.js'),
            "localization_js_url": get_js_url('localization.js'),
            "share_app_js_url": get_js_url('share-app.js'),
            "donation_js_url": get_js_url('donation.js'),
            "styles_css_url": get_css_url('styles.css'),
            "share_app_css_url": get_css_url('share-app.css'),
            "donation_css_url": get_css_url('donation.css'),
            "top_users_js_url": get_js_url('top_users.js'),
            "share_topic_js_url": get_js_url('share-topic.js'),
            "share_topic_css_url": get_css_url('share-topic.css'),
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
    
    user_statistics = None  # Инициализируем переменную
    if telegram_id:
        try:
            host = request.headers.get('x-forwarded-host') or request.headers.get('host')
            scheme = request.headers.get('x-forwarded-proto') or request.url.scheme
            user_statistics = await django_api_service.get_user_statistics(
                telegram_id, host=host, scheme=scheme, language=current_language
            )
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
        "get_css_url": get_css_url,
        "get_js_url": get_js_url,
        "tasks_js_url": get_js_url('tasks.js'),
        "localization_js_url": get_js_url('localization.js'),
        "share_app_js_url": get_js_url('share-app.js'),
        "donation_js_url": get_js_url('donation.js'),
        "styles_css_url": get_css_url('styles.css'),
        "share_app_css_url": get_css_url('share-app.css'),
        "donation_css_url": get_css_url('donation.css'),
        "statistics_js_url": get_js_url('statistics.js'),
        "share_topic_js_url": get_js_url('share-topic.js'),
        "share_topic_css_url": get_css_url('share-topic.css'),
    })

@router.get("/admin-analytics", response_class=HTMLResponse)
async def admin_analytics(
    request: Request,
    lang: str = Query(default=None, description="Language code")
):
    """Страница админ-панели с аналитикой (только для админов)"""
    if lang:
        localization_service.set_language(lang)
    
    current_language = localization_service.get_language()
    logger.info(f"Rendering admin analytics page with language: {current_language}")
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("admin_analytics.html", {
        "request": request,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages(),
        # Добавляем функции для генерации URL с cache buster
        "get_css_url": get_css_url,
        "get_js_url": get_js_url,
        # Добавляем общие ресурсы, чтобы base.html корректно подключал стили и локализацию
        "styles_css_url": get_css_url('styles.css'),
        "localization_js_url": get_js_url('localization.js'),
        "share_app_css_url": get_css_url('share-app.css'),
        "donation_css_url": get_css_url('donation.css'),
        "tasks_js_url": get_js_url('tasks.js'),
        "share_app_js_url": get_js_url('share-app.js'),
        "donation_js_url": get_js_url('donation.js'),
        "share_topic_js_url": get_js_url('share-topic.js'),
        "share_topic_css_url": get_css_url('share-topic.css'),
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
    logger.info(f"📧 ADMIN_TELEGRAM_ID value: [{app_settings.ADMIN_TELEGRAM_ID}]")
    
    # Получаем переводы для текущего языка
    translations = localization_service.get_all_texts()
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "translations": translations,
        "current_language": current_language,
        "supported_languages": localization_service.get_supported_languages(),
        "admin_telegram_id": app_settings.ADMIN_TELEGRAM_ID,
        # Добавляем функции для генерации URL с cache buster
        "get_css_url": get_css_url,
        "get_js_url": get_js_url,
        "tasks_js_url": get_js_url('tasks.js'),
        "localization_js_url": get_js_url('localization.js'),
        "share_app_js_url": get_js_url('share-app.js'),
        "donation_js_url": get_js_url('donation.js'),
        "styles_css_url": get_css_url('styles.css'),
        "share_app_css_url": get_css_url('share-app.css'),
        "donation_css_url": get_css_url('donation.css'),
        "share_topic_js_url": get_js_url('share-topic.js'),
        "share_topic_css_url": get_css_url('share-topic.css'),
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
        "share_topic_js_url": get_js_url('share-topic.js'),
        "share_topic_css_url": get_css_url('share-topic.css'),
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
        "share_topic_js_url": get_js_url('share-topic.js'),
        "share_topic_css_url": get_css_url('share-topic.css'),
    })
    # Сбрасываем временную cookie уровня, чтобы не влияла на последующие переходы
    return response

@router.get("/share/topic/{topic_id}", response_class=HTMLResponse)
async def share_topic_preview(request: Request, topic_id: int):
    topic_data = await django_api_service.get_topic_detail(topic_id=topic_id)
    if not topic_data:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Построим базовый URL на основе заголовков запроса (работает за прокси и локально)
    host = request.headers.get('x-forwarded-host') or request.headers.get('host') or request.url.hostname
    scheme = request.headers.get('x-forwarded-proto') or request.url.scheme
    if host:
        base_url = f"{scheme}://{host}"
    else:
        # fallback к настройкам, если хост не определен
        base_url = app_settings.MINI_APP_BASE_URL

    # Конструируем абсолютный путь к изображению аккуратно, чтобы не получилось двойного слэша
    image_path = topic_data.get('video_poster_url') if topic_data.get('media_type') == 'video' and topic_data.get('video_poster_url') else topic_data.get('image_url', '')
    image_url = f"{base_url.rstrip('/')}/{image_path.lstrip('/')}" if image_path else ''

    context = {
        "request": request,
        "title": topic_data.get("name", "Quiz Topic"),
        "description": topic_data.get("description", "Check out this interesting topic!"),
        "image_url": image_url,
        # redirect_url оставляем для клика/кнопки на странице, но НЕ делаем автоматический редирект
        "redirect_url": f"https://t.me/mr_proger_bot/quiz?startapp=topic_{topic_id}"
    }
    # Возвращаем страницу с OG-мета — НЕ редиректим, чтобы мессенджеры могли считать превью
    response = templates.TemplateResponse("share_preview.html", context)
    return response

# Загрузка аватара останется здесь, так как она связана со страницей профиля
@router.post("/profile/{telegram_id}/update/", response_class=HTMLResponse)
async def update_profile(request: Request, telegram_id: int, avatar: UploadFile = File(...)):
    # Эта логика должна быть перенесена в api.py, но она принимает form-data, а не JSON.
    # Оставим ее пока здесь для простоты, но в идеале ее надо переделать.
    logger.info(f"Updating profile for telegram_id: {telegram_id}")
    # ... (логика проксирования на Django)
    pass
