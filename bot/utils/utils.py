# bot/utils/utils.py

import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.database.models import TelegramGroup, TelegramAdmin
from bot.utils.markdownV2 import escape_markdown, format_group_link

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






async def remove_admin_rights(
    bot: Bot,
    db_session: AsyncSession,
    admin: TelegramAdmin,
    groups: list[TelegramGroup],
    notify_user: bool = True
) -> list[TelegramGroup]:
    """
    Снимает права админа в указанных группах и обновляет базу данных.

    Args:
        bot: Экземпляр Aiogram Bot.
        db_session: Асинхронная сессия SQLAlchemy.
        admin: Объект TelegramAdmin, представляющий админа.
        groups: Список объектов TelegramGroup для снятия прав.
        notify_user: Флаг, указывающий, нужно ли уведомлять админа.

    Returns:
        Список объектов TelegramGroup, где права были успешно сняты.
    """
    successful_groups = []
    admin_id = admin.telegram_id
    admin_username = admin.username

    for group in groups:
        try:
            # Проверка статуса пользователя
            member = await bot.get_chat_member(chat_id=group.group_id, user_id=admin_id)
            if member.status in ["left", "kicked"]:
                logger.info(f"Пользователь {admin_id} не в группе {group.group_id}, синхронизация базы")
                if any(g.group_id == group.group_id for g in admin.groups):
                    admin.groups = [g for g in admin.groups if g.group_id != group.group_id]
                    await db_session.commit()
                    logger.info(f"Группа {group.group_id} удалена из admin.groups для {admin_id}")
                continue

            # Проверка, является ли пользователь админом
            admins = await bot.get_chat_administrators(chat_id=group.group_id)
            is_admin_in_group = any(admin.user.id == admin_id for admin in admins)
            if not is_admin_in_group:
                logger.info(f"Пользователь {admin_id} не админ в группе {group.group_id}, синхронизация базы")
                if any(g.group_id == group.group_id for g in admin.groups):
                    admin.groups = [g for g in admin.groups if g.group_id != group.group_id]
                    await db_session.commit()
                    logger.info(f"Группа {group.group_id} удалена из admin.groups для {admin_id}")
                continue

            # Проверка прав бота
            bot_id = (await bot.get_me()).id
            bot_is_admin = any(admin.user.id == bot_id and admin.can_promote_members for admin in admins)
            if not bot_is_admin:
                logger.warning(f"Бот не имеет прав для снятия админов в группе {group.group_id}")
                continue

            # Снятие прав админа
            if await demote_admin_in_group(bot, group.group_id, admin_id):
                if any(g.group_id == group.group_id for g in admin.groups):
                    admin.groups = [g for g in admin.groups if g.group_id != group.group_id]
                    await db_session.commit()
                    logger.info(f"Группа {group.group_id} удалена из admin.groups для {admin_id}")
                successful_groups.append(group)
                logger.info(f"Права админа для {admin_id} сняты в группе {group.group_id}")

                if notify_user:
                    message_text = (
                        escape_markdown(f"ℹ️ Вы больше не админ в группе ") +
                        format_group_link(group) + escape_markdown(".")
                    )
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=message_text,
                            parse_mode="MarkdownV2"
                        )
                        logger.debug(f"Уведомление отправлено админу {admin_id} для группы {group.group_id}")
                    except Exception as e:
                        logger.error(f"Ошибка уведомления админа {admin_id} для группы {group.group_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка снятия прав админа для {admin_id} в группе {group.group_id}: {e}")
            continue

    return successful_groups
