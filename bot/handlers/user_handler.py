import logging
from aiogram import Router, types
from sqlalchemy.ext.asyncio import AsyncSession
import datetime
from sqlalchemy import select

from database.models import UserChannelSubscription, Group, User

logger = logging.getLogger(__name__)
router = Router(name="user_router")


@router.chat_member()
async def handle_member_update(event: types.ChatMemberUpdated, db_session: AsyncSession):
    """
    Обработка изменения статуса user в канале/группе.
    """
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status
    chat = event.chat
    user = event.from_user

    logger.info(f"ChatMemberUpdated: chat_id={chat.id}, user_id={user.id}, {old_status} -> {new_status}")

    if not user or user.is_bot:
        return

    user_obj = await get_or_create_user(db_session, user)
    channel_obj = await get_or_create_group(db_session, chat)

    # Обновляем запись UserChannelSubscription
    subscription = await db_session.execute(
        select(UserChannelSubscription)
        .where(UserChannelSubscription.user_id == user_obj.id)
        .where(UserChannelSubscription.channel_id == channel_obj.group_id)
    )
    sub_obj = subscription.scalar_one_or_none()

    if new_status == "member":
        # подписка
        if not sub_obj:
            sub_obj = UserChannelSubscription(
                user_id=user_obj.id,
                channel_id=channel_obj.group_id,
                subscription_status="active",
                subscribed_at=datetime.datetime.utcnow()
            )
            db_session.add(sub_obj)
        else:
            if sub_obj.subscription_status != "active":
                sub_obj.subscription_status = "active"
                sub_obj.subscribed_at = datetime.datetime.utcnow()
                sub_obj.unsubscribed_at = None

    elif new_status == "left":
        # отписка
        if sub_obj and sub_obj.subscription_status != "inactive":
            sub_obj.subscription_status = "inactive"
            sub_obj.unsubscribed_at = datetime.datetime.utcnow()

    await db_session.commit()


async def get_or_create_user(db_session: AsyncSession, from_user: types.User) -> User:
    result = await db_session.execute(
        select(User).where(User.telegram_id == from_user.id)
    )
    user_obj = result.scalar_one_or_none()
    if not user_obj:
        user_obj = User(
            telegram_id=from_user.id,
            username=from_user.username or None,
            subscription_status="active",
            created_at=datetime.datetime.utcnow(),
            language=from_user.language_code or "unknown"
        )
        db_session.add(user_obj)
        await db_session.commit()
    return user_obj


async def get_or_create_group(db_session: AsyncSession, chat: types.Chat) -> Group:
    result = await db_session.execute(
        select(Group).where(Group.group_id == chat.id)
    )
    group_obj = result.scalar_one_or_none()

    if not group_obj:
        group_obj = Group(
            group_id=chat.id,
            group_name=chat.title or "Без имени",
            topic_id=1,  # временно
            language="ru",
            location_type=chat.type,
            username=chat.username
        )
        db_session.add(group_obj)
        await db_session.commit()
    return group_obj