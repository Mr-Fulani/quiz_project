import aiohttp
import logging
import os
import re
import requests
from typing import Optional
from django.conf import settings
from django.db import models as django_models

logger = logging.getLogger(__name__)


def escape_markdown(text: str) -> str:
    """
    Экранирует специальные символы Markdown для Telegram.
    
    Args:
        text: Исходный текст
        
    Returns:
        str: Текст с экранированными специальными символами
    """
    if text is None:
        return ''

    # Для parse_mode="Markdown" (Telegram Markdown V1) требуется экранировать
    # только ограниченный набор символов. Расширенное экранирование приводило
    # к некорректным ссылкам (например, https://quiz-code.com -> https://quiz\-code\.com).
    # Экранируем только действительно необходимые символы и не трогаем символы URL.
    return re.sub(r'(?<!\\)([_*\[\]\(\)])', r'\\\1', text)


def escape_username_for_markdown(username: Optional[str]) -> str:
    """
    Экранирует username для Markdown так, чтобы символы не ломали форматирование
    и корректно отображались в Telegram.
    
    Args:
        username: Имя пользователя (может быть None)
        
    Returns:
        str: Экранированный username или пустая строка, если вход None
    """
    if username is None:
        return ''

    return re.sub(r'(?<!\\)([_*\[\]\(\)])', r'\\\1', username)


def get_base_url(request=None):
    """
    Получает базовый URL для формирования ссылок в уведомлениях.
    Для админских ссылок всегда использует основной домен (quiz-code.com), игнорируя поддомены.
    
    Приоритет:
    1. Из settings.SITE_URL (для продакшена) - ВСЕГДА используется для админских ссылок
    2. Из request заголовков (X-Forwarded-Host, X-Forwarded-Proto) - для работы через nginx/ngrok
    3. Из request.get_host() - стандартный способ Django
    
    Args:
        request: Django request объект (опционально)
        
    Returns:
        str: Базовый URL (например, https://quiz-code.com или https://xxx.ngrok-free.dev)
    """
    # Для админских ссылок всегда используем SITE_URL из настроек (основной домен)
    # Это гарантирует, что ссылки на админку будут работать корректно
    if hasattr(settings, 'SITE_URL') and settings.SITE_URL:
        # Убираем поддомены из SITE_URL если они есть (например, mini.quiz-code.com -> quiz-code.com)
        site_url = settings.SITE_URL
        # Если есть поддомен типа mini., убираем его
        if 'mini.' in site_url:
            site_url = site_url.replace('mini.', '')
        logger.debug(f"🌐 Используем SITE_URL из настроек (для админки): {site_url}")
        return site_url
    
    # Если передан request и нет SITE_URL, пытаемся получить URL из него
    if request:
        try:
            # Сначала проверяем заголовки X-Forwarded-Host и X-Forwarded-Proto
            # Это важно для работы через nginx/ngrok
            forwarded_host = request.META.get('HTTP_X_FORWARDED_HOST') or request.META.get('X-Forwarded-Host')
            forwarded_proto = request.META.get('HTTP_X_FORWARDED_PROTO') or request.META.get('X-Forwarded-Proto')
            
            if forwarded_host:
                # Используем заголовки от прокси (ngrok/nginx)
                scheme = forwarded_proto or 'https'
                # X-Forwarded-Host может содержать несколько хостов, берем первый
                host = forwarded_host.split(',')[0].strip()
                # Убираем поддомены для админских ссылок
                if 'mini.' in host:
                    host = host.replace('mini.', '')
                base_url = f"{scheme}://{host}"
                logger.debug(f"🌐 Используем URL из заголовков X-Forwarded-Host: {base_url}")
                return base_url
            
            # Если заголовков нет, используем стандартный способ Django
            scheme = request.scheme or 'https'
            host = request.get_host()
            if host and host not in ['localhost', '127.0.0.1'] and 'localhost' not in host:
                # Убираем поддомены для админских ссылок
                if 'mini.' in host:
                    host = host.replace('mini.', '')
                base_url = f"{scheme}://{host}"
                logger.debug(f"🌐 Используем URL из request.get_host(): {base_url}")
                return base_url
            else:
                logger.debug(f"⚠️ request.get_host() вернул localhost или невалидный хост: {host}, используем fallback")
        except Exception as e:
            logger.warning(f"Не удалось получить URL из request: {e}")
    
    # Последний fallback
    logger.warning("Не удалось определить базовый URL, используется дефолтный")
    return "https://quiz-code.com"


def get_mini_app_url(request=None):
    """
    Получает базовый URL для mini app (с поддоменом mini.).
    Для ссылок на mini app всегда использует поддомен mini.quiz-code.com.
    
    Args:
        request: Django request объект (опционально)
        
    Returns:
        str: Базовый URL для mini app (например, https://mini.quiz-code.com)
    """
    # Сначала проверяем настройки
    if hasattr(settings, 'SITE_URL') and settings.SITE_URL:
        site_url = settings.SITE_URL
        # Если в SITE_URL уже есть mini., используем его
        if 'mini.' in site_url:
            logger.debug(f"🌐 Используем SITE_URL с mini поддоменом: {site_url}")
            return site_url
        # Если нет mini., добавляем его
        # Заменяем основной домен на mini.домен
        if 'quiz-code.com' in site_url:
            mini_url = site_url.replace('quiz-code.com', 'mini.quiz-code.com')
            logger.debug(f"🌐 Добавляем mini поддомен: {mini_url}")
            return mini_url
        # Если другой домен, добавляем mini. в начало
        if '://' in site_url:
            parts = site_url.split('://', 1)
            mini_url = f"{parts[0]}://mini.{parts[1]}"
            logger.debug(f"🌐 Добавляем mini поддомен: {mini_url}")
            return mini_url
    
    # Если передан request, пытаемся получить URL из него и добавить mini.
    if request:
        try:
            forwarded_host = request.META.get('HTTP_X_FORWARDED_HOST') or request.META.get('X-Forwarded-Host')
            forwarded_proto = request.META.get('HTTP_X_FORWARDED_PROTO') or request.META.get('X-Forwarded-Proto')
            
            if forwarded_host:
                scheme = forwarded_proto or 'https'
                host = forwarded_host.split(',')[0].strip()
                # Добавляем mini. если его нет
                if 'mini.' not in host:
                    host = f"mini.{host}"
                mini_url = f"{scheme}://{host}"
                logger.debug(f"🌐 Используем URL из заголовков с mini поддоменом: {mini_url}")
                return mini_url
            
            scheme = request.scheme or 'https'
            host = request.get_host()
            if host and host not in ['localhost', '127.0.0.1'] and 'localhost' not in host:
                # Добавляем mini. если его нет
                if 'mini.' not in host:
                    host = f"mini.{host}"
                mini_url = f"{scheme}://{host}"
                logger.debug(f"🌐 Используем URL из request.get_host() с mini поддоменом: {mini_url}")
                return mini_url
        except Exception as e:
            logger.warning(f"Не удалось получить URL из request для mini app: {e}")
    
    # Fallback на дефолтный mini app URL
    logger.warning("Не удалось определить базовый URL для mini app, используется дефолтный")
    return "https://mini.quiz-code.com"


def get_mini_app_url_with_startapp(comment_id: int, request=None) -> str:
    """
    Формирует URL mini app для открытия комментария через WebAppInfo.
    Параметр startParam будет автоматически передан Telegram через window.Telegram.WebApp.startParam,
    поэтому в URL его указывать не нужно - просто возвращаем базовый URL mini app.
    
    Args:
        comment_id: ID комментария (используется только для логирования)
        request: Django request объект (опционально)
        
    Returns:
        str: Базовый URL mini app (например, https://mini.quiz-code.com/)
    """
    mini_app_url = get_mini_app_url(request)
    # Telegram автоматически передаст startParam через window.Telegram.WebApp.startParam
    # при открытии через WebAppInfo, поэтому просто возвращаем базовый URL
    logger.debug(f"🔗 Сформирован URL mini app для комментария {comment_id}: {mini_app_url}/")
    return f"{mini_app_url}/"


def get_comment_deep_link(comment_id: int) -> str:
    """
    Формирует deep link для открытия комментария в mini app через Telegram бота.
    
    Args:
        comment_id: ID комментария
        
    Returns:
        str: Deep link URL (например, https://t.me/mr_proger_bot?startapp=comment_123)
    """
    from django.conf import settings
    bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'mr_proger_bot')
    # Формат: https://t.me/bot_username?startapp=comment_123
    # Используем стандартный формат deep link без указания имени mini app
    # Telegram автоматически откроет mini app, настроенный в боте
    deep_link = f"https://t.me/{bot_username}?startapp=comment_{comment_id}"
    logger.debug(f"🔗 Сформирован deep link для комментария {comment_id}: {deep_link}")
    return deep_link


def get_web_app_url_for_notification(
    notification_type: str,
    related_object_id: Optional[int] = None,
    related_object_type: Optional[str] = None,
    request=None
) -> Optional[str]:
    """
    Формирует URL mini app для уведомления на основе типа уведомления и связанного объекта.
    
    Args:
        notification_type: Тип уведомления (feedback, comment, donation, subscription, report, other)
        related_object_id: ID связанного объекта
        related_object_type: Тип связанного объекта
        request: Django request объект (опционально)
        
    Returns:
        str: URL mini app с параметром startapp или None, если URL не может быть сформирован
    """
    if not related_object_id:
        return None
    
    mini_app_base_url = get_mini_app_url(request)
    
    # Формируем URL в зависимости от типа уведомления
    if notification_type == 'feedback' or related_object_type == 'feedback':
        return f"{mini_app_base_url}/?startapp=feedback_{related_object_id}"
    elif notification_type == 'comment' or related_object_type == 'comment':
        return f"{mini_app_base_url}/?startapp=comment_{related_object_id}"
    elif notification_type == 'donation' or related_object_type == 'donation':
        return f"{mini_app_base_url}/?startapp=donation_{related_object_id}"
    elif notification_type == 'subscription' or related_object_type == 'subscription':
        # Для подписки используем профиль пользователя
        return f"{mini_app_base_url}/?startapp=profile_{related_object_id}"
    elif notification_type == 'report' or related_object_type == 'report':
        # Для жалобы используем комментарий, на который пожаловались
        # Нужно получить comment_id из report через запрос к БД
        try:
            from tasks.models import TaskCommentReport
            report = TaskCommentReport.objects.filter(id=related_object_id).first()
            if report and report.comment_id:
                return f"{mini_app_base_url}/?startapp=comment_{report.comment_id}"
            else:
                logger.warning(f"⚠️ Не удалось найти report #{related_object_id} или его comment_id")
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения comment_id из report #{related_object_id}: {e}")
            return None
    elif notification_type == 'other' and related_object_type == 'message':
        # Для авторизации новых пользователей используем профиль
        return f"{mini_app_base_url}/?startapp=profile_{related_object_id}"
    else:
        # Для других типов используем главную страницу
        return f"{mini_app_base_url}/"


def format_markdown_link(text: str, url: str) -> str:
    """
    Формирует Markdown-ссылку, не экранируя допустимые символы в URL.
    
    Args:
        text: Текст ссылки
        url: Адрес, на который должна вести ссылка
        
    Returns:
        str: Строка с Markdown-ссылкой или экранированный текст, если URL пустой
    """
    if not url:
        return escape_markdown(text)

    escaped_text = escape_markdown(text)
    safe_url = re.sub(r'(?<!\\)([_*])', r'\\\1', url)
    safe_url = safe_url.replace(')', '\\)').replace('(', '\\(')
    return f"[{escaped_text}]({safe_url})"


def send_telegram_notification_sync(
    telegram_id: int,
    message: str,
    parse_mode: str = "Markdown",
    web_app_url: Optional[str] = None,
    tenant=None,
) -> bool:
    """
    Синхронная отправка уведомления пользователю в Telegram через бота.
    Сначала пытается использовать прямой API Telegram, если не получается - через bot сервис.
    При ошибке 400 (Bad Request) пытается отправить без parse_mode или с HTML.
    
    Args:
        telegram_id: Telegram ID получателя
        message: Текст сообщения
        parse_mode: Режим парсинга (Markdown, HTML или None)
        web_app_url: URL для открытия mini app (опционально, создаст inline keyboard button)
        
    Returns:
        bool: True если отправлено успешно, иначе False
    """
    # Формируем reply_markup если есть web_app_url
    reply_markup = None
    if web_app_url:
        # Telegram WebApp requires HTTPS
        if web_app_url.startswith("http://") and "localhost" not in web_app_url and "127.0.0.1" not in web_app_url:
            web_app_url = web_app_url.replace("http://", "https://")
            
        # Определяем текст кнопки в зависимости от типа уведомления (по URL)
        button_text = "Открыть в приложении"
        if "comment_" in web_app_url:
            button_text = "Открыть комментарий"
        elif "feedback_" in web_app_url:
            button_text = "Открыть обращение"
        elif "donation_" in web_app_url:
            button_text = "Открыть донат"
        elif "profile_" in web_app_url:
            button_text = "Открыть профиль"
        
        reply_markup = {
            "inline_keyboard": [[
                {
                    "text": button_text,
                    "web_app": {"url": web_app_url}
                }
            ]]
        }
    
    # Сначала пробуем прямой API Telegram.
    # В multi-tenant системе токен бота может отличаться в зависимости от тенанта.
    bot_token = getattr(tenant, "bot_token", None) or os.getenv('TELEGRAM_BOT_TOKEN')
    if bot_token:
        # Пробуем разные режимы парсинга при ошибке
        parse_modes_to_try = [parse_mode, None, "HTML"] if parse_mode else [None]
        
        for try_parse_mode in parse_modes_to_try:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    'chat_id': telegram_id,
                    'text': message
                }
                
                # Добавляем parse_mode только если он указан
                if try_parse_mode:
                    payload['parse_mode'] = try_parse_mode
                
                # Добавляем reply_markup если есть
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                
                response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"✅ Уведомление отправлено пользователю {telegram_id} через Telegram API (parse_mode: {try_parse_mode})")
                    return True
                elif response.status_code == 400:
                    # Если ошибка 400, пробуем следующий режим парсинга
                    error_data = response.json() if response.content else {}
                    error_desc = error_data.get('description', '')
                    logger.warning(f"⚠️ Telegram API вернул 400 (parse_mode: {try_parse_mode}): {error_desc}")
                    if try_parse_mode != parse_modes_to_try[-1]:  # Не последний режим
                        continue
                    # Если это последний режим, пробуем через bot сервис
                    break
                else:
                    logger.warning(f"⚠️ Telegram API вернул {response.status_code}, пробуем через bot сервис")
                    break
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отправки через Telegram API (parse_mode: {try_parse_mode}): {e}")
                if try_parse_mode == parse_modes_to_try[-1]:  # Последний режим
                    break
                continue
    
    # Если прямой API не сработал, пробуем через bot сервис
    parse_modes_to_try = [parse_mode, None, "HTML"] if parse_mode else [None]
    
    for try_parse_mode in parse_modes_to_try:
        try:
            bot_url = os.getenv('BOT_API_URL', 'http://telegram_bot:8000')
            payload = {
                'chat_id': telegram_id,
                'text': message
            }
            
            if try_parse_mode:
                payload['parse_mode'] = try_parse_mode
            
            # Добавляем reply_markup если есть
            if reply_markup:
                payload['reply_markup'] = reply_markup
            
            response = requests.post(
                f"{bot_url}/api/send-message/",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Уведомление отправлено пользователю {telegram_id} через bot сервис (parse_mode: {try_parse_mode})")
                return True
            elif response.status_code == 400 and try_parse_mode != parse_modes_to_try[-1]:
                logger.warning(f"⚠️ Bot сервис вернул 400 (parse_mode: {try_parse_mode}), пробуем следующий режим")
                continue
            else:
                logger.error(f"❌ Ошибка отправки уведомления через bot сервис: {response.status_code}")
                if try_parse_mode == parse_modes_to_try[-1]:
                    return False
                continue
                
        except Exception as e:
            logger.error(f"❌ Исключение при отправке уведомления через bot сервис (parse_mode: {try_parse_mode}): {e}")
            if try_parse_mode == parse_modes_to_try[-1]:
                return False
            continue
    
    return False


def create_notification(
    recipient_telegram_id: int,
    notification_type: str,
    title: str,
    message: str,
    related_object_id: Optional[int] = None,
    related_object_type: Optional[str] = None,
    send_to_telegram: bool = True,
    web_app_url: Optional[str] = None,
    tenant=None
) -> Optional[object]:
    """
    Создает уведомление в БД и опционально отправляет его в Telegram.
    
    Args:
        recipient_telegram_id: Telegram ID получателя
        notification_type: Тип уведомления (message, comment_reply, report и т.д.)
        title: Заголовок уведомления
        message: Текст уведомления
        related_object_id: ID связанного объекта (опционально)
        related_object_type: Тип связанного объекта (опционально)
        send_to_telegram: Отправлять ли уведомление в Telegram
        web_app_url: URL для открытия mini app (опционально, создаст inline keyboard button)
        
    Returns:
        Объект Notification или None при ошибке
    """
    from accounts.models import Notification, MiniAppUser
    
    try:
        # Проверяем, включены ли уведомления у пользователя
        user = None
        try:
            # В multi-tenant системе выбираем пользователя с приоритетом:
            # 1) текущий tenant, 2) глобальный tenant=None, 3) любой (fallback).
            user_qs = MiniAppUser.objects.filter(telegram_id=recipient_telegram_id)
            if tenant:
                user = user_qs.filter(tenant=tenant).first() or user_qs.filter(tenant__isnull=True).first()
            if not user:
                user = user_qs.first()
            if not user:
                raise MiniAppUser.DoesNotExist()
            if not user.notifications_enabled:
                logger.info(f"Уведомления отключены для пользователя {recipient_telegram_id}")
                # Всё равно создаём уведомление в БД, но не отправляем в Telegram
                send_to_telegram = False
        except MiniAppUser.DoesNotExist:
            logger.warning(f"Пользователь {recipient_telegram_id} не найден в MiniAppUser, но создаём уведомление")

        # Если tenant не передан явно, используем tenant найденного пользователя.
        notification_tenant = tenant or getattr(user, 'tenant', None)
        
        # Создаем запись уведомления в БД
        notification = Notification.objects.create(
            tenant=notification_tenant,
            recipient_telegram_id=recipient_telegram_id,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_id=related_object_id,
            related_object_type=related_object_type
        )
        
        logger.info(f"📝 Создано уведомление #{notification.id} для {recipient_telegram_id}")
        
        # Отправляем в Telegram если нужно
        if send_to_telegram:
            success = send_telegram_notification_sync(
                recipient_telegram_id,
                message,
                web_app_url=web_app_url,
                tenant=notification_tenant,
            )
            if success:
                notification.mark_as_sent()
        
        return notification
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания уведомления: {e}")
        return None


def notify_all_admins(
    notification_type: str,
    title: str,
    message: str,
    related_object_id: Optional[int] = None,
    related_object_type: Optional[str] = None,
    web_app_url: Optional[str] = None,
    request=None,
    tenant=None
) -> int:
    """
    Отправляет уведомление всем админам текущего тенанта.
    Создает одно уведомление в БД (для всех админов этого тенанта) и отправляет в Telegram каждому админу.
    
    Args:
        notification_type: Тип уведомления
        title: Заголовок
        message: Текст сообщения
        related_object_id: ID связанного объекта
        related_object_type: Тип связанного объекта
        web_app_url: URL для открытия mini app (опционально, если не указан, будет сформирован автоматически)
        request: Django request объект (опционально, используется для получения тенанта и формирования URL)
        tenant: Объект тенанта (опционально, имеет приоритет перед request.tenant)
        
    Returns:
        int: Количество админов, которым было отправлено уведомление
    """
    from accounts.models import MiniAppUser, Notification, TelegramAdmin
    
    try:
        # Пытаемся определить тенант
        if not tenant and request:
            tenant = getattr(request, 'tenant', None)
        
        # Базовый запрос: активные Telegram-админы.
        # Используем TelegramAdmin как первичный источник, чтобы не зависеть от OneToOne-связей в MiniAppUser.
        admins_qs = TelegramAdmin.objects.filter(is_active=True)

        # Фильтруем по тенанту если он известен (включаем также глобальных админов с tenant IS NULL)
        if tenant:
            admins_qs = admins_qs.filter(
                django_models.Q(tenant=tenant) | django_models.Q(tenant__isnull=True)
            )
            logger.debug(f"🔍 Фильтрация админов для уведомления по тенанту: {tenant} (включая глобальных)")
        else:
            # Если тенант не определен, уведомляем только глобальных админов
            admins_qs = admins_qs.filter(tenant__isnull=True)
            logger.warning("⚠️ Тенант не определен для уведомления админов. Уведомляем только глобальных админов.")

        admins = admins_qs.distinct()

        # Готовим финальный список telegram_id получателей.
        recipients = []
        recipient_ids = set()

        for admin in admins:
            if not admin.telegram_id:
                continue

            # Проверяем notifications_enabled в MiniAppUser, если такой профиль существует.
            mini_qs = MiniAppUser.objects.filter(telegram_id=admin.telegram_id)
            mini_user = None
            if tenant:
                mini_user = mini_qs.filter(tenant=tenant).first() or mini_qs.filter(tenant__isnull=True).first()
            if not mini_user:
                mini_user = mini_qs.first()

            if mini_user and not mini_user.notifications_enabled:
                logger.info(f"Уведомления отключены для админа {admin.telegram_id}, пропускаем отправку")
                continue

            if admin.telegram_id not in recipient_ids:
                recipient_ids.add(admin.telegram_id)
                recipients.append(admin.telegram_id)

        # Дополнительно включаем супер-админа из .env/settings, если задан.
        env_admin_chat_id = (
            getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)
            or os.getenv('TELEGRAM_ADMIN_CHAT_ID')
            or getattr(settings, 'ADMIN_TELEGRAM_ID', None)
            or os.getenv('ADMIN_TELEGRAM_ID')
        )
        if env_admin_chat_id:
            try:
                env_admin_chat_id_int = int(str(env_admin_chat_id).strip())
                if env_admin_chat_id_int not in recipient_ids:
                    recipient_ids.add(env_admin_chat_id_int)
                    recipients.append(env_admin_chat_id_int)
                    logger.debug(f"➕ Добавлен env/super-admin получатель: {env_admin_chat_id_int}")
            except (ValueError, TypeError):
                logger.warning(f"⚠️ Некорректный TELEGRAM_ADMIN_CHAT_ID/ADMIN_TELEGRAM_ID: {env_admin_chat_id!r}")

        if not recipients:
            logger.warning(f"Не найдено получателей для отправки админского уведомления (тенант: {tenant})")
            return 0
        
        # Если web_app_url не указан, пытаемся сформировать автоматически
        if not web_app_url and related_object_id:
            web_app_url = get_web_app_url_for_notification(
                notification_type=notification_type,
                related_object_id=related_object_id,
                related_object_type=related_object_type,
                request=request
            )
            if web_app_url:
                logger.debug(f"🔗 Автоматически сформирован web_app_url для уведомления: {web_app_url}")
        
        # Создаем ОДНО уведомление в БД для всех админов этого тенанта
        admin_notification = Notification.objects.create(
            tenant=tenant,
            recipient_telegram_id=None,  # NULL для админских уведомлений
            is_admin_notification=True,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_id=related_object_id,
            related_object_type=related_object_type
        )
        
        logger.info(f"📝 Создано админское уведомление #{admin_notification.id} для админов тенанта {tenant}")
        
        # Отправляем в Telegram каждому админу с web_app_url если есть
        sent_count = 0
        for telegram_id in recipients:
            success = send_telegram_notification_sync(
                telegram_id=telegram_id,
                message=message,
                web_app_url=web_app_url,
                tenant=tenant,
            )
            if success:
                sent_count += 1
        
        # Отмечаем уведомление как отправленное, если хотя бы одному админу отправлено
        if sent_count > 0:
            admin_notification.mark_as_sent()
        
        logger.info(f"📤 Уведомление отправлено {sent_count} из {len(recipients)} получателям (Тенант: {tenant})")
        return sent_count
        
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомлений админам: {e}", exc_info=True)
        return 0


async def notify_admin(action: str, admin, groups):
    """
    Отправляет уведомление в Telegram-бот о действиях с администратором через HTTP API.
    :param action: 'added', 'updated', или 'removed'.
    :param admin: Объект TelegramAdmin.
    :param groups: Список групп/каналов (QuerySet).
    """
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не найден")
        return

    group_links = [
        f"[{group.group_name}](https://t.me/{group.username})" if group.username else f"{group.group_name} (ID: {group.group_id})"
        for group in groups
    ]

    if action == 'added':
        message = f"Здравствуйте, {admin.username}!\nВы были добавлены как администратор:\n{', '.join(group_links)}"
    elif action == 'updated':
        message = f"Здравствуйте, {admin.username}!\nВаши права обновлены:\n{', '.join(group_links)}"
    elif action == 'removed':
        message = f"Здравствуйте, {admin.username}!\nВы удалены из администраторов:\n{', '.join(group_links)}"
    else:
        logger.error(f"Некорректное действие: {action}")
        return

    try:
        async with aiohttp.ClientSession() as session:
            payload = {'chat_id': admin.telegram_id, 'text': message, 'parse_mode': 'Markdown'}
            async with session.post(f"http://telegram_bot:8000/api/send-message/", json=payload) as response:
                if response.status != 200:
                    logger.error(f"Ошибка отправки уведомления: {response.status}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}")
