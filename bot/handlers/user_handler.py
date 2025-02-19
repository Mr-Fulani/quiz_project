# bot/handlers/user_handler.py

import logging
from aiogram import Router, types
from django.contrib.auth.hashers import make_password
from sqlalchemy.ext.asyncio import AsyncSession
import datetime
from sqlalchemy import select

from bot.database.models import UserChannelSubscription, User, Group

logger = logging.getLogger(__name__)
router = Router(name="user_router")


@router.chat_member()
async def handle_member_update(event: types.ChatMemberUpdated, db_session: AsyncSession):
    """
    Обрабатывает изменения статуса пользователя в канале или группе.

    Функция вызывается при каждом изменении статуса участника (например, присоединение или выход).
    Она обновляет базу данных, фиксируя текущий статус подписки пользователя на канал/группу.

    :param event: Объект события ChatMemberUpdated от aiogram.
    :param db_session: Асинхронная сессия SQLAlchemy для взаимодействия с базой данных.
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


async def get_or_create_user(db_session: AsyncSession, from_user: types.User) -> User:
    """
    Получает пользователя из базы данных по Telegram ID или создает нового, если его нет.
    """
    result = await db_session.execute(
        select(User).where(User.telegram_id == from_user.id)
    )
    user_obj = result.scalar_one_or_none()

    if not user_obj:
        # Если пользователя нет, создаем нового, передавая все обязательные поля
        user_obj = User(
            telegram_id=from_user.id,
            username=from_user.username or None,
            subscription_status="active",
            created_at=datetime.datetime.utcnow(),
            language=from_user.language_code or "unknown",
            password=make_password("passforuser"),
            is_superuser=False,        # обязательно, чтобы не было NULL
            is_staff=False,
            is_active=True
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



async def get_group(db_session: AsyncSession, chat: types.Chat) -> Group | None:
    """
    Получает группу (канал) из базы данных по Telegram ID.

    В отличие от `get_or_create_group`, эта функция **только** пытается найти существующую группу.
    Если группа не найдена, **не создает новую** и возвращает `None`.

    :param db_session: Асинхронная сессия SQLAlchemy.
    :param chat: Объект чата из Telegram.
    :return: Объект Group из базы данных или `None`, если группа не найдена.
    """
    # Ищем группу по Telegram ID чата
    result = await db_session.execute(
        select(Group).where(Group.group_id == chat.id)
    )
    group_obj = result.scalar_one_or_none()

    if group_obj:
        logger.debug(f"Группа найдена: {group_obj.group_name} (ID={group_obj.group_id})")
    else:
        logger.debug(f"Группа с ID {chat.id} не найдена.")
    return group_obj