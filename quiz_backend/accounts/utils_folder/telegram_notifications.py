import aiohttp
import logging
import os

logger = logging.getLogger(__name__)

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
            async with session.post(f"http://bot:8000/api/send-message/", json=payload) as response:
                if response.status != 200:
                    logger.error(f"Ошибка отправки уведомления: {response.status}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}")