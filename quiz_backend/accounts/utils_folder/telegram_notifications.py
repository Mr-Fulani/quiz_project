import aiohttp
import logging
import os
import requests
from typing import Optional, List
from django.conf import settings
from django.db import models as django_models

logger = logging.getLogger(__name__)


def send_telegram_notification_sync(telegram_id: int, message: str, parse_mode: str = "Markdown") -> bool:
    """
    Синхронная отправка уведомления пользователю в Telegram через бота.
    Сначала пытается использовать прямой API Telegram, если не получается - через bot сервис.
    
    Args:
        telegram_id: Telegram ID получателя
        message: Текст сообщения
        parse_mode: Режим парсинга (Markdown, HTML или None)
        
    Returns:
        bool: True если отправлено успешно, иначе False
    """
    # Сначала пробуем прямой API Telegram
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if bot_token:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': telegram_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"✅ Уведомление отправлено пользователю {telegram_id} через Telegram API")
                return True
            else:
                logger.warning(f"⚠️ Telegram API вернул {response.status_code}, пробуем через bot сервис")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка отправки через Telegram API: {e}, пробуем через bot сервис")
    
    # Если прямой API не сработал, пробуем через bot сервис
    try:
        bot_url = os.getenv('BOT_API_URL', 'http://telegram_bot:8000')
        payload = {
            'chat_id': telegram_id,
            'text': message,
            'parse_mode': parse_mode
        }
        
        response = requests.post(
            f"{bot_url}/api/send-message/",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Уведомление отправлено пользователю {telegram_id} через bot сервис")
            return True
        else:
            logger.error(f"❌ Ошибка отправки уведомления через bot сервис: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Исключение при отправке уведомления через bot сервис: {e}")
        return False


def create_notification(
    recipient_telegram_id: int,
    notification_type: str,
    title: str,
    message: str,
    related_object_id: Optional[int] = None,
    related_object_type: Optional[str] = None,
    send_to_telegram: bool = True
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
        
    Returns:
        Объект Notification или None при ошибке
    """
    from accounts.models import Notification, MiniAppUser
    
    try:
        # Проверяем, включены ли уведомления у пользователя
        try:
            user = MiniAppUser.objects.get(telegram_id=recipient_telegram_id)
            if not user.notifications_enabled:
                logger.info(f"Уведомления отключены для пользователя {recipient_telegram_id}")
                # Всё равно создаём уведомление в БД, но не отправляем в Telegram
                send_to_telegram = False
        except MiniAppUser.DoesNotExist:
            logger.warning(f"Пользователь {recipient_telegram_id} не найден в MiniAppUser, но создаём уведомление")
        
        # Создаем запись уведомления в БД
        notification = Notification.objects.create(
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
            success = send_telegram_notification_sync(recipient_telegram_id, message)
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
    related_object_type: Optional[str] = None
) -> int:
    """
    Отправляет уведомление всем админам.
    Создает одно уведомление в БД (для всех админов) и отправляет в Telegram каждому админу.
    
    Args:
        notification_type: Тип уведомления
        title: Заголовок
        message: Текст сообщения
        related_object_id: ID связанного объекта
        related_object_type: Тип связанного объекта
        
    Returns:
        int: Количество админов, которым было отправлено уведомление
    """
    from accounts.models import MiniAppUser, Notification
    
    try:
        # Получаем всех админов
        admins = MiniAppUser.objects.filter(
            notifications_enabled=True
        ).filter(
            django_models.Q(telegram_admin__isnull=False) |
            django_models.Q(django_admin__isnull=False)
        ).distinct()
        
        if not admins.exists():
            logger.warning("Не найдено активных админов для отправки уведомления")
            return 0
        
        # Создаем ОДНО уведомление в БД для всех админов
        admin_notification = Notification.objects.create(
            recipient_telegram_id=None,  # NULL для админских уведомлений
            is_admin_notification=True,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_id=related_object_id,
            related_object_type=related_object_type
        )
        
        logger.info(f"📝 Создано админское уведомление #{admin_notification.id} для всех админов")
        
        # Отправляем в Telegram каждому админу
        sent_count = 0
        for admin in admins:
            success = send_telegram_notification_sync(admin.telegram_id, message)
            if success:
                sent_count += 1
        
        # Отмечаем уведомление как отправленное, если хотя бы одному админу отправлено
        if sent_count > 0:
            admin_notification.mark_as_sent()
        
        logger.info(f"📤 Уведомление отправлено {sent_count} из {admins.count()} админам")
        return sent_count
        
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомлений админам: {e}")
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