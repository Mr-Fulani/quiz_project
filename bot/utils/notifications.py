import logging
from aiogram import Bot
from bot.database.models import TelegramAdmin

logger = logging.getLogger(__name__)

async def notify_admin(bot: Bot, action: str, admin: TelegramAdmin):
    """
    Отправляет уведомление администратору через Telegram API.

    Args:
        bot: Экземпляр Aiogram Bot.
        action: Действие ('added', 'updated', 'removed').
        admin: Объект TelegramAdmin с полем groups.

    Raises:
        Exception: Если не удалось отправить сообщение.
    """
    try:
        # Формируем список групп из admin.groups
        group_links = [group.username or f"ID: {group.group_id}" for group in admin.groups] if admin.groups else []
        group_text = ", ".join([f"[{group}](https://t.me/{group.lstrip('@')})" for group in group_links]) if group_links else "нет групп"

        if action == "added":
            message = f"Здравствуйте, @{admin.username or admin.telegram_id}!\nВы были добавлены как администратор.\nГруппы: {group_text}"
        elif action == "updated":
            message = f"Здравствуйте, @{admin.username or admin.telegram_id}!\nВаши права обновлены.\nГруппы: {group_text}"
        elif action == "removed":
            message = f"Здравствуйте, @{admin.username or admin.telegram_id}!\nВы удалены из администраторов.\nГруппы: {group_text}"
        else:
            logger.error(f"Некорректное действие: {action}")
            return

        await bot.send_message(
            chat_id=admin.telegram_id,
            text=message,
            parse_mode="Markdown"
        )
        logger.debug(f"Уведомление отправлено пользователю {admin.telegram_id} для действия {action}")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление пользователю {admin.telegram_id}: {e}")