import logging
from aiogram import Router, types
from sqlalchemy.ext.asyncio import AsyncSession
import datetime
from sqlalchemy import select

from bot.database.models import UserChannelSubscription, TelegramUser, TelegramGroup

logger = logging.getLogger(__name__)
router = Router(name="user_router")


@router.chat_member()
async def handle_member_update(event: types.ChatMemberUpdated, db_session: AsyncSession):
    """
    Обрабатывает изменения статуса пользователя в канале или группе.
    Обновляет записи в таблице user_channel_subscriptions, фиксируя статус подписки пользователя.

    Args:
        event (types.ChatMemberUpdated): Событие изменения статуса участника от aiogram.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для взаимодействия с базой данных.
    """
    # Извлекаем новый и старый статус пользователя
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status
    chat = event.chat
    user = event.from_user

    # Логируем информацию об обновлении статуса
    logger.info(f"ChatMemberUpdated: chat_id={chat.id}, user_id={user.id}, {old_status} -> {new_status}")

    # Игнорируем ботов и отсутствующих пользователей
    if not user or user.is_bot:
        logger.debug("Игнорирование бота или отсутствующего пользователя.")
        return

    # Получаем пользователя из базы данных или создаем нового
    user_obj = await get_or_create_user(db_session, user)

    # Получаем существующую группу из базы данных
    channel_obj = await get_group(db_session, chat)

    if not channel_obj:
        # Группа не найдена, логируем и выходим
        logger.warning(f"Группа с ID {chat.id} не найдена в базе данных. Подписка не обновлена.")
        return

    # Обновляем запись о подписке пользователя на канал/группу
    subscription = await db_session.execute(
        select(UserChannelSubscription)
        .where(UserChannelSubscription.user_id == user_obj.id)
        .where(UserChannelSubscription.channel_id == channel_obj.group_id)
    )
    sub_obj = subscription.scalar_one_or_none()

    if new_status == "member":
        # Пользователь подписался на канал/группу
        if not sub_obj:
            # Если записи о подписке нет, создаем ее
            sub_obj = UserChannelSubscription(
                user_id=user_obj.id,
                channel_id=channel_obj.group_id,
                subscription_status="active",
                subscribed_at=datetime.datetime.utcnow()
            )
            db_session.add(sub_obj)
            logger.info(f"Создана новая подписка: пользователь {user_obj.id} на группу {channel_obj.group_id}")
        else:
            # Если запись существует, обновляем статус и дату подписки
            if sub_obj.subscription_status != "active":
                sub_obj.subscription_status = "active"
                sub_obj.subscribed_at = datetime.datetime.utcnow()
                sub_obj.unsubscribed_at = None
                logger.info(
                    f"Обновлена подписка: пользователь {user_obj.id} снова подписался на группу {channel_obj.group_id}")

    elif new_status == "left":
        # Пользователь отписался от канала/группы
        if sub_obj and sub_obj.subscription_status != "inactive":
            sub_obj.subscription_status = "inactive"
            sub_obj.unsubscribed_at = datetime.datetime.utcnow()
            logger.info(f"Отписка пользователя {user_obj.id} от группы {channel_obj.group_id}")

    # Сохраняем изменения в базе данных
    try:
        await db_session.commit()
        logger.debug("Изменения в подписках успешно сохранены.")
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Ошибка при сохранении изменений в подписках: {e}")


async def get_or_create_user(db_session: AsyncSession, from_user: types.User) -> TelegramUser:
    """
    Получает пользователя из таблицы telegram_users по Telegram ID или создаёт нового, если его нет.

    Args:
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для взаимодействия с базой данных.
        from_user (types.User): Объект пользователя Telegram из aiogram.

    Returns:
        TelegramUser: Объект пользователя из базы данных.
    """
    result = await db_session.execute(
        select(TelegramUser).where(TelegramUser.telegram_id == from_user.id)
    )
    user_obj = result.scalar_one_or_none()

    if not user_obj:
        # Если пользователя нет, создаём нового с необходимыми полями
        user_obj = TelegramUser(
            telegram_id=from_user.id,
            username=from_user.username or None,
            first_name=from_user.first_name or None,
            last_name=from_user.last_name or None,
            subscription_status="active",
            created_at=datetime.datetime.utcnow(),
            language=from_user.language_code or "unknown"
        )
        db_session.add(user_obj)
        try:
            await db_session.commit()
            logger.info(f"Создан новый пользователь: Telegram ID={from_user.id}")
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Ошибка при создании пользователя: {e}")
            raise
    else:
        logger.debug(f"Пользователь найден: Telegram ID={from_user.id}")
    return user_obj


async def get_group(db_session: AsyncSession, chat: types.Chat) -> TelegramGroup | None:
    """
    Получает группу (канал) из таблицы groups по Telegram ID.
    Если группа не найдена, возвращает None, не создавая новую запись.

    Args:
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для взаимодействия с базой данных.
        chat (types.Chat): Объект чата из Telegram.

    Returns:
        Group | None: Объект группы из базы данных или None, если группа не найдена.
    """
    # Ищем группу по Telegram ID чата
    result = await db_session.execute(
        select(TelegramGroup).where(TelegramGroup.group_id == chat.id)
    )
    group_obj = result.scalar_one_or_none()

    if group_obj:
        logger.debug(f"Группа найдена: {group_obj.group_name} (ID={group_obj.group_id})")
    else:
        logger.debug(f"Группа с ID {chat.id} не найдена.")
    return group_obj