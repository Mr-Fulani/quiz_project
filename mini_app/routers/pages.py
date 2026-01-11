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
    tgWebAppStartParam: str = Query(default=None, alias="tgWebAppStartParam"),
    startapp: str = Query(default=None, description="Start parameter from URL")
):
    # Обработка deep link для комментариев
    # Проверяем оба варианта: tgWebAppStartParam (из query) и startapp (из URL параметра)
    # Также проверяем query параметры напрямую
    start_param = tgWebAppStartParam or startapp
    if not start_param:
        # Проверяем query параметры напрямую из request
        start_param = request.query_params.get('startapp') or request.query_params.get('tgWebAppStartParam')
    
    # Также проверяем URL напрямую (для случаев, когда параметр передается в URL, но не попадает в query_params)
    if not start_param:
        # Получаем полный URL и парсим его вручную
        full_url = str(request.url)
        if 'startapp=' in full_url:
            try:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(full_url)
                params = parse_qs(parsed.query)
                if 'startapp' in params:
                    start_param = params['startapp'][0]
            except Exception as e:
                logger.warning(f"⚠️ Ошибка парсинга URL для startapp: {e}")
    
    logger.info(f"🔗 [PAGES] Обработка startParam: tgWebAppStartParam={tgWebAppStartParam}, startapp={startapp}, start_param={start_param}, query_params={dict(request.query_params)}, full_url={str(request.url)}")
    
    if start_param and start_param.startswith("comment_"):
        try:
            comment_id = int(start_param.split("_")[1])
            logger.info(f"🔗 Deep link для комментария: comment_id={comment_id}")
            # Получаем информацию о комментарии через Django API
            try:
                comment_data = await django_api_service.get_comment_detail(comment_id)
                if comment_data:
                    translation_id = comment_data.get('translation_id')
                    task_id = comment_data.get('task_id')
                    subtopic_id = comment_data.get('subtopic_id')
                    topic_id = comment_data.get('topic_id')
                    language = comment_data.get('language', 'en')
                    
                    # Устанавливаем язык
                    if lang:
                        localization_service.set_language(lang)
                    elif language:
                        localization_service.set_language(language)
                    
                    current_language = localization_service.get_language()
                    
                    # Редиректим на страницу задач подтемы с параметрами для прокрутки к комментарию
                    if subtopic_id:
                        redirect_url = f"/subtopic/{subtopic_id}/tasks?comment_id={comment_id}&translation_id={translation_id}&lang={current_language}"
                    elif topic_id:
                        redirect_url = f"/topic/{topic_id}?comment_id={comment_id}&lang={current_language}"
                    else:
                        redirect_url = f"/?comment_id={comment_id}&lang={current_language}"
                    
                    logger.info(f"🔗 Редирект на: {redirect_url}")
                    return RedirectResponse(url=redirect_url)
                else:
                    logger.warning(f"⚠️ Не удалось получить данные комментария {comment_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка получения данных комментария {comment_id}: {e}", exc_info=True)
                # Fallback - просто открываем главную страницу
        except (ValueError, IndexError) as e:
            logger.warning(f"Некорректный параметр deep link для комментария: {start_param}, ошибка: {e}")
    
    # Обработка deep link для тем
    if start_param and start_param.startswith("topic_"):
        try:
            topic_id = int(start_param.split("_")[1])
            # Устанавливаем язык перед редиректом
            if lang:
                localization_service.set_language(lang)
            current_language = localization_service.get_language()
            return RedirectResponse(url=f"/topic/{topic_id}?lang={current_language}")
        except (ValueError, IndexError):
            logger.warning(f"Некорректный параметр deep link: {start_param}")

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
        
        # Получаем telegram_id из заголовков/куки для проверки админа
        telegram_id = request.headers.get('X-Telegram-User-Id')
        if not telegram_id:
            telegram_id = request.cookies.get('telegram_id')
        
        # Проверяем, является ли пользователь админом через Django API
        is_admin = False
        if telegram_id:
            try:
                telegram_id_int = int(telegram_id)
                # Получаем полный профиль пользователя из Django API для проверки is_admin
                # Используем метод get_miniapp_user_by_telegram, который возвращает полный профиль с is_admin
                user_profile = await django_api_service.get_miniapp_user_by_telegram(telegram_id_int)
                if user_profile and user_profile.get('is_admin'):
                    is_admin = True
                    logger.info(f"Пользователь {telegram_id_int} является админом")
            except (ValueError, TypeError) as e:
                logger.warning(f"Ошибка при проверке админа для telegram_id={telegram_id}: {e}")
            except Exception as e:
                # Если пользователь не найден или произошла ошибка, считаем что не админ
                logger.debug(f"Пользователь {telegram_id} не найден или ошибка при проверке админа: {e}")
                is_admin = False
        
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
            "is_admin": is_admin, # Флаг для проверки админа
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
    # ВАЖНО: На продакшене с правильным HTTPS доменом все будет работать корректно
    # При разработке с ngrok могут быть проблемы с мета-тегами Stories (это нормально)
    host = request.headers.get('x-forwarded-host') or request.headers.get('host') or request.url.hostname
    scheme = request.headers.get('x-forwarded-proto') or request.url.scheme
    
    # Проверяем, не является ли это ngrok URL (для разработки)
    is_ngrok = host and ('ngrok' in host.lower() or 'ngrok-free' in host.lower() or 'ngrok.io' in host.lower())
    
    # Принудительно используем https для share_url (для корректной работы соцсетей)
    # На продакшене всегда будет HTTPS, на ngrok тоже обычно HTTPS
    share_scheme = 'https' if scheme in ['https', 'http'] else scheme
    
    if host:
        base_url = f"{scheme}://{host}"
        share_base_url = f"{share_scheme}://{host}"
        
        # Логируем для отладки (можно убрать в продакшене)
        if is_ngrok:
            logger.info(f"⚠️ Используется ngrok URL для шаринга: {share_base_url} (на продакшене будет правильный домен)")
    else:
        # fallback к настройкам, если хост не определен
        base_url = app_settings.MINI_APP_BASE_URL
        share_base_url = app_settings.MINI_APP_BASE_URL
        logger.warning(f"⚠️ Хост не определен, используется fallback URL: {share_base_url}")

    # Конструируем абсолютный путь к изображению аккуратно, чтобы не получилось двойного слэша
    # ВАЖНО: Используем share_base_url (HTTPS) для изображений, чтобы они работали в Stories
    image_path = topic_data.get('video_poster_url') if topic_data.get('media_type') == 'video' and topic_data.get('video_poster_url') else topic_data.get('image_url', '')
    if image_path:
        # Убеждаемся, что путь начинается с / для правильной конкатенации
        image_path_clean = image_path.lstrip('/')
        image_url = f"{share_base_url.rstrip('/')}/{image_path_clean}"
    else:
        # Fallback на логотип приложения, если изображение темы отсутствует
        image_url = f"{share_base_url.rstrip('/')}/static/images/logo.png"

    # Получаем язык из параметров запроса или используем английский по умолчанию
    language = request.query_params.get('lang', 'en')
    if language not in ['ru', 'en']:
        language = 'en'
    
    # Проверяем откуда пришел пользователь (из мини-апп или по внешней ссылке)
    from_app = request.query_params.get('from', '') == 'app'
    
    # URL для редиректа в бота (прямая ссылка на мини-апп)
    bot_url = f"https://t.me/mr_proger_bot/quiz?startapp=topic_{topic_id}"
    
    # URL для шаринга БЕЗ параметра from=app (для внешних ссылок)
    share_url = f"{share_base_url}/share/topic/{topic_id}?lang={language}"
    
    # Текущий URL страницы для мета-тегов
    current_url = f"{share_base_url}/share/topic/{topic_id}?lang={language}"
    
    # Получаем локализованное описание темы
    topic_name = topic_data.get("name", "Quiz Topic")
    topic_description = topic_data.get("description", "")
    
    # Если описание пустое, используем дефолтное с локализацией
    if not topic_description or topic_description.strip() == "":
        if language == 'ru':
            topic_description = f"Изучайте тему '{topic_name}' через интерактивные квизы. Проходите тесты и получайте достижения!"
        else:
            topic_description = f"Learn the topic '{topic_name}' through interactive quizzes. Take tests and earn achievements!"
    
    context = {
        "request": request,
        "title": topic_name,
        "description": topic_description,
        "image_url": image_url,
        "redirect_url": bot_url,
        "share_url": share_url,
        "current_url": current_url,
        "language": language,
        "from_app": from_app
    }
    # Возвращаем страницу с кнопками соцсетей для всех пользователей
    response = templates.TemplateResponse("share_preview.html", context)
    return response

@router.get("/share/app", response_class=HTMLResponse)
async def share_app_preview(request: Request):
    """
    Страница для шаринга мини-приложения с правильными мета-тегами для Telegram и соцсетей
    """
    # Построим базовый URL на основе заголовков запроса (работает за прокси и локально)
    # ВАЖНО: На продакшене с правильным HTTPS доменом все будет работать корректно
    # При разработке с ngrok могут быть проблемы с мета-тегами Stories (это нормально)
    host = request.headers.get('x-forwarded-host') or request.headers.get('host') or request.url.hostname
    scheme = request.headers.get('x-forwarded-proto') or request.url.scheme
    
    # Проверяем, не является ли это ngrok URL (для разработки)
    is_ngrok = host and ('ngrok' in host.lower() or 'ngrok-free' in host.lower() or 'ngrok.io' in host.lower())
    
    # Принудительно используем https для share_url (для корректной работы соцсетей)
    # На продакшене всегда будет HTTPS, на ngrok тоже обычно HTTPS
    share_scheme = 'https' if scheme in ['https', 'http'] else scheme
    
    if host:
        base_url = f"{scheme}://{host}"
        share_base_url = f"{share_scheme}://{host}"
        current_url = f"{share_base_url}/share/app"
        
        # Логируем для отладки (можно убрать в продакшене)
        if is_ngrok:
            logger.info(f"⚠️ Используется ngrok URL для шаринга приложения: {share_base_url} (на продакшене будет правильный домен)")
    else:
        # fallback к настройкам, если хост не определен
        base_url = app_settings.MINI_APP_BASE_URL
        share_base_url = app_settings.MINI_APP_BASE_URL
        current_url = f"{share_base_url}/share/app"
        logger.warning(f"⚠️ Хост не определен, используется fallback URL: {share_base_url}")
    
    # Получаем язык из параметров запроса или используем английский по умолчанию
    language = request.query_params.get('lang', 'en')
    if language not in ['ru', 'en']:
        language = 'en'
    
    # Устанавливаем язык в сервисе локализации
    localization_service.set_language(language)
    translations = localization_service.get_all_texts()
    
    # Проверяем откуда пришел пользователь (из мини-апп или по внешней ссылке)
    from_app = request.query_params.get('from', '') == 'app'
    
    # URL для редиректа в бота (прямая ссылка на мини-апп)
    bot_url = "https://t.me/mr_proger_bot/quiz"
    
    # URL для шаринга БЕЗ параметра from=app (для внешних ссылок)
    share_url = f"{share_base_url}/share/app?lang={language}"
    
    # Конструируем абсолютный путь к изображению логотипа
    # Используем правильный формат без двойных слэшей
    # ВАЖНО: Используем share_base_url (HTTPS) для изображений, чтобы они работали в Stories
    image_path = "static/images/logo.png"
    image_url = f"{share_base_url.rstrip('/')}/{image_path}"
    
    # Название и описание приложения с локализацией
    app_title_ru = "Quiz Mini App - Образовательное приложение"
    app_title_en = "Quiz Mini App - Educational App"
    app_description_ru = "Изучайте различные темы через интерактивные квизы. Проходите тесты, получайте достижения и развивайте свои навыки!"
    app_description_en = "Learn various topics through interactive quizzes. Take tests, earn achievements and develop your skills!"
    
    title = app_title_ru if language == 'ru' else app_title_en
    description = app_description_ru if language == 'ru' else app_description_en
    
    context = {
        "request": request,
        "title": title,
        "description": description,
        "image_url": image_url,
        "redirect_url": bot_url,
        "share_url": share_url,
        "current_url": current_url,
        "language": language,
        "from_app": from_app
    }
    
    # Возвращаем страницу с кнопками соцсетей для всех пользователей
    response = templates.TemplateResponse("share_app.html", context)
    return response

# Загрузка аватара останется здесь, так как она связана со страницей профиля
@router.post("/profile/{telegram_id}/update/", response_class=HTMLResponse)
async def update_profile(request: Request, telegram_id: int, avatar: UploadFile = File(...)):
    # Эта логика должна быть перенесена в api.py, но она принимает form-data, а не JSON.
    # Оставим ее пока здесь для простоты, но в идеале ее надо переделать.
    logger.info(f"Updating profile for telegram_id: {telegram_id}")
    # ... (логика проксирования на Django)
    pass
