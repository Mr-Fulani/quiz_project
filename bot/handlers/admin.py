from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import logging
import os
import asyncio
from django.utils import timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ContentType, CallbackQuery, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
from bot.database.database import get_session
from bot.database.models import TelegramAdmin, TelegramGroup, TelegramUser, UserChannelSubscription
from bot.keyboards.reply_keyboards import get_start_reply_keyboard
from bot.services.admin_service import is_admin, add_admin, remove_admin
from bot.states.admin_states import AddAdminStates, RemoveAdminStates
from bot.utils.notifications import notify_admin






# Загрузка переменных окружения
load_dotenv()

# Инициализация маршрутизатора
router = Router(name="admin_router")

# Настройка логирования
logger = logging.getLogger(__name__)

# Секретные пароли
ADMIN_SECRET_PASSWORD = os.getenv("ADMIN_SECRET_PASSWORD")
ADMIN_REMOVE_SECRET_PASSWORD = os.getenv("ADMIN_REMOVE_SECRET_PASSWORD")

# Символы, которые нужно экранировать в MarkdownV2
MARKDOWN_V2_SPECIAL_CHARS = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

def escape_markdown_v2(text: str) -> str:
    """
    Экранирует специальные символы для MarkdownV2.
    """
    if not text:
        return text
    for char in MARKDOWN_V2_SPECIAL_CHARS:
        text = text.replace(char, f'\\{char}')
    return text


@router.message(Command("add_admin"))
@router.callback_query(F.data == "add_admin_button")
async def cmd_add_admin(query: types.Message | types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Запрашивает пароль для добавления админа, если пользователь — админ.
    """
    user_id = query.from_user.id
    message = query if isinstance(query, types.Message) else query.message
    username = query.from_user.username or "None"

    if not await is_admin(user_id, db_session):
        await message.reply("⛔ У вас нет прав для этой команды.", reply_markup=get_start_reply_keyboard())
        logger.warning(f"Пользователь {username} ({user_id}) попытался добавить админа без прав.")
        if isinstance(query, types.CallbackQuery):
            await query.answer()
        return

    await message.reply(
        "🔒 Введите секретный пароль для добавления админа:\n\n_Символы видны только вам._",
        parse_mode="Markdown",
        reply_markup=ForceReply(selective=True)
    )
    logger.debug("Запрошен пароль для добавления админа")
    await state.set_state(AddAdminStates.waiting_for_password)
    if isinstance(query, types.CallbackQuery):
        await query.answer()


@router.message(AddAdminStates.waiting_for_password, F.content_type == ContentType.TEXT)
async def process_add_admin_password(message: Message, state: FSMContext, db_session: AsyncSession):
    """
    Проверяет пароль и запрашивает Telegram ID.
    """
    username = message.from_user.username or "None"
    try:
        if message.text.strip() != ADMIN_SECRET_PASSWORD:
            await message.reply("❌ Неверный пароль.", reply_markup=get_start_reply_keyboard())
            logger.warning(f"Неверный пароль от {username} ({message.from_user.id}).")
            await state.clear()
            return
        await message.reply(
            "✅ Пароль верный. Введите Telegram ID нового админа: 🔢",
            reply_markup=ForceReply(selective=True)
        )
        logger.debug("Пароль верен. Запрошен Telegram ID")
        await state.set_state(AddAdminStates.waiting_for_user_id)
    except Exception as e:
        logger.error(f"Ошибка в process_add_admin_password: {e}")
        await message.reply("❌ Ошибка. Попробуйте снова.", reply_markup=get_start_reply_keyboard())
        await state.clear()


@router.message(AddAdminStates.waiting_for_user_id, F.content_type == ContentType.TEXT)
async def process_add_admin_user_id(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    """
    Проверяет Telegram ID и запрашивает группы.
    """
    username = message.from_user.username or "None"
    if not message.text:
        await message.reply("❌ Введите числовой Telegram ID.", reply_markup=ForceReply(selective=True))
        logger.warning(f"Пустое сообщение от {username} ({message.from_user.id}).")
        return

    try:
        new_admin_id = int(message.text.strip())
    except ValueError:
        await message.reply("❌ Введите корректный числовой ID.", reply_markup=ForceReply(selective=True))
        logger.debug(f"Некорректный ID от {username}: {message.text}")
        return

    if await is_admin(new_admin_id, db_session):
        await message.reply("ℹ️ Этот пользователь уже админ.", reply_markup=get_start_reply_keyboard())
        logger.info(f"Пользователь {new_admin_id} уже админ.")
        await state.clear()
        return

    try:
        user = await bot.get_chat(new_admin_id)
        new_username = user.username.lstrip("@") if user.username else None
        new_language = user.language_code if hasattr(user, "language_code") else None
    except Exception as e:
        await message.reply("❌ Пользователь не найден.", reply_markup=get_start_reply_keyboard())
        logger.error(f"Ошибка получения чата {new_admin_id}: {e}")
        await state.clear()
        return

    await state.update_data(new_admin_id=new_admin_id, new_username=new_username, new_language=new_language)

    # Получаем группы, где юзер не админ
    query = select(TelegramGroup).where(~TelegramGroup.admins.any(telegram_id=new_admin_id))
    result = await db_session.execute(query)
    groups = result.scalars().all()

    if not groups:
        await message.reply(
            "🚫 Нет доступных групп, админ будет создан без привязки.",
            reply_markup=get_start_reply_keyboard()
        )
        logger.debug("Нет доступных групп")
        await state.update_data(selected_groups=[])
        await confirm_admin_creation(message, state, bot, db_session, message.message_id)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for group in groups:
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=group.username or f"ID: {group.group_id}",
                                  callback_data=f"group_{group.group_id}")]
        )
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="Без групп 🚫", callback_data="no_groups")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="Готово ✅", callback_data="confirm_groups")])

    groups_message = await message.reply("📋 Выберите группы/каналы для админа:", reply_markup=keyboard)
    await state.update_data(groups_message_id=groups_message.message_id)
    logger.debug("Показаны группы для выбора")
    await state.set_state(AddAdminStates.waiting_for_groups)


@router.callback_query(AddAdminStates.waiting_for_groups,
                       F.data.startswith("group_") | F.data.in_(["no_groups", "confirm_groups"]))
async def process_add_admin_groups(call: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot):
    """
    Обрабатывает выбор групп через inline-кнопки.
    """
    data = await state.get_data()
    selected_groups = data.get("selected_groups", [])

    if call.data.startswith("group_"):
        group_id = int(call.data.replace("group_", ""))
        query = select(TelegramGroup).where(TelegramGroup.group_id == group_id)
        result = await db_session.execute(query)
        group = result.scalar_one_or_none()
        if group and group not in selected_groups:
            selected_groups.append(group)
            await state.update_data(selected_groups=selected_groups)
            await call.answer(f"Группа {group.username or group.group_id} добавлена")
        else:
            await call.answer("Группа уже выбрана или не найдена")
        return

    if call.data == "no_groups":
        await state.update_data(selected_groups=[])
        await call.answer("Выбрано: без групп")

    if call.data == "confirm_groups":
        await confirm_admin_creation(call.message, state, bot, db_session, data.get("groups_message_id"))
    await call.answer()


async def confirm_admin_creation(message: Message, state: FSMContext, bot: Bot, db_session: AsyncSession,
                                groups_message_id: int):
    """
    Показывает подтверждение и сохраняет админа.
    """
    data = await state.get_data()
    new_admin_id = data.get("new_admin_id")
    new_username = data.get("new_username")
    new_language = data.get("new_language")
    selected_groups = data.get("selected_groups", [])

    group_names = ", ".join(
        [f"[{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id})" for group in selected_groups]
    ) if selected_groups else "без групп"
    text = (
        f"Создать админа? 🤔\n"
        f"ID: {new_admin_id}\n"
        f"Username: @{new_username or 'Без username'}\n"
        f"Группы: {group_names}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить ✅", callback_data="confirm_admin")],
        [InlineKeyboardButton(text="Отмена 🚫", callback_data="cancel")]
    ])
    await message.reply(text, parse_mode="Markdown", reply_markup=keyboard)
    await state.update_data(groups_message_id=groups_message_id)
    await state.set_state(AddAdminStates.waiting_for_confirmation)




@router.callback_query(lambda c: c.data in ["confirm_admin", "cancel"])
async def process_admin_confirmation(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """
    Обрабатывает подтверждение или отмену добавления нового администратора.

    Проверяет подписку нового администратора на группы, создаёт подписки в таблице user_channel_subscriptions,
    назначает администратора в группах, отправляет уведомления текущему и новому администратору.
    При отмене очищает состояние и удаляет временные сообщения.

    Args:
        call: Объект CallbackQuery от inline-кнопки подтверждения или отмены.
        state: Контекст FSM для управления состоянием.
        bot: Экземпляр Aiogram Bot для взаимодействия с Telegram API.

    Returns:
        None
    """
    data = await state.get_data()
    new_admin_id = data.get("new_admin_id")
    new_username = data.get("new_username")
    new_language = data.get("new_language")
    selected_groups = data.get("selected_groups", [])
    groups_message_id = data.get("groups_message_id")

    await call.answer()

    if call.data == "cancel":
        await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
        await call.message.answer(
            text="❌ Добавление админа отменено.",
            parse_mode="Markdown",
            reply_markup=get_start_reply_keyboard()
        )
        await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        await state.clear()
        return

    async with get_session() as db_session:
        try:
            # Добавить админа в TelegramAdmin
            new_admin = TelegramAdmin(
                telegram_id=new_admin_id,
                username=new_username,
                language=new_language,
                is_active=True
            )
            await add_admin(new_admin_id, new_username, db_session, groups=selected_groups)
            logger.info(f"Админ с ID {new_admin_id} (@{new_username}) добавлен с группами: {[g.username for g in selected_groups]}")

            # Найти TelegramUser
            telegram_user = (await db_session.execute(
                select(TelegramUser).where(TelegramUser.telegram_id == new_admin_id)
            )).scalar_one_or_none()

            if not telegram_user:
                logger.warning(f"TelegramUser для ID {new_admin_id} не найден, подписки не создаются")
            else:
                logger.debug(f"TelegramUser для ID {new_admin_id}: {telegram_user}")

            # Список групп, где админ был успешно назначен
            successful_groups = []

            # Назначить админа в группах и создать подписки
            for group in selected_groups:
                try:
                    # Проверка подписки
                    try:
                        member = await bot.get_chat_member(chat_id=group.group_id, user_id=new_admin_id)
                        if member.status in ["left", "kicked"]:
                            invite_link = await bot.create_chat_invite_link(chat_id=group.group_id)
                            await bot.send_message(
                                chat_id=new_admin_id,
                                text=f"📩 Перейдите по ссылке и нажмите 'Подписаться', чтобы стать админом в [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}): {invite_link.invite_link}",
                                parse_mode="Markdown"
                            )
                            await call.message.answer(
                                f"⚠️ Пользователь @{new_username or new_admin_id} не в группе [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}). Отправлена пригласительная ссылка.",
                                parse_mode="Markdown",
                                reply_markup=get_start_reply_keyboard()
                            )
                            logger.warning(f"Пользователь {new_admin_id} не в группе {group.group_id}, отправлена ссылка: {invite_link.invite_link}")

                            # Проверка через 2 минуты, напоминание НОВОМУ админу
                            await asyncio.sleep(120)
                            member = await bot.get_chat_member(chat_id=group.group_id, user_id=new_admin_id)
                            if member.status in ["left", "kicked"]:
                                await bot.send_message(
                                    chat_id=new_admin_id,  # Отправляем новому админу
                                    text=f"⚠️ Вы не подписались на [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}). Пожалуйста, присоединитесь, чтобы стать админом.",
                                    parse_mode="Markdown"
                                )
                                # Проверка через 3 минуты
                                await asyncio.sleep(60)
                                member = await bot.get_chat_member(chat_id=group.group_id, user_id=new_admin_id)
                                if member.status in ["left", "kicked"]:
                                    await bot.send_message(
                                        chat_id=new_admin_id,
                                        text=f"❌ Вы не добавлены админом в [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}), так как не перешли по ссылке.",
                                        parse_mode="Markdown"
                                    )
                                    await call.message.answer(
                                        f"❌ Пользователь @{new_username or new_admin_id} не подписался на [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}) и не добавлен админом.",
                                        parse_mode="Markdown",
                                        reply_markup=get_start_reply_keyboard()
                                    )
                                    continue
                    except Exception as e:
                        logger.error(f"Ошибка проверки членства {new_admin_id} в группе {group.group_id}: {e}")
                        await call.message.answer(
                            f"⚠️ Не удалось проверить членство в группе [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}): {e}",
                            parse_mode="Markdown",
                            reply_markup=get_start_reply_keyboard()
                        )
                        continue

                    # Проверка прав бота
                    admins = await bot.get_chat_administrators(chat_id=group.group_id)
                    bot_id = (await bot.get_me()).id
                    bot_is_admin = any(admin.user.id == bot_id and admin.can_promote_members for admin in admins)
                    if not bot_is_admin:
                        await call.message.answer(
                            f"⚠️ Бот не имеет прав назначать админов в группе [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}). Дайте боту права.",
                            parse_mode="Markdown",
                            reply_markup=get_start_reply_keyboard()
                        )
                        logger.warning(f"Бот не имеет прав в группе {group.group_id}")
                        continue

                    # Назначение админа
                    await bot.promote_chat_member(
                        chat_id=group.group_id,
                        user_id=new_admin_id,
                        can_manage_chat=True,
                        can_post_messages=True,
                        can_edit_messages=True,
                        can_delete_messages=True,
                        can_invite_users=True,
                        can_restrict_members=True,
                        can_pin_messages=True,
                        can_promote_members=False
                    )

                    # Создание подписки
                    if telegram_user:
                        try:
                            subscription = UserChannelSubscription(
                                telegram_user_id=telegram_user.id,  # Используем telegram_user.id
                                channel_id=group.group_id,
                                subscription_status='active',
                                subscribed_at=timezone.now()
                            )
                            db_session.add(subscription)
                            await db_session.commit()
                            logger.info(f"Создана подписка для {new_admin_id} на группу {group.group_id}")
                        except IntegrityError:
                            logger.warning(f"Подписка для {new_admin_id} на группу {group.group_id} уже существует")
                            await db_session.rollback()
                    else:
                        logger.warning(f"Не удалось создать подписку для {new_admin_id} на группу {group.group_id}: TelegramUser не найден")

                    # Добавляем группу в успешные только после успешного назначения
                    successful_groups.append(group)

                    await call.message.answer(
                        f"✅ Пользователь @{new_username or new_admin_id} назначен админом в [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}).",
                        parse_mode="Markdown",
                        reply_markup=get_start_reply_keyboard()
                    )
                    await bot.send_message(
                        chat_id=new_admin_id,
                        text=f"🎉 Вы назначены админом в [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}).",
                        parse_mode="Markdown"
                    )
                    logger.info(f"Админ {new_admin_id} назначен в группе {group.group_id}")
                except Exception as e:
                    logger.error(f"Ошибка назначения админа {new_admin_id} в группе {group.group_id}: {e}")
                    await call.message.answer(
                        f"⚠️ Не удалось назначить админа в группе [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}): {e}",
                        parse_mode="Markdown",
                        reply_markup=get_start_reply_keyboard()
                    )

            # Формирование сообщения с ТОЛЬКО успешными группами
            group_names = ", ".join(
                [f"[{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id})" for group in successful_groups]
            ) if successful_groups else "без групп"
            await call.message.answer(
                text=f"🎉 Админ добавлен: @{new_username or 'Без username'} (ID: {new_admin_id}), группы: {group_names}",
                parse_mode="Markdown",
                reply_markup=get_start_reply_keyboard()
            )

            # Удаление старых сообщений
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение {groups_message_id}: {e}")
            await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)

            # Уведомление админу
            try:
                # Получаем обновлённый объект TelegramAdmin из базы
                query = select(TelegramAdmin).where(TelegramAdmin.telegram_id == new_admin_id).options(selectinload(TelegramAdmin.groups))
                result = await db_session.execute(query)
                updated_admin = result.scalar_one_or_none()
                if updated_admin:
                    await notify_admin(bot=bot, action="added", admin=updated_admin)
                    logger.debug(f"Уведомление отправлено админу {new_admin_id}")
                else:
                    logger.error(f"Не удалось найти обновлённый объект TelegramAdmin для {new_admin_id}")
            except Exception as e:
                logger.error(f"Ошибка уведомления админа {new_admin_id}: {e}")

            logger.info(f"Админ @{new_username} (ID: {new_admin_id}) добавлен с группами: {group_names}")
            await state.clear()

        except IntegrityError:
            await call.message.answer(
                text="❌ Ошибка: пользователь уже админ.",
                parse_mode="Markdown",
                reply_markup=get_start_reply_keyboard()
            )
            await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
            logger.error(f"IntegrityError для админа {new_admin_id}")
            await state.clear()
        except Exception as e:
            await call.message.answer(
                text=f"❌ Ошибка: {e}",
                parse_mode="Markdown",
                reply_markup=get_start_reply_keyboard()
            )
            await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
            logger.error(f"Ошибка добавления админа: {e}")
            await state.clear()


@router.message(RemoveAdminStates.waiting_for_user_id, F.content_type == ContentType.TEXT)
async def process_remove_admin_user_id(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    """
    Удаляет администратора и снимает его права в группах.

    Проверяет корректность введённого Telegram ID, подтверждает статус администратора,
    снимает права в группах, удаляет запись из базы данных и отправляет уведомление
    удалённому администратору.

    Args:
        message: Сообщение с Telegram ID администратора для удаления.
        state: Контекст FSM для управления состоянием.
        db_session: Асинхронная сессия базы данных SQLAlchemy.
        bot: Экземпляр Aiogram Bot для взаимодействия с Telegram API.

    Returns:
        None
    """
    username = message.from_user.username or "None"
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        await message.reply("❌ Введите корректный числовой ID.", reply_markup=get_start_reply_keyboard())
        logger.debug(f"Некорректный ID от {username}: {message.text}")
        return

    if not await is_admin(admin_id, db_session):
        await message.reply("ℹ️ Этот пользователь не админ.", reply_markup=get_start_reply_keyboard())
        logger.info(f"Пользователь {admin_id} не админ.")
        await state.clear()
        return

    try:
        # Получаем админа и его группы до удаления
        query = select(TelegramAdmin).where(TelegramAdmin.telegram_id == admin_id).options(selectinload(TelegramAdmin.groups))
        result = await db_session.execute(query)
        admin = result.scalar_one_or_none()

        if admin:
            # Снимаем права админа в группах
            for group in admin.groups:
                try:
                    # Проверяем статус пользователя в группе
                    member = await bot.get_chat_member(chat_id=group.group_id, user_id=admin_id)
                    if member.status in ["left", "kicked"]:
                        await message.answer(
                            f"ℹ️ Пользователь @{admin.username or admin_id} не состоит в группе [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}). Права не снимаются.",
                            parse_mode="Markdown",
                            reply_markup=get_start_reply_keyboard()
                        )
                        logger.info(f"Пользователь {admin_id} не в группе {group.group_id}, права не снимаются")
                        continue

                    # Проверяем, является ли пользователь админом
                    admins = await bot.get_chat_administrators(chat_id=group.group_id)
                    is_admin_in_group = any(admin.user.id == admin_id for admin in admins)
                    if not is_admin_in_group:
                        await message.answer(
                            f"ℹ️ Пользователь @{admin.username or admin_id} не является админом в группе [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}). Права не снимаются.",
                            parse_mode="Markdown",
                            reply_markup=get_start_reply_keyboard()
                        )
                        logger.info(f"Пользователь {admin_id} не админ в группе {group.group_id}, права не снимаются")
                        continue

                    # Снимаем права админа
                    await bot.promote_chat_member(
                        chat_id=group.group_id,
                        user_id=admin_id,
                        can_manage_chat=False,
                        can_post_messages=False,
                        can_edit_messages=False,
                        can_delete_messages=False,
                        can_invite_users=False,
                        can_restrict_members=False,
                        can_pin_messages=False,
                        can_promote_members=False
                    )
                    await message.answer(
                        f"✅ Права админа сняты в группе [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}).",
                        parse_mode="Markdown",
                        reply_markup=get_start_reply_keyboard()
                    )
                    logger.info(f"Права админа {admin_id} сняты в группе {group.group_id}")
                except Exception as e:
                    logger.error(f"Ошибка снятия прав админа {admin_id} в группе {group.group_id}: {e}")
                    if "bots can't add new chat members" in str(e):
                        logger.warning(f"Бот не может добавить {admin_id} в группу {group.group_id}, возможно, пользователь не в группе")
                        await message.answer(
                            f"⚠️ Пользователь @{admin.username or admin_id} не в группе [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}). Права не снимаются.",
                            parse_mode="Markdown",
                            reply_markup=get_start_reply_keyboard()
                        )
                    else:
                        await message.answer(
                            f"⚠️ Не удалось снять права в группе [{group.username or group.group_id}](https://t.me/{group.username.lstrip('@') if group.username else group.group_id}): {e}",
                            parse_mode="Markdown",
                            reply_markup=get_start_reply_keyboard()
                        )

        # Удаляем админа
        await remove_admin(admin_id, db_session)
        await message.reply(f"🗑️ Админ с ID {admin_id} удалён.", reply_markup=get_start_reply_keyboard())
        logger.info(f"Админ {admin_id} удалён.")

        # Уведомляем удалённого админа
        if admin:
            try:
                await notify_admin(bot=bot, action="removed", admin=admin)
                logger.debug(f"Уведомление об удалении отправлено админу {admin_id}")
            except Exception as e:
                logger.error(f"Ошибка уведомления об удалении админа {admin_id}: {e}")

    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}", reply_markup=get_start_reply_keyboard())
        logger.error(f"Ошибка удаления админа {admin_id}: {e}")
    finally:
        await state.clear()





@router.message(Command("remove_admin"))
@router.callback_query(F.data == "remove_admin_button")
async def cmd_remove_admin(query: types.Message | types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Запрашивает пароль для удаления админа.
    """
    user_id = query.from_user.id
    message = query if isinstance(query, types.Message) else query.message
    username = query.from_user.username or "None"

    if not await is_admin(user_id, db_session):
        await message.reply("⛔ У вас нет прав для этой команды.", reply_markup=get_start_reply_keyboard())
        logger.warning(f"Пользователь {username} ({user_id}) попытался удалить админа без прав.")
        if isinstance(query, types.CallbackQuery):
            await query.answer()
        return

    await message.reply(
        "🔒 Введите пароль для удаления админа:\n\n_Символы видны только вам._",
        parse_mode="Markdown",
        reply_markup=ForceReply(selective=True)
    )
    logger.debug("Запрошен пароль для удаления админа")
    await state.set_state(RemoveAdminStates.waiting_for_password)
    if isinstance(query, types.CallbackQuery):
        await query.answer()


@router.message(RemoveAdminStates.waiting_for_password, F.content_type == ContentType.TEXT)
async def process_remove_admin_password(message: Message, state: FSMContext, db_session: AsyncSession):
    """
    Проверяет пароль и запрашивает Telegram ID.
    """
    username = message.from_user.username or "None"
    if message.text != ADMIN_REMOVE_SECRET_PASSWORD:
        await message.reply("❌ Неверный пароль.", reply_markup=get_start_reply_keyboard())
        logger.warning(f"Неверный пароль от {username} ({message.from_user.id}).")
        await state.clear()
        return
    await message.reply(
        "✅ Пароль верный. Введите Telegram ID админа для удаления:",
        reply_markup=ForceReply(selective=True)
    )
    logger.debug("Пароль верен. Запрошен Telegram ID")
    await state.set_state(RemoveAdminStates.waiting_for_user_id)







@router.callback_query(F.data == "list_admins_button")
async def callback_list_admins(call: CallbackQuery, db_session: AsyncSession):
    """
    Отправляет список админов в MarkdownV2 с экранированием специальных символов.
    """
    username = call.from_user.username or "None"
    logger.info(f"Пользователь {username} (ID: {call.from_user.id}) запросил список админов")

    try:
        query = select(TelegramAdmin).options(selectinload(TelegramAdmin.groups))
        result = await db_session.execute(query)
        admins = result.scalars().all()

        if not admins:
            admin_list = "👥 Нет админов."
        else:
            admin_list = "👥 **Список админов:**\n"
            for admin in admins:
                escaped_username = escape_markdown_v2(admin.username or "Нет username")
                username_link = f"[{escaped_username}](https://t.me/{admin.username.lstrip('@')})" if admin.username else "Нет username"
                group_names = ", ".join(
                    [f"[{escape_markdown_v2(g.username or str(g.group_id))}](https://t.me/{g.username.lstrip('@') if g.username else g.group_id})" for g in admin.groups]
                ) if admin.groups else "нет групп"
                line = f"• {username_link} \\(ID: {admin.telegram_id}, Groups: {group_names}\\)"
                admin_list += f"{line}\n"

        await call.message.answer(f"{admin_list}", parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
        await call.answer()
        logger.debug("Список админов отправлен")
    except Exception as e:
        logger.error(f"Ошибка в callback_list_admins: {e}")
        await call.message.answer("❌ Ошибка при отправке списка админов.", reply_markup=get_start_reply_keyboard())
        await call.answer()