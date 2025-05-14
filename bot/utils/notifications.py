import logging
from aiogram import Bot
from bot.database.models import TelegramAdmin
from bot.utils.markdownV2 import format_group_link, escape_markdown

logger = logging.getLogger(__name__)

async def notify_admin(bot: Bot, action: str, admin: TelegramAdmin) -> None:
    """
    Отправляет уведомление администратору через Telegram API в формате MarkdownV2.

    Args:
        bot: Экземпляр Aiogram Bot.
        action: Действие ('added', 'updated', 'removed').
        admin: Объект TelegramAdmin с полем groups.

    Raises:
        TelegramBadRequest: Если не удалось отправить сообщение из-за ошибок Telegram API.
        Exception: Для других ошибок при отправке сообщения.
    """
    try:
        # Формируем список ссылок на группы с использованием format_group_link
        group_links = [format_group_link(group) for group in admin.groups] if admin.groups else []
        group_text = ", ".join(group_links) if group_links else escape_markdown("нет групп")

        # Экранируем username для безопасного отображения
        escaped_username = escape_markdown(admin.username or str(admin.telegram_id))

        if action == "added":
            message = (
                escape_markdown("Здравствуйте, @") + f"[{escaped_username}](https://t.me/{admin.username.lstrip('@') if admin.username else admin.telegram_id})" +
                escape_markdown("!\nВы были добавлены как администратор.\nГруппы: ") + group_text + escape_markdown(".")
            )
        elif action == "updated":
            message = (
                escape_markdown("Здравствуйте, @") + f"[{escaped_username}](https://t.me/{admin.username.lstrip('@') if admin.username else admin.telegram_id})" +
                escape_markdown("!\nВаши права обновлены.\nГруппы: ") + group_text + escape_markdown(".")
            )
        elif action == "removed":
            message = (
                escape_markdown("Здравствуйте, @") + f"[{escaped_username}](https://t.me/{admin.username.lstrip('@') if admin.username else admin.telegram_id})" +
                escape_markdown("!\nВы удалены из администраторов.\nГруппы: ") + group_text + escape_markdown(".")
            )
        else:
            logger.error(f"Некорректное действие: {action}")
            return

        await bot.send_message(
            chat_id=admin.telegram_id,
            text=message,
            parse_mode="MarkdownV2"
        )
        logger.debug(f"Уведомление отправлено пользователю {admin.telegram_id} для действия {action}: {message}")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление пользователю {admin.telegram_id}: {e}")