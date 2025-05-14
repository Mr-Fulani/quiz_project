# bot/utils/utils.py

import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.database.models import TelegramGroup



logger = logging.getLogger(__name__)




async def create_groups_keyboard(groups: list, callback_prefix: str, include_select_all: bool = False) -> InlineKeyboardMarkup:
    """
    Создаёт inline-клавиатуру для выбора групп.

    Args:
        groups: Список объектов TelegramGroup.
        callback_prefix: Префикс для callback_data кнопок групп.
        include_select_all: Включать ли кнопку "Выбрать все".

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками групп.
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from bot.utils.markdownV2 import escape_markdown

    builder = InlineKeyboardBuilder()

    for group in groups:
        button_text = f"@{escape_markdown(group.username)}" if group.username else f"ID: {escape_markdown(str(group.group_id))}"
        builder.row(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"{callback_prefix}{group.group_id}"
            )
        )

    if include_select_all and groups:
        builder.row(
            InlineKeyboardButton(
                text="Выбрать все ✅",
                callback_data=f"{callback_prefix}all"
            )
        )

    builder.row(
        InlineKeyboardButton(text="Готово ✅", callback_data="confirm_groups"),
        InlineKeyboardButton(text="Отмена 🚫", callback_data="cancel")
    )

    return builder.as_markup()




async def promote_admin_in_group(bot: Bot, group_id: int, user_id: int) -> bool:
    """
    Назначает пользователя администратором в группе.

    Args:
        bot: Экземпляр Aiogram Bot.
        group_id: ID группы.
        user_id: Telegram ID пользователя.

    Returns:
        bool: True, если назначение успешно, False в случае ошибки.
    """
    try:
        await bot.promote_chat_member(
            chat_id=group_id,
            user_id=user_id,
            can_manage_chat=True,
            can_post_messages=True,
            can_edit_messages=True,
            can_delete_messages=True,
            can_invite_users=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_promote_members=False
        )
        logger.info(f"Пользователь {user_id} назначен админом в группе {group_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка назначения админа {user_id} в группе {group_id}: {e}")
        return False

async def demote_admin_in_group(bot: Bot, group_id: int, user_id: int) -> bool:
    """
    Снимает права администратора в группе.

    Args:
        bot: Экземпляр Aiogram Bot.
        group_id: ID группы.
        user_id: Telegram ID пользователя.

    Returns:
        bool: True, если снятие прав успешно, False в случае ошибки.
    """
    try:
        await bot.promote_chat_member(
            chat_id=group_id,
            user_id=user_id,
            can_manage_chat=False,
            can_post_messages=False,
            can_edit_messages=False,
            can_delete_messages=False,
            can_invite_users=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_promote_members=False
        )
        logger.info(f"Права админа {user_id} сняты в группе {group_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка снятия прав админа {user_id} в группе {group_id}: {e}")
        return False

async def get_available_groups(db_session: AsyncSession, admin_id: int) -> list:
    """
    Возвращает список групп, в которых пользователь ещё не является администратором.

    Args:
        db_session: Асинхронная сессия SQLAlchemy.
        admin_id: Telegram ID администратора.

    Returns:
        list: Список объектов TelegramGroup.
    """
    query = select(TelegramGroup).where(~TelegramGroup.admins.any(telegram_id=admin_id))
    result = await db_session.execute(query)
    return result.scalars().all()


