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


def get_base_url(request=None, tenant=None):
    """
    Получает базовый URL для формирования ссылок в уведомлениях.
    
    Приоритет:
    1. Переданный объект tenant (используем его домен)
    2. Из settings.SITE_URL (для продакшена)
    3. Из request заголовков (X-Forwarded-Host, X-Forwarded-Proto)
    4. Из request.get_host()
    
    Args:
        request: Django request объект (опционально)
        tenant: Объект тенанта (опционально)
        
    Returns:
        str: Базовый URL (например, https://quiz-code.com или https://xxx.ngrok-free.dev)
    """
    # 1. Если передан тенант, используем его основной домен
    if tenant:
        if hasattr(tenant, 'site_url') and tenant.site_url:
            logger.debug(f"🌐 Используем site_url из тенанта: {tenant.site_url}")
            return tenant.site_url
        if hasattr(tenant, 'domain') and tenant.domain:
            # Предполагаем https для тенантов
            base = f"https://{tenant.domain.rstrip('/')}"
            logger.debug(f"🌐 Используем домен из тенанта: {base}")
            return base

    # 2. Для админских ссылок (если тенант не передан) пытаемся использовать SITE_URL из настроек
    if hasattr(settings, 'SITE_URL') and settings.SITE_URL:
        # Убираем поддомены из SITE_URL если они есть (например, mini.quiz-code.com -> quiz-code.com)
        site_url = settings.SITE_URL
        # Если есть поддомен типа mini., убираем его
        if 'mini.' in site_url:
            site_url = site_url.replace('mini.', '')
        logger.debug(f"🌐 Используем SITE_URL из настроек: {site_url}")
        return site_url
    
    # 3. Пытаемся получить из request
    if request:
        try:
            # Проверяем request.tenant если он есть (и tenant не был передан в аргументах)
            req_tenant = getattr(request, 'tenant', None)
            if req_tenant:
                if hasattr(req_tenant, 'site_url') and req_tenant.site_url:
                    return req_tenant.site_url
                if hasattr(req_tenant, 'domain') and req_tenant.domain:
                    return f"https://{req_tenant.domain.rstrip('/')}"

            # Сначала проверяем заголовки X-Forwarded-Host и X-Forwarded-Proto
            forwarded_host = request.META.get('HTTP_X_FORWARDED_HOST') or request.META.get('X-Forwarded-Host')
            forwarded_proto = request.META.get('HTTP_X_FORWARDED_PROTO') or request.META.get('X-Forwarded-Proto')
            
            if forwarded_host:
                scheme = forwarded_proto or 'https'
                host = forwarded_host.split(',')[0].strip()
                # Убираем поддомены типа mini.
                if 'mini.' in host:
                    host = host.replace('mini.', '')
                base_url = f"{scheme}://{host}"
                return base_url
            
            # Если заголовков нет, используем стандартный способ Django
            scheme = request.scheme or 'https'
            host = request.get_host()
            if 'mini.' in host:
                host = host.replace('mini.', '')
            return f"{scheme}://{host}"
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения URL из request: {e}")
            
    return "https://quiz-code.com"


def get_mini_app_url(request=None, tenant=None):
    """
    Получает базовый URL для Mini App.
    Приоритет:
    1. Переданный объект tenant (используем его mini_app_domain)
    2. Из settings.MINI_APP_URL
    3. Из request.tenant
    4. Конструирует из get_base_url (добавляя mini. если нужно)
    """
    # 1. Если передан тенант
    if tenant:
        if hasattr(tenant, 'mini_app_url') and tenant.mini_app_url:
            logger.debug(f"📱 Используем mini_app_url из тенанта: {tenant.mini_app_url}")
            return tenant.mini_app_url
        if hasattr(tenant, 'mini_app_domain') and tenant.mini_app_domain:
            url = f"https://{tenant.mini_app_domain.rstrip('/')}"
            logger.debug(f"📱 Используем mini_app_domain из тенанта: {url}")
            return url

    # 2. Пытаемся из настроек
    if hasattr(settings, 'MINI_APP_URL') and settings.MINI_APP_URL:
        return settings.MINI_APP_URL
    
    # 3. Пытаемся через request.tenant
    if request:
        req_tenant = getattr(request, 'tenant', None)
        if req_tenant:
            if hasattr(req_tenant, 'mini_app_url') and req_tenant.mini_app_url:
                return req_tenant.mini_app_url
            if hasattr(req_tenant, 'mini_app_domain') and req_tenant.mini_app_domain:
                return f"https://{req_tenant.mini_app_domain.rstrip('/')}"

    # 4. Фоллбэк - конструируем из базового URL
    base_url = get_base_url(request, tenant)
    
    # Если в базовом URL уже есть mini., возвращаем как есть
    if 'mini.' in base_url:
        return base_url
        
    # Пытаемся добавить mini. к домену
    if '://' in base_url:
        parts = base_url.split('://', 1)
        scheme = parts[0]
        domain = parts[1]
        
        # Если это не localhost/IP, добавляем mini.
        if not any(x in domain for x in ['localhost', '127.0.0.1', 'ngrok']):
            return f"{scheme}://mini.{domain}"
            
    return base_url


def get_mini_app_url_with_startapp(comment_id: int, request=None, tenant=None) -> str:
    """
    Формирует URL mini app для открытия комментария через WebAppInfo.
    """
    mini_app_url = get_mini_app_url(request, tenant)
    logger.debug(f"🔗 Сформирован URL mini app для комментария {comment_id}: {mini_app_url}/")
    return f"{mini_app_url}/"


def get_comment_deep_link(comment_id: int, tenant=None) -> str:
    """
    Формирует deep link для открытия комментария в mini app через Telegram бота.
    """
    # 1. Если передан тенант, используем его бота
    bot_username = None
    if tenant and hasattr(tenant, 'bot_username') and tenant.bot_username:
        bot_username = tenant.bot_username
    
    # 2. Фоллбэк на настройки
    if not bot_username:
        bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'mr_proger_bot')
    
    deep_link = f"https://t.me/{bot_username}?startapp=comment_{comment_id}"
    logger.debug(f"🔗 Сформирован deep link для комментария {comment_id}: {deep_link}")
    return deep_link


def get_web_app_url_for_notification(
    notification_type: str,
    related_object_id: Optional[int] = None,
    related_object_type: Optional[str] = None,
    request=None,
    tenant=None
) -> Optional[str]:
    """
    Формирует URL mini app для уведомления на основе типа уведомления и связанного объекта.
    
    Args:
        notification_type: Тип уведомления (feedback, comment, donation, subscription, report, other)
        related_object_id: ID связанного объекта
        related_object_type: Тип связанного объекта
        request: Django request объект (опционально)
        tenant: Объект тенанта (опционально)
        
    Returns:
        str: URL mini app с параметром startapp или None, если URL не может быть сформирован
    """
    if not related_object_id:
        return None
    
    mini_app_base_url = get_mini_app_url(request, tenant)
    
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
    tenant_bot_token = getattr(tenant, "bot_token", None)
    global_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    bot_tokens_to_try = [tenant_bot_token] if tenant_bot_token else []
    
    # Если токен тенанта отличается от глобального, добавляем глобальный как фоллбэк
    # (полезно, если супер-админ не запускал бота тенанта, но запускал глобального)
    if global_bot_token and global_bot_token not in bot_tokens_to_try:
        bot_tokens_to_try.append(global_bot_token)
        
    if not bot_tokens_to_try:
        logger.error("❌ Не найден bot_token ни в тенанте, ни в переменных окружения")
        return False

    for current_token in bot_tokens_to_try:
        # Пробуем разные режимы парсинга при ошибке
        parse_modes_to_try = [parse_mode, None, "HTML"] if parse_mode else [None]
        
        chat_not_found = False
        
        for try_parse_mode in parse_modes_to_try:
            try:
                url = f"https://api.telegram.org/bot{current_token}/sendMessage"
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
                    # Если ошибка 400, смотрим описание
                    error_data = response.json() if response.content else {}
                    error_desc = error_data.get('description', '')
                    logger.warning(f"⚠️ Telegram API вернул 400 (parse_mode: {try_parse_mode}): {error_desc}")
                    
                    if "chat not found" in error_desc.lower():
                        chat_not_found = True
                        break # Бессмысленно менять parse_mode, если чата нет
                        
                    if try_parse_mode != parse_modes_to_try[-1]:  # Не последний режим
                        continue
                    break
                else:
                    logger.warning(f"⚠️ Telegram API вернул {response.status_code}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отправки через Telegram API (parse_mode: {try_parse_mode}): {e}")
                if try_parse_mode == parse_modes_to_try[-1]:  # Последний режим
                    break
                continue
                
        # Если чат не найден для текущего токена, и есть еще токены в запасе, пробуем следующий
        if chat_not_found and current_token != bot_tokens_to_try[-1]:
            logger.info(f"🔄 Пробуем отправить через резервный токен бота для пользователя {telegram_id}")
            continue
        elif chat_not_found:
            logger.error(f"❌ Чат не найден для пользователя {telegram_id} ни в одном из ботов. Пользователь должен нажать /start в боте.")
            return False
            
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
    Отправляет уведомление TelegramAdmin о действиях с его аккаунтом напрямую через Telegram Bot API.
    :param action: 'added', 'updated', или 'removed' / 'deleted'.
    :param admin: Объект TelegramAdmin.
    :param groups: Список групп/каналов (QuerySet).
    """
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не найден — уведомление TelegramAdmin не отправлено")
        return

    if not admin.telegram_id:
        logger.warning(f"TelegramAdmin {admin} не имеет telegram_id, пропускаем уведомление")
        return

    group_links = [
        f"[{group.group_name}](https://t.me/{group.username.lstrip('@')})" if group.username
        else f"{group.group_name} (ID: {group.group_id})"
        for group in groups
    ]
    channels_text = ', '.join(group_links) if group_links else 'не указаны'

    if action == 'added':
        message = f"🎉 *Поздравляем, {admin.username or 'Администратор'}!*\n\nВы были добавлены как администратор:\n{channels_text}"
    elif action == 'updated':
        message = f"✏️ *{admin.username or 'Администратор'}*, ваши права обновлены:\n{channels_text}"
    elif action in ('removed', 'deleted'):
        message = f"⚠️ *{admin.username or 'Администратор'}*, вы удалены из администраторов:\n{channels_text}"
    else:
        logger.error(f"notify_admin: Некорректное действие: {action!r}")
        return

    # Отправляем напрямую через Telegram Bot API (больше не через внутренний бот-сервис)
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': admin.telegram_id,
            'text': message,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    logger.info(f"✅ Уведомление TelegramAdmin ({action}) отправлено → {admin.telegram_id}")
                else:
                    resp_text = await response.text()
                    logger.error(f"❌ Ошибка Telegram API при отправке уведомления TelegramAdmin: {response.status} — {resp_text}")
    except Exception as e:
        logger.error(f"❌ Исключение при отправке уведомления TelegramAdmin {admin.telegram_id}: {e}")
