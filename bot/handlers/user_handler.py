import logging
from datetime import datetime, timezone
from typing import Optional

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import TelegramUser, TelegramGroup, UserChannelSubscription, TelegramAdmin

logger = logging.getLogger(__name__)
router = Router()


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
    # ИСПРАВЛЕНИЕ: используем пользователя, который изменил статус, а не того, кто выполнил действие
    user = event.new_chat_member.user

    # Логируем информацию об обновлении статуса
    logger.info(f"ChatMemberUpdated: chat_id={chat.id}, chat_title='{chat.title}', user_id={user.id}, username='{user.username}', {old_status} -> {new_status}")
    
    # Дополнительное логирование для отладки
    logger.info(f"=== ДЕТАЛЬНАЯ ОТЛАДКА ===")
    logger.info(f"Пользователь: ID={user.id}, username='{user.username}', first_name='{user.first_name}', last_name='{user.last_name}'")
    logger.info(f"Чат: ID={chat.id}, title='{chat.title}', type='{chat.type}'")
    logger.info(f"Статус: {old_status} -> {new_status}")
    logger.info(f"Новый статус детали: {event.new_chat_member}")
    logger.info(f"Старый статус детали: {event.old_chat_member}")
    logger.info(f"=== КОНЕЦ ОТЛАДКИ ===")

    # Игнорируем ботов и отсутствующих пользователей
    if not user or user.is_bot:
        logger.debug("Игнорирование бота или отсутствующего пользователя.")
        return

    # Проверяем, является ли пользователь админом
    admin_obj = await get_admin(db_session, user.id)
    
    if admin_obj:
        # Пользователь является админом - создаем TelegramUser для админа
        user_obj = await get_or_create_user_for_admin(db_session, admin_obj)
        logger.debug(f"Обработка подписки админа {user.id} (@{user.username or 'None'})")
    else:
        # Обычный пользователь - создаем TelegramUser
        user_obj = await get_or_create_user(db_session, user)
        logger.debug(f"Обработка подписки пользователя {user.id} (@{user.username or 'None'})")
    
    if not user_obj:
        logger.error(f"Не удалось получить или создать пользователя с ID {user.id}")
        return

    # Получаем существующую группу из базы данных
    channel_obj = await get_group(db_session, chat)
    if not channel_obj:
        logger.warning(f"Группа с ID {chat.id} не найдена в базе данных. Подписка не обновлена.")
        return

    # Обновляем запись о подписке пользователя на канал/группу
    subscription = await db_session.execute(
        select(UserChannelSubscription)
        .where(UserChannelSubscription.telegram_user_id == user_obj.id)  # Используем внутренний ID
        .where(UserChannelSubscription.channel_id == channel_obj.group_id)
    )
    sub_obj = subscription.scalar_one_or_none()

    if new_status == "member":
        # Пользователь подписался на канал/группу
        if not sub_obj:
            # Если записи о подписке нет, создаем ее
            sub_obj = UserChannelSubscription(
                telegram_user_id=user_obj.id,  # Используем внутренний ID
                channel_id=channel_obj.group_id,
                subscription_status="active",
                subscribed_at=datetime.now(timezone.utc)
            )
            db_session.add(sub_obj)
            logger.info(f"Создана новая подписка: пользователь {user_obj.id} на группу {channel_obj.group_id}")
        else:
            # Если запись существует, обновляем статус и дату подписки
            if sub_obj.subscription_status != "active":
                sub_obj.subscription_status = "active"
                sub_obj.subscribed_at = datetime.now(timezone.utc)
                sub_obj.unsubscribed_at = None
                logger.info(
                    f"Обновлена подписка: пользователь {user_obj.id} снова подписался на группу {channel_obj.group_id}")

    elif new_status in ("left", "kicked"):  # Добавлено "kicked" для большей надёжности
        # Пользователь отписался от канала/группы
        if sub_obj and sub_obj.subscription_status != "inactive":
            sub_obj.subscription_status = "inactive"
            sub_obj.unsubscribed_at = datetime.now(timezone.utc)
            logger.info(f"Отписка пользователя {user_obj.id} от группы {channel_obj.group_id}")
    
    elif new_status == "administrator":
        # Пользователь стал администратором канала
        logger.info(f"Пользователь {user_obj.id} стал администратором канала {channel_obj.group_id}")
        
        # Создаем запись админа через Django ORM
        try:
            logger.info("Начинаем создание админа через Django ORM...")
            import asyncio
            
            def create_admin_in_django():
                logger.info("Функция create_admin_in_django вызвана")
                import os
                import sys
                import django
                
                # Настройка Django
                os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_backend.settings')
                sys.path.append('/quiz_project')
                django.setup()
                logger.info("Django настроен")
                
                from accounts.models import TelegramAdmin
                from platforms.models import TelegramGroup
                
                # Получаем или создаем админа
                admin, created = TelegramAdmin.objects.get_or_create(
                    telegram_id=user_obj.telegram_id,
                    defaults={
                        'username': user.username or None,
                        'language': user.language_code or "ru",
                        'is_active': True
                    }
                )
                
                if created:
                    logger.info(f"Создан новый админ в Django: {user.username} (Telegram ID: {user_obj.telegram_id})")
                else:
                    logger.debug(f"Админ уже существует в Django: {user.username}")
                
                # Получаем группу
                group = TelegramGroup.objects.get(group_id=channel_obj.group_id)
                logger.info(f"Найдена группа: {group.group_name}")
                
                # Создаем связь через Django ORM
                if group not in admin.groups.all():
                    admin.groups.add(group)
                    logger.info(f"Создана связь админа {user.username} с группой {channel_obj.group_name}")
                    return True
                else:
                    logger.debug(f"Связь админа {user.username} с группой {channel_obj.group_name} уже существует")
                    return False
            
            # Выполняем синхронную функцию в отдельном потоке
            logger.info("Запускаем create_admin_in_django в отдельном потоке...")
            loop = asyncio.get_event_loop()
            link_created = await loop.run_in_executor(None, create_admin_in_django)
            logger.info(f"Результат создания админа: {link_created}")
            
        except Exception as e:
            logger.error(f"Ошибка создания админа через Django: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    # Сохраняем изменения в базе данных
    try:
        await db_session.commit()
        logger.debug("Изменения в подписках успешно сохранены.")
            
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Ошибка при сохранении изменений в подписках: {e}")


async def get_or_create_user(db_session: AsyncSession, from_user: types.User) -> TelegramUser | None:
    """
    Получает пользователя из таблицы telegram_users по Telegram ID или создаёт нового, если его нет.

    Args:
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для взаимодействия с базой данных.
        from_user (types.User): Объект пользователя Telegram из aiogram.

    Returns:
        TelegramUser | None: Объект пользователя из базы данных или None в случае ошибки.
    """
    try:
        # Проверяем, существует ли пользователь
        result = await db_session.execute(
            select(TelegramUser).where(TelegramUser.telegram_id == from_user.id)
        )
        user_obj = result.scalar_one_or_none()

        if not user_obj:
            # Если пользователя нет, создаём нового с необходимыми полями
            # ДОБАВИТЬ: Отладка перед созданием
            created_at = datetime.now(timezone.utc)
            logger.debug(f"Создаём пользователя с created_at={created_at}")
            user_obj = TelegramUser(
                telegram_id=from_user.id,
                username=from_user.username or None,
                first_name=from_user.first_name or None,
                last_name=from_user.last_name or None,
                subscription_status="active",
                created_at=created_at,
                language=from_user.language_code or "unknown",
                is_premium=from_user.is_premium if hasattr(from_user, "is_premium") else False,
                linked_user_id=None  # Явно указываем, что связь с CustomUser отсутствует
            )
            db_session.add(user_obj)
            await db_session.commit()
            logger.info(f"Создан новый пользователь: Telegram ID={from_user.id}, Username=@{from_user.username or 'None'}")
            

        else:
            logger.debug(f"Пользователь найден: Telegram ID={from_user.id}, Username=@{from_user.username or 'None'}")
        return user_obj
    except Exception as e:
        logger.error(f"Ошибка при создании пользователя Telegram ID={from_user.id}, Username=@{from_user.username or 'None'}: {e}")
        await db_session.rollback()
        return None


async def get_group(db_session: AsyncSession, chat: types.Chat) -> TelegramGroup | None:
    """
    Получает группу (канал) из таблицы groups по Telegram ID.
    Если группа не найдена, возвращает None, не создавая новую запись.

    Args:
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для взаимодействия с базой данных.
        chat (types.Chat): Объект чата из Telegram.

    Returns:
        TelegramGroup | None: Объект группы из базы данных или None, если группа не найдена.
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


async def get_admin(db_session: AsyncSession, telegram_id: int):
    """
    Проверяет, является ли пользователь админом.
    
    Args:
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для взаимодействия с базой данных.
        telegram_id (int): Telegram ID пользователя.
        
    Returns:
        TelegramAdmin | None: Объект админа из базы данных или None, если пользователь не админ.
    """
    try:
        result = await db_session.execute(
            select(TelegramAdmin).where(TelegramAdmin.telegram_id == telegram_id)
        )
        admin_obj = result.scalar_one_or_none()
        
        if admin_obj:
            logger.debug(f"Пользователь {telegram_id} является админом")
        else:
            logger.debug(f"Пользователь {telegram_id} не является админом")
            
        return admin_obj
    except Exception as e:
        logger.error(f"Ошибка при проверке админа {telegram_id}: {e}")
        return None


async def get_or_create_user_for_admin(db_session: AsyncSession, admin: TelegramAdmin) -> TelegramUser | None:
    """
    Получает или создает TelegramUser для админа.
    Используется когда админ подписывается на канал/группу.
    
    Args:
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для взаимодействия с базой данных.
        admin (TelegramAdmin): Объект админа.
        
    Returns:
        TelegramUser | None: Объект пользователя из базы данных или None в случае ошибки.
    """
    try:
        # Проверяем, существует ли уже TelegramUser для этого админа
        result = await db_session.execute(
            select(TelegramUser).where(TelegramUser.telegram_id == admin.telegram_id)
        )
        user_obj = result.scalar_one_or_none()

        if not user_obj:
            # Создаем TelegramUser для админа
            created_at = datetime.now(timezone.utc)
            user_obj = TelegramUser(
                telegram_id=admin.telegram_id,
                username=admin.username,
                first_name=None,  # У админов может не быть этих полей
                last_name=None,
                subscription_status="active",
                created_at=created_at,
                language=admin.language or "ru",
                is_premium=False,
                linked_user_id=None
            )
            db_session.add(user_obj)
            await db_session.commit()
            logger.info(f"Создан TelegramUser для админа {admin.telegram_id} (@{admin.username or 'None'})")
        else:
            logger.debug(f"TelegramUser для админа {admin.telegram_id} уже существует")
            
        return user_obj
    except Exception as e:
        logger.error(f"Ошибка при создании TelegramUser для админа {admin.telegram_id}: {e}")
        await db_session.rollback()
        return None