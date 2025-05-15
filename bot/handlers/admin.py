from aiogram.exceptions import TelegramBadRequest
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
from bot.services.admin_service import is_admin, add_admin
from bot.states.admin_states import AddAdminStates, RemoveAdminStates, ManageAdminGroupsStates
from bot.utils.markdownV2 import escape_markdown, format_group_link
from bot.utils.notifications import notify_admin
from bot.utils.admin_utils import create_groups_keyboard, promote_admin_in_group, get_available_groups, demote_admin_in_group, \
    remove_admin_rights

# Загрузка переменных окружения
load_dotenv()

# Инициализация маршрутизатора
router = Router(name="admin_router")

# Настройка логирования
logger = logging.getLogger(__name__)

# Секретные пароли
ADMIN_SECRET_PASSWORD = os.getenv("ADMIN_SECRET_PASSWORD")
ADMIN_REMOVE_SECRET_PASSWORD = os.getenv("ADMIN_REMOVE_SECRET_PASSWORD")










@router.message(Command("add_admin"))
@router.callback_query(F.data == "add_admin_button")
async def cmd_add_admin(query: types.Message | types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Запрашивает пароль для добавления админа, если пользователь — админ.

    Args:
        query: Сообщение или callback-запрос.
        state: Контекст FSM.
        db_session: Асинхронная сессия SQLAlchemy.
    """
    user_id = query.from_user.id
    message = query if isinstance(query, types.Message) else query.message
    username = query.from_user.username or "None"

    if not await is_admin(user_id, db_session):
        await message.reply(
            escape_markdown("⛔ У вас нет прав для этой команды."),
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )
        logger.warning(f"Пользователь {username} ({user_id}) попытался добавить админа без прав.")
        if isinstance(query, types.CallbackQuery):
            await query.answer()
        return

    await message.reply(
        f"{escape_markdown('🔒 Введите секретный пароль для добавления админа:')}\n\n{escape_markdown('_Символы видны только вам._')}",
        parse_mode="MarkdownV2",
        reply_markup=ForceReply(selective=True)
    )

    logger.debug("Запрошен пароль для добавления админа")
    await state.set_state(AddAdminStates.waiting_for_password)
    if isinstance(query, types.CallbackQuery):
        await query.answer()






@router.message(AddAdminStates.waiting_for_password, F.content_type == ContentType.TEXT)
async def process_add_admin_password(message: Message, state: FSMContext, db_session: AsyncSession):
    username = message.from_user.username or "None"
    try:
        if message.text.strip() != ADMIN_SECRET_PASSWORD:
            await message.reply(
                escape_markdown("❌ Неверный пароль."),
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
            logger.warning(f"Неверный пароль от {username} ({message.from_user.id}).")
            await state.clear()
            return
        await message.reply(
            escape_markdown("✅ Пароль верный. Введите Telegram ID нового админа: 🔢"),
            parse_mode="MarkdownV2",
            reply_markup=ForceReply(selective=True)
        )
        logger.debug("Пароль верен. Запрошен Telegram ID")
        await state.set_state(AddAdminStates.waiting_for_user_id)
    except Exception as e:
        logger.error(f"Ошибка в process_add_admin_password: {e}")
        await message.reply(
            escape_markdown("❌ Ошибка. Попробуйте снова."),
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )
        await state.clear()






@router.message(AddAdminStates.waiting_for_user_id, F.content_type == ContentType.TEXT)
async def process_add_admin_user_id(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    """
    Проверяет Telegram ID и запрашивает группы.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.
        db_session: Асинхронная сессия SQLAlchemy.
        bot: Экземпляр Aiogram Bot.
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
    groups = await get_available_groups(db_session, new_admin_id)

    if not groups:
        await message.reply(
            "🚫 Нет доступных групп, админ будет создан без привязки.",
            reply_markup=get_start_reply_keyboard()
        )
        logger.debug("Нет доступных групп")
        await state.update_data(selected_groups=[])
        await confirm_admin_creation(message, state, bot, db_session, message.message_id)
        return

    keyboard = await create_groups_keyboard(groups, "group_", include_select_all=False)
    groups_message = await message.reply("📋 Выберите группы/каналы для админа:", reply_markup=keyboard)
    await state.update_data(groups_message_id=groups_message.message_id)
    logger.debug("Показаны группы для выбора")
    await state.set_state(AddAdminStates.waiting_for_groups)







@router.callback_query(AddAdminStates.waiting_for_groups,
                       F.data.startswith("group_") | F.data.in_(["no_groups", "confirm_groups", "cancel"]))
async def process_add_admin_groups(call: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot):
    data = await state.get_data()
    selected_groups = data.get("selected_groups", [])
    groups_message_id = data.get("groups_message_id")

    if call.data.startswith("group_"):
        group_id = int(call.data.replace("group_", ""))
        query = select(TelegramGroup).where(TelegramGroup.group_id == group_id)
        result = await db_session.execute(query)
        group = result.scalar_one_or_none()
        if group and group not in selected_groups:
            selected_groups.append(group)
            await state.update_data(selected_groups=selected_groups)
            await call.answer(escape_markdown(f"Группа {group.username or group.group_id} добавлена"))
        else:
            await call.answer(escape_markdown("Группа уже выбрана или не найдена"))
        return

    if call.data == "no_groups":
        await state.update_data(selected_groups=[])
        await call.answer(escape_markdown("Выбрано: без групп"))

    if call.data == "confirm_groups":
        await confirm_admin_creation(call.message, state, bot, db_session, groups_message_id)
    elif call.data == "cancel":
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщения: {e}")
        await call.message.answer(
            escape_markdown("❌ Операция отменена."),
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )
        await state.clear()
    await call.answer()




async def confirm_admin_creation(message: Message, state: FSMContext, bot: Bot, db_session: AsyncSession,
                                groups_message_id: int) -> None:
    """
    Показывает подтверждение создания нового администратора и отправляет сообщение с деталями.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM для хранения данных.
        bot: Экземпляр Aiogram Bot.
        db_session: Асинхронная сессия SQLAlchemy.
        groups_message_id: ID сообщения с выбором групп.

    Raises:
        TelegramBadRequest: Если не удалось отправить сообщение.
        Exception: Для других ошибок при обработке.
    """
    data = await state.get_data()
    new_admin_id = data.get("new_admin_id")
    new_username = data.get("new_username")
    new_language = data.get("new_language")
    selected_groups = data.get("selected_groups", [])

    # Формируем ссылки на группы
    group_names = ", ".join([format_group_link(group) for group in selected_groups]) if selected_groups else escape_markdown("без групп")

    # Экранируем username и добавляем @ в тексте
    escaped_username = escape_markdown(new_username or "Без username")

    text = (
        escape_markdown("Создать админа? 🤔\n") +
        escape_markdown(f"ID: {new_admin_id}\n") +
        escape_markdown("Username: @") + f"[{escaped_username}](https://t.me/{new_username if new_username else new_admin_id})" +
        escape_markdown("\nГруппы: ") + group_names
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить ✅", callback_data="confirm_admin")],
        [InlineKeyboardButton(text="Отмена 🚫", callback_data="cancel")]
    ])

    confirmation_message = await message.reply(text, parse_mode="MarkdownV2", reply_markup=keyboard)
    await state.update_data(groups_message_id=groups_message_id,
                            confirmation_message_id=confirmation_message.message_id)
    await state.set_state(AddAdminStates.waiting_for_confirmation)




@router.callback_query(AddAdminStates.waiting_for_confirmation, F.data.in_(["confirm_admin", "cancel"]))
async def process_admin_confirmation(call: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обрабатывает подтверждение или отмену добавления нового администратора.
    """
    data = await state.get_data()
    new_admin_id = data.get("new_admin_id")
    new_username = data.get("new_username")
    new_language = data.get("new_language")
    selected_groups = data.get("selected_groups", [])
    groups_message_id = data.get("groups_message_id")
    confirmation_message_id = data.get("confirmation_message_id")

    logger.debug(f"process_admin_confirmation: callback_data={call.data}, new_admin_id={new_admin_id}, "
                 f"new_username={new_username}, selected_groups={[g.group_id for g in selected_groups]}, "
                 f"groups_message_id={groups_message_id}, confirmation_message_id={confirmation_message_id}, "
                 f"state={await state.get_state()}")

    await call.answer()

    if call.data == "cancel":
        try:
            if groups_message_id:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
                logger.debug(f"Сообщение {groups_message_id} успешно удалено (отмена)")
            if confirmation_message_id:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                logger.debug(f"Сообщение {confirmation_message_id} успешно удалено (отмена)")
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось удалить сообщения (groups_message_id={groups_message_id}, "
                          f"confirmation_message_id={confirmation_message_id}): {e}")

        message_text = escape_markdown("❌ Добавление админа отменено.")
        logger.debug(f"Отправка сообщения: {message_text}")
        await call.message.answer(
            text=message_text,
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )
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
            logger.info(
                f"Админ с ID {new_admin_id} (@{new_username}) добавлен с группами: {[g.username for g in selected_groups]}")

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

                            # Формируем сообщение с приглашением
                            invite_text = (
                                f"📩 Перейдите по ссылке и нажмите 'Подписаться', чтобы стать админом в " +
                                format_group_link(group) + f": {escape_markdown(invite_link.invite_link)}"
                            )
                            logger.debug(f"Отправка приглашения админу {new_admin_id}: {invite_text}")
                            await bot.send_message(
                                chat_id=new_admin_id,
                                text=invite_text,
                                parse_mode="MarkdownV2"
                            )

                            warning_text = (
                                f"⚠️ Пользователь @{escape_markdown(new_username or str(new_admin_id))} " +
                                f"не в группе {format_group_link(group)}. " +
                                f"Отправлена пригласительная ссылка."
                            )
                            logger.debug(f"Отправка предупреждения: {warning_text}")
                            await call.message.answer(
                                warning_text,
                                parse_mode="MarkdownV2",
                                reply_markup=get_start_reply_keyboard()
                            )

                            logger.warning(
                                f"Пользователь {new_admin_id} не в группе {group.group_id}, отправлена ссылка: {invite_link.invite_link}")

                            # Проверка через 2 минуты
                            await asyncio.sleep(120)
                            member = await bot.get_chat_member(chat_id=group.group_id, user_id=new_admin_id)
                            if member.status in ["left", "kicked"]:
                                no_subscription_text = (
                                    f"⚠️ Вы не подписались на {format_group_link(group)}. " +
                                    f"Пожалуйста, присоединитесь, чтобы стать админом."
                                )
                                logger.debug(f"Отправка предупреждения админу {new_admin_id}: {no_subscription_text}")
                                await bot.send_message(
                                    chat_id=new_admin_id,
                                    text=no_subscription_text,
                                    parse_mode="MarkdownV2"
                                )

                                # Проверка через 3 минуты
                                await asyncio.sleep(60)
                                member = await bot.get_chat_member(chat_id=group.group_id, user_id=new_admin_id)
                                if member.status in ["left", "kicked"]:
                                    final_warning_text = (
                                        f"❌ Вы не добавлены админом в {format_group_link(group)}, " +
                                        f"так как не перешли по ссылке."
                                    )
                                    logger.debug(f"Отправка финального предупреждения админу {new_admin_id}: {final_warning_text}")
                                    await bot.send_message(
                                        chat_id=new_admin_id,
                                        text=final_warning_text,
                                        parse_mode="MarkdownV2"
                                    )

                                    admin_notice_text = (
                                        f"❌ Пользователь @{escape_markdown(new_username or str(new_admin_id))} " +
                                        f"не подписался на {format_group_link(group)} и не добавлен админом."
                                    )
                                    logger.debug(f"Отправка уведомления: {admin_notice_text}")
                                    await call.message.answer(
                                        admin_notice_text,
                                        parse_mode="MarkdownV2",
                                        reply_markup=get_start_reply_keyboard()
                                    )
                                    continue
                    except Exception as e:
                        logger.error(f"Ошибка проверки членства {new_admin_id} в группе {group.group_id}: {e}")
                        error_text = (
                            f"⚠️ Не удалось проверить членство в группе {format_group_link(group)}: " +
                            f"{escape_markdown(str(e))}"
                        )
                        logger.debug(f"Отправка сообщения об ошибке: {error_text}")
                        await call.message.answer(
                            error_text,
                            parse_mode="MarkdownV2",
                            reply_markup=get_start_reply_keyboard()
                        )
                        continue

                    # Проверка прав бота
                    admins = await bot.get_chat_administrators(chat_id=group.group_id)
                    bot_id = (await bot.get_me()).id
                    bot_is_admin = any(admin.user.id == bot_id and admin.can_promote_members for admin in admins)
                    if not bot_is_admin:
                        bot_rights_text = (
                            f"⚠️ Бот не имеет прав назначать админов в группе {format_group_link(group)}. " +
                            f"Дайте боту права."
                        )
                        logger.debug(f"Отправка сообщения о правах бота: {bot_rights_text}")
                        await call.message.answer(
                            bot_rights_text,
                            parse_mode="MarkdownV2",
                            reply_markup=get_start_reply_keyboard()
                        )
                        logger.warning(f"Бот не имеет прав в группе {group.group_id}")
                        continue

                    # Назначение админа
                    if await promote_admin_in_group(bot, group.group_id, new_admin_id):
                        # Создание подписки
                        if telegram_user:
                            try:
                                # Проверяем, существует ли подписка
                                existing_subscription = (await db_session.execute(
                                    select(UserChannelSubscription).where(
                                        UserChannelSubscription.telegram_user_id == telegram_user.id,
                                        UserChannelSubscription.channel_id == group.group_id
                                    )
                                )).scalar_one_or_none()

                                if existing_subscription:
                                    # Обновляем существующую подписку
                                    existing_subscription.subscription_status = 'active'
                                    existing_subscription.subscribed_at = timezone.now()
                                    existing_subscription.unsubscribed_at = None
                                    await db_session.commit()
                                    logger.info(f"Обновлена подписка для {new_admin_id} на группу {group.group_id}")
                                else:
                                    # Создаем новую подписку
                                    subscription = UserChannelSubscription(
                                        telegram_user_id=telegram_user.id,
                                        channel_id=group.group_id,
                                        subscription_status='active',
                                        subscribed_at=timezone.now()
                                    )
                                    db_session.add(subscription)
                                    await db_session.commit()
                                    logger.info(f"Создана подписка для {new_admin_id} на группу {group.group_id}")
                            except Exception as e:
                                logger.error(f"Ошибка создания/обновления подписки для {new_admin_id} на группу {group.group_id}: {e}")
                                await db_session.rollback()
                        else:
                            logger.warning(
                                f"Не удалось создать подписку для {new_admin_id} на группу {group.group_id}: TelegramUser не найден")

                        successful_groups.append(group)

                        success_text = (
                            f"✅ Пользователь @{escape_markdown(new_username or str(new_admin_id))} " +
                            f"назначен админом в {format_group_link(group)}."
                        )
                        logger.debug(f"Отправка сообщения об успехе: {success_text}")
                        await call.message.answer(
                            success_text,
                            parse_mode="MarkdownV2",
                            reply_markup=get_start_reply_keyboard()
                        )

                        admin_notification = (
                            f"🎉 Вы назначены админом в {format_group_link(group)}."
                        )
                        logger.debug(f"Отправка уведомления админу {new_admin_id}: {admin_notification}")
                        await bot.send_message(
                            chat_id=new_admin_id,
                            text=admin_notification,
                            parse_mode="MarkdownV2"
                        )

                        logger.info(f"Админ {new_admin_id} назначен в группе {group.group_id}")
                except Exception as e:
                    logger.error(f"Ошибка назначения админа {new_admin_id} в группе {group.group_id}: {e}")
                    admin_error_text = (
                        f"⚠️ Не удалось назначить админа в группе {format_group_link(group)}: " +
                        f"{escape_markdown(str(e))}"
                    )
                    logger.debug(f"Отправка сообщения об ошибке: {admin_error_text}")
                    await call.message.answer(
                        admin_error_text,
                        parse_mode="MarkdownV2",
                        reply_markup=get_start_reply_keyboard()
                    )

            # Формирование сообщения с успешными группами
            group_names = ", ".join(
                [format_group_link(group) for group in successful_groups]) if successful_groups else escape_markdown("без групп")
            summary_text = (
                f"🎉 Админ добавлен: @{escape_markdown(new_username or 'Без username')} " +
                f"\\(ID: {new_admin_id}\\), группы: {group_names}"
            )
            logger.debug(f"Отправка итогового сообщения: {summary_text}")
            await call.message.answer(
                text=summary_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )

            # Удаление старых сообщений
            try:
                if groups_message_id:
                    await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
                    logger.debug(f"Сообщение {groups_message_id} успешно удалено")
                if confirmation_message_id:
                    await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                    logger.debug(f"Сообщение {confirmation_message_id} успешно удалено")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить сообщения (groups_message_id={groups_message_id}, "
                              f"confirmation_message_id={confirmation_message_id}): {e}")

            # Уведомление админу
            try:
                query = select(TelegramAdmin).where(TelegramAdmin.telegram_id == new_admin_id).options(
                    selectinload(TelegramAdmin.groups))
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
            message_text = escape_markdown("❌ Ошибка: пользователь уже админ.")
            logger.debug(f"Отправка сообщения: {message_text}")
            await call.message.answer(
                text=message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
            try:
                if groups_message_id:
                    await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
                    logger.debug(f"Сообщение {groups_message_id} успешно удалено (IntegrityError)")
                if confirmation_message_id:
                    await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                    logger.debug(f"Сообщение {confirmation_message_id} успешно удалено (IntegrityError)")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить сообщения (groups_message_id={groups_message_id}, "
                              f"confirmation_message_id={confirmation_message_id}): {e}")
            logger.error(f"IntegrityError для админа {new_admin_id}")
            await state.clear()
        except Exception as e:
            message_text = f"❌ Ошибка: {escape_markdown(str(e))}"
            logger.debug(f"Отправка сообщения: {message_text}")
            await call.message.answer(
                text=message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
            try:
                if groups_message_id:
                    await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
                    logger.debug(f"Сообщение {groups_message_id} успешно удалено (ошибка)")
                if confirmation_message_id:
                    await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                    logger.debug(f"Сообщение {confirmation_message_id} успешно удалено (ошибка)")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить сообщения (groups_message_id={groups_message_id}, "
                              f"confirmation_message_id={confirmation_message_id}): {e}")
            logger.error(f"Ошибка добавления админа: {e}")
            await state.clear()





@router.message(Command("remove_admin"))
@router.callback_query(F.data == "remove_admin_button")
async def cmd_remove_admin(query: types.Message | types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Запрашивает пароль для удаления админа.

    Args:
        query: Сообщение или callback-запрос.
        state: Контекст FSM.
        db_session: Асинхронная сессия SQLAlchemy.
    """
    user_id = query.from_user.id
    message = query if isinstance(query, types.Message) else query.message
    username = query.from_user.username or "None"

    if not await is_admin(user_id, db_session):
        await message.reply(
            escape_markdown("⛔ У вас нет прав для этой команды."),
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )
        logger.warning(f"Пользователь {username} ({user_id}) попытался удалить админа без прав.")
        if isinstance(query, types.CallbackQuery):
            await query.answer()
        return

    await message.reply(
        f"{escape_markdown('🔒 Введите пароль для удаления админа:')}\n\n{escape_markdown('_Символы видны только вам._')}",
        parse_mode="MarkdownV2",
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

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.
        db_session: Асинхронная сессия SQLAlchemy.
    """
    username = message.from_user.username or "None"
    if message.text != ADMIN_REMOVE_SECRET_PASSWORD:
        await message.reply(
            escape_markdown("❌ Неверный пароль."),
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )
        logger.warning(f"Неверный пароль от {username} ({message.from_user.id}).")
        await state.clear()
        return
    await message.reply(
        "✅ Пароль верный. Введите Telegram ID админа для удаления:",
        reply_markup=ForceReply(selective=True)
    )
    logger.debug("Пароль верен. Запрошен Telegram ID")
    await state.set_state(RemoveAdminStates.waiting_for_user_id)




@router.message(RemoveAdminStates.waiting_for_user_id, F.content_type == ContentType.TEXT)
async def process_remove_admin_user_id(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    username = message.from_user.username or "None"
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        await message.reply(
            escape_markdown("❌ Введите корректный числовой ID."),
            parse_mode="MarkdownV2",
            reply_markup=ForceReply(selective=True)
        )
        logger.debug(f"Некорректный ID от {username}: {message.text}")
        return

    if not await is_admin(admin_id, db_session):
        await message.reply(
            escape_markdown("ℹ️ Этот пользователь не админ."),
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )
        logger.info(f"Пользователь {admin_id} не админ.")
        await state.clear()
        return

    # Получаем админа и его группы
    query = select(TelegramAdmin).where(TelegramAdmin.telegram_id == admin_id).options(selectinload(TelegramAdmin.groups))
    result = await db_session.execute(query)
    admin = result.scalar_one_or_none()

    # Сохраняем данные админа
    await state.update_data(admin_id=admin_id, admin_username=admin.username, admin_groups=admin.groups)

    if not admin.groups:
        text = f"{escape_markdown('Удалить админа')} @{escape_markdown(admin.username or str(admin_id))}? {escape_markdown('Нет связанных групп.')}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить ✅", callback_data="confirm_remove_admin_groups")],
            [InlineKeyboardButton(text="Отмена 🚫", callback_data="cancel")]
        ])
        confirmation_message = await message.reply(text, parse_mode="MarkdownV2", reply_markup=keyboard)
        await state.update_data(confirmation_message_id=confirmation_message.message_id)
        await state.set_state(RemoveAdminStates.waiting_for_confirmation)
        logger.debug("Состояние установлено: RemoveAdminStates.waiting_for_confirmation")
        return

    # Создаём клавиатуру с группами
    keyboard = await create_groups_keyboard(admin.groups, "remove_group_", include_select_all=True)
    groups_message = await message.reply(
        f"{escape_markdown('📋 Выберите группы, из которых снять права для')} @{escape_markdown(admin.username or str(admin_id))}:",
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )
    await state.update_data(groups_message_id=groups_message.message_id)
    logger.debug(f"Показаны группы для админа {admin_id}")
    await state.set_state(RemoveAdminStates.waiting_for_groups)






@router.callback_query(RemoveAdminStates.waiting_for_groups,
                       F.data.startswith("remove_group_") | F.data.in_(["confirm_groups", "cancel"]))
async def process_remove_admin_groups(call: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot):
    logger.debug("Функция process_remove_admin_groups вызвана, callback_data=%s, state=%s",
                 call.data, await state.get_state())

    data = await state.get_data()
    admin_id = data.get("admin_id")
    admin_username = data.get("admin_username")
    admin_groups = data.get("admin_groups", [])
    selected_groups = data.get("selected_groups", [])
    groups_message_id = data.get("groups_message_id")

    if call.data.startswith("remove_group_"):
        if call.data == "remove_group_all":
            selected_groups = admin_groups
            await call.answer("Выбраны все группы")
        else:
            group_id = int(call.data.replace("remove_group_", ""))
            query = select(TelegramGroup).where(TelegramGroup.group_id == group_id)
            result = await db_session.execute(query)
            group = result.scalar_one_or_none()
            if group and group not in selected_groups:
                selected_groups.append(group)
                await call.answer(f"Группа {group.username or group.group_id} выбрана")
            else:
                await call.answer("Группа уже выбрана или не найдена")
        await state.update_data(selected_groups=selected_groups)
        return

    await call.answer()

    if call.data == "cancel":
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
            logger.debug(f"Сообщение {groups_message_id} удалено (отмена)")
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение {groups_message_id}: {e}")
        message_text = escape_markdown("❌ Операция отменена.")
        logger.debug(f"Отправка сообщения: {message_text}")
        await call.message.answer(message_text, parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
        await state.clear()
        return

    if call.data == "confirm_groups":
        if not selected_groups:
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
                logger.debug(f"Сообщение {groups_message_id} удалено (нет групп)")
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение {groups_message_id}: {e}")
            message_text = escape_markdown("ℹ️ Не выбрано ни одной группы.")
            logger.debug(f"Отправка сообщения: {message_text}")
            await call.message.answer(message_text, parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
            await state.clear()
            return

        # Подтверждение выбора
        group_names = ", ".join([format_group_link(group) for group in selected_groups])
        text = (
            f"{escape_markdown('Снять права и удалить админа')} @{escape_markdown(admin_username or str(admin_id))}?\n"
            f"{escape_markdown('Группы:')} {group_names}"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить ✅", callback_data="confirm_remove_admin_groups")],
            [InlineKeyboardButton(text="Отмена 🚫", callback_data="cancel")]
        ])
        try:
            confirmation_message = await call.message.reply(text, parse_mode="MarkdownV2", reply_markup=keyboard)
            await state.update_data(confirmation_message_id=confirmation_message.message_id)
        except TelegramBadRequest as e:
            logger.error(f"Ошибка отправки сообщения с подтверждением: {e}")
            await call.message.answer(
                escape_markdown("❌ Ошибка отправки сообщения. Попробуйте снова."),
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
            await state.clear()
            return
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
            logger.debug(f"Сообщение {groups_message_id} удалено (перед подтверждением)")
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение {groups_message_id}: {e}")
        await state.set_state(RemoveAdminStates.waiting_for_confirmation)
        logger.info(f"Состояние установлено: RemoveAdminStates.waiting_for_confirmation, confirmation_message_id={confirmation_message.message_id}")






@router.callback_query(RemoveAdminStates.waiting_for_confirmation,
                       F.data.in_(["confirm_remove_admin_groups", "cancel"]))
async def confirm_remove_admin_groups(call: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot):
    """
    Подтверждает или отменяет удаление админа и снятие его прав в группах.

    Args:
        call: Callback-запрос от кнопки.
        state: Контекст FSM.
        db_session: Асинхронная сессия SQLAlchemy.
        bot: Экземпляр Aiogram Bot.
    """
    logger.info(f"Обработка callback: callback_data={call.data}, state={await state.get_state()}, chat_id={call.message.chat.id}")

    data = await state.get_data()
    admin_id = data.get("admin_id")
    admin_username = data.get("admin_username")
    selected_groups = data.get("selected_groups", [])
    confirmation_message_id = data.get("confirmation_message_id")

    logger.debug(f"confirm_remove_admin_groups: admin_id={admin_id}, admin_username={admin_username}, "
                 f"selected_groups={[group.group_id for group in selected_groups]}, "
                 f"confirmation_message_id={confirmation_message_id}")

    await call.answer()

    if call.data == "cancel":
        if confirmation_message_id:
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                logger.debug(f"Сообщение {confirmation_message_id} удалено (отмена)")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")
        message_text = escape_markdown("❌ Операция отменена.")
        await call.message.answer(message_text, parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
        await state.clear()
        logger.info(f"Операция отменена для админа {admin_id}")
        return

    try:
        query = select(TelegramAdmin).where(TelegramAdmin.telegram_id == admin_id).options(selectinload(TelegramAdmin.groups))
        result = await db_session.execute(query)
        admin = result.scalar_one_or_none()

        if not admin:
            if confirmation_message_id:
                try:
                    await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                    logger.debug(f"Сообщение {confirmation_message_id} удалено (админ не найден)")
                except TelegramBadRequest as e:
                    logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")
            message_text = escape_markdown("❌ Админ не найден.")
            await call.message.answer(message_text, parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
            await state.clear()
            logger.info(f"Админ {admin_id} не найден")
            return

        successful_groups = await remove_admin_rights(bot, db_session, admin, selected_groups)

        await db_session.delete(admin)
        await db_session.commit()
        logger.info(f"Админ {admin_id} удалён из TelegramAdmin")

        group_names = ", ".join([format_group_link(group) for group in successful_groups]) if successful_groups else escape_markdown("без групп")
        escaped_username = escape_markdown(admin_username or str(admin_id))
        username_link = f"[{escaped_username}](https://t.me/{admin_username if admin_username else admin_id})"
        message_text = (
            escape_markdown(f"✅ Админ {username_link} удалён. Права сняты в группах: ") + group_names
        )
        try:
            await call.message.answer(
                message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
            logger.debug(f"Итоговое сообщение отправлено: {message_text}")
        except TelegramBadRequest as e:
            logger.error(f"Ошибка отправки итогового сообщения: {e}")
            message_text = escape_markdown("❌ Ошибка отправки сообщения об удалении админа.")
            await call.message.answer(
                message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )

        try:
            message_text = (
                escape_markdown(f"ℹ️ Вы больше не админ. Права сняты в группах: ") + group_names
            )
            await bot.send_message(
                chat_id=admin_id,
                text=message_text,
                parse_mode="MarkdownV2"
            )
            logger.debug(f"Уведомление отправлено админу {admin_id}")
        except Exception as e:
            logger.error(f"Ошибка уведомления админа {admin_id}: {e}")

        if confirmation_message_id:
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                logger.debug(f"Сообщение {confirmation_message_id} удалено")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка обработки удаления админа {admin_id}: {e}")
        message_text = f"{escape_markdown('❌ Ошибка:')} {escape_markdown(str(e))}"
        await call.message.answer(message_text, parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
        if confirmation_message_id:
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                logger.debug(f"Сообщение {confirmation_message_id} удалено (ошибка)")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")
        await state.clear()






@router.message(Command("manage_admin_groups"))
@router.callback_query(F.data == "manage_admin_groups")
async def cmd_manage_admin_groups(query: types.Message | types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Запрашивает Telegram ID админа для управления его группами.

    Args:
        query: Сообщение или callback-запрос.
        state: Контекст FSM.
        db_session: Асинхронная сессия SQLAlchemy.
    """
    user_id = query.from_user.id
    message = query if isinstance(query, types.Message) else query.message
    username = query.from_user.username or "None"

    if not await is_admin(user_id, db_session):
        await message.reply(
            escape_markdown("⛔ У вас нет прав для этой команды."),
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )
        logger.warning(f"Пользователь {username} ({user_id}) попытался управлять группами админа без прав.")
        if isinstance(query, types.CallbackQuery):
            await query.answer()
        return

    await message.reply(
        "🔢 Введите Telegram ID админа для управления группами:",
        reply_markup=ForceReply(selective=True)
    )
    logger.debug(f"Запрошен Telegram ID для управления группами от {username} ({user_id})")
    await state.set_state(ManageAdminGroupsStates.waiting_for_admin_id)
    if isinstance(query, types.CallbackQuery):
        await query.answer()




@router.message(ManageAdminGroupsStates.waiting_for_admin_id, F.content_type == ContentType.TEXT)
async def process_manage_admin_id(message: Message, state: FSMContext, db_session: AsyncSession):
    """
    Проверяет Telegram ID и показывает группы админа.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.
        db_session: Асинхронная сессия SQLAlchemy.
    """
    username = message.from_user.username or "None"
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        message_text = "❌ Введите корректный числовой ID\\."
        logger.debug(f"Некорректный ID от {username}: {message.text}")
        await message.reply(message_text, parse_mode="MarkdownV2", reply_markup=ForceReply(selective=True))
        return

    if not await is_admin(admin_id, db_session):
        message_text = "ℹ️ Этот пользователь не админ\\."
        logger.info(f"Пользователь {admin_id} не админ.")
        await message.reply(message_text, parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
        await state.clear()
        return

    # Получаем админа и его группы
    query = select(TelegramAdmin).where(TelegramAdmin.telegram_id == admin_id).options(selectinload(TelegramAdmin.groups))
    result = await db_session.execute(query)
    admin = result.scalar_one_or_none()

    if not admin:
        message_text = "❌ Админ не найден\\."
        logger.error(f"Админ {admin_id} не найден.")
        await message.reply(message_text, parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
        await state.clear()
        return

    await state.update_data(admin_id=admin_id, admin_username=admin.username, admin_groups=admin.groups)

    # Показываем группы
    if not admin.groups:
        message_text = f"ℹ️ У админа @{escape_markdown(admin.username or str(admin_id))} нет групп\\."
        logger.debug(f"Отправка сообщения: {message_text}")
        try:
            await message.reply(
                message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось отправить ответное сообщение: {e}")
            await message.answer(
                message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Добавить группы ➕", callback_data="add_groups")],
            [InlineKeyboardButton(text="Готово ✅", callback_data="finish")]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for group in admin.groups:
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(
                    text=f"@{escape_markdown(group.username or str(group.group_id))}",
                    callback_data=f"view_group:{group.group_id}"
                ),
                InlineKeyboardButton(
                    text="Снять права 🗑️",
                    callback_data=f"remove_group:{group.group_id}"
                )]
            )
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="Снять все права 🗑️", callback_data="remove_all_groups")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="Добавить группы ➕", callback_data="add_groups")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="Готово ✅", callback_data="finish")])

    message_text = f"📋 Группы админа @{escape_markdown(admin.username or str(admin_id))}\\:"
    logger.debug(f"Отправка сообщения: {message_text}")
    try:
        groups_message = await message.reply(
            message_text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        logger.warning(f"Не удалось отправить ответное сообщение: {e}")
        groups_message = await message.answer(
            message_text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )
    await state.update_data(groups_message_id=groups_message.message_id)
    logger.debug(f"Показаны группы для админа {admin_id}")
    await state.set_state(ManageAdminGroupsStates.waiting_for_group_action)





@router.callback_query(ManageAdminGroupsStates.waiting_for_group_action,
                      F.data.startswith(("view_group:", "remove_group:", "add_groups", "remove_all_groups", "finish")))
async def process_manage_groups_action(call: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot) -> None:
    """
    Обрабатывает действия с группами администратора (просмотр, удаление, добавление).

    Args:
        call: CallbackQuery от inline-кнопки.
        state: Контекст FSM для хранения данных.
        db_session: Асинхронная сессия SQLAlchemy.
        bot: Экземпляр Aiogram Bot.

    Raises:
        TelegramBadRequest: Если не удалось отправить или удалить сообщение.
        Exception: Для других ошибок при обработке.
    """
    data = await state.get_data()
    admin_id = data.get("admin_id")
    admin_username = data.get("admin_username")
    admin_groups = data.get("admin_groups", [])
    groups_message_id = data.get("groups_message_id")

    await call.answer()

    if call.data == "finish":
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
            logger.debug(f"Сообщение {groups_message_id} успешно удалено (завершение)")
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось удалить сообщение {groups_message_id}: {e}")
        message_text = escape_markdown("✅ Управление группами завершено.")
        await call.message.answer(message_text, parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
        await state.clear()
        return

    if call.data.startswith("view_group:"):
        group_id = int(call.data.replace("view_group:", ""))
        query = select(TelegramGroup).where(TelegramGroup.group_id == group_id)
        result = await db_session.execute(query)
        group = result.scalar_one_or_none()
        if group:
            message_text = (
                escape_markdown("ℹ️ Группа: ") + format_group_link(group) + "\n" +
                escape_markdown(f"Название: {group.group_name}\n") +
                escape_markdown(f"Тип: {group.location_type}")
            )
            await call.message.answer(
                message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
        else:
            message_text = escape_markdown("❌ Группа не найдена.")
            await call.message.answer(
                message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
        return

    if call.data.startswith("remove_group:") or call.data == "remove_all_groups":
        selected_groups = []
        if call.data == "remove_all_groups":
            selected_groups = admin_groups
        else:
            group_id = int(call.data.replace("remove_group:", ""))
            query = select(TelegramGroup).where(TelegramGroup.group_id == group_id)
            result = await db_session.execute(query)
            group = result.scalar_one_or_none()
            if group:
                selected_groups.append(group)

        if not selected_groups:
            message_text = escape_markdown("ℹ️ Не выбрано ни одной группы.")
            await call.message.answer(
                message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
            return

        # Подтверждение удаления
        group_names = ", ".join([format_group_link(group) for group in selected_groups])
        escaped_username = escape_markdown(admin_username or str(admin_id))
        text = (
            escape_markdown(f"Снять права админа @") +
            f"[{escaped_username}](https://t.me/{admin_username if admin_username else admin_id})" +
            escape_markdown(" в группах?\nГруппы: ") + group_names
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить ✅", callback_data="confirm_remove_groups")],
            [InlineKeyboardButton(text="Отмена 🚫", callback_data="cancel")]
        ])
        confirmation_message = await call.message.reply(text, parse_mode="MarkdownV2", reply_markup=keyboard)
        await state.update_data(selected_groups=selected_groups, confirmation_message_id=confirmation_message.message_id)
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
            logger.debug(f"Сообщение {groups_message_id} успешно удалено (перед подтверждением)")
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось удалить сообщение {groups_message_id}: {e}")
        await state.set_state(ManageAdminGroupsStates.waiting_for_groups_to_remove)
        return

    if call.data == "add_groups":
        # Получаем доступные группы
        available_groups = await get_available_groups(db_session, admin_id)
        if not available_groups:
            message_text = escape_markdown("ℹ️ Нет доступных групп для добавления.")
            await call.message.answer(
                message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
                logger.debug(f"Сообщение {groups_message_id} успешно удалено (нет групп)")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить сообщение {groups_message_id}: {e}")
            await state.set_state(ManageAdminGroupsStates.waiting_for_group_action)
            return

        keyboard = await create_groups_keyboard(available_groups, "add_group_", include_select_all=False)
        escaped_username = escape_markdown(admin_username or str(admin_id))
        message_text = (
            escape_markdown(f"📋 Выберите группы для добавления админу @") +
            f"[{escaped_username}](https://t.me/{admin_username if admin_username else admin_id})" +
            escape_markdown(":")
        )
        groups_message = await call.message.reply(
            message_text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )
        await state.update_data(groups_message_id=groups_message.message_id)
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
            logger.debug(f"Сообщение {groups_message_id} успешно удалено (перед выбором групп)")
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось удалить сообщение {groups_message_id}: {e}")
        await state.set_state(ManageAdminGroupsStates.waiting_for_groups_to_add)






@router.callback_query(ManageAdminGroupsStates.waiting_for_groups_to_remove,
                      F.data.in_(["confirm_remove_groups", "cancel"]))
async def confirm_remove_groups(call: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot) -> None:
    """
    Подтверждает или отменяет снятие прав администратора в выбранных группах.

    Args:
        call: CallbackQuery от inline-кнопки.
        state: Контекст FSM для хранения данных.
        db_session: Асинхронная сессия SQLAlchemy.
        bot: Экземпляр Aiogram Bot.

    Raises:
        TelegramBadRequest: Если не удалось отправить или удалить сообщение.
        Exception: Для других ошибок при обработке.
    """
    data = await state.get_data()
    admin_id = data.get("admin_id")
    admin_username = data.get("admin_username")
    selected_groups = data.get("selected_groups", [])
    confirmation_message_id = data.get("confirmation_message_id")

    logger.debug(f"confirm_remove_groups: callback_data={call.data}, admin_id={admin_id}, admin_username={admin_username}, "
                 f"selected_groups={[group.group_id for group in selected_groups]}, "
                 f"confirmation_message_id={confirmation_message_id}")

    await call.answer()

    if call.data == "cancel":
        if confirmation_message_id:
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                logger.debug(f"Сообщение {confirmation_message_id} успешно удалено (отмена)")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")
        message_text = escape_markdown("❌ Операция отменена.")
        logger.debug(f"Отправка сообщения об отмене: {message_text}")
        await call.message.answer(
            message_text,
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )
        await state.clear()
        return

    successful_groups = []

    try:
        # Получаем админа
        query = select(TelegramAdmin).where(TelegramAdmin.telegram_id == admin_id).options(selectinload(TelegramAdmin.groups))
        result = await db_session.execute(query)
        admin = result.scalar_one_or_none()

        if not admin:
            if confirmation_message_id:
                try:
                    await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                    logger.debug(f"Сообщение {confirmation_message_id} успешно удалено (админ не найден)")
                except TelegramBadRequest as e:
                    logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")
            message_text = escape_markdown("❌ Админ не найден.")
            logger.debug(f"Отправка сообщения об отсутствии админа: {message_text}")
            await call.message.answer(
                message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
            await state.clear()
            return

        logger.debug(f"Admin groups for {admin_id}: {[group.group_id for group in admin.groups]}")

        # Снимаем права в выбранных группах
        for group in selected_groups:
            try:
                # Проверяем статус пользователя
                member = await bot.get_chat_member(chat_id=group.group_id, user_id=admin_id)
                if member.status in ["left", "kicked"]:
                    message_text = (
                        escape_markdown(f"ℹ️ Пользователь @{admin_username or str(admin_id)} не состоит в группе ") +
                        format_group_link(group) + escape_markdown(".")
                    )
                    logger.debug(f"Отправка сообщения: {message_text}")
                    await call.message.answer(
                        message_text,
                        parse_mode="MarkdownV2",
                        reply_markup=get_start_reply_keyboard()
                    )
                    logger.info(f"Пользователь {admin_id} не в группе {group.group_id}, права не снимаются")
                    continue

                # Проверяем, является ли пользователь админом
                admins = await bot.get_chat_administrators(chat_id=group.group_id)
                is_admin_in_group = any(admin.user.id == admin_id for admin in admins)
                if not is_admin_in_group:
                    message_text = (
                        escape_markdown(f"ℹ️ Пользователь @{admin_username or str(admin_id)} не является админом в группе ") +
                        format_group_link(group) + escape_markdown(".")
                    )
                    logger.debug(f"Отправка сообщения: {message_text}")
                    await call.message.answer(
                        message_text,
                        parse_mode="MarkdownV2",
                        reply_markup=get_start_reply_keyboard()
                    )
                    logger.info(f"Пользователь {admin_id} не админ в группе {group.group_id}, права не снимаются")
                    # Синхронизируем базу данных
                    if any(g.group_id == group.group_id for g in admin.groups):
                        admin.groups = [g for g in admin.groups if g.group_id != group.group_id]
                        await db_session.commit()
                        logger.info(f"Группа {group.group_id} удалена из admin.groups для {admin_id}, так как пользователь не админ")
                    continue

                # Проверяем права бота
                bot_id = (await bot.get_me()).id
                bot_is_admin = any(admin.user.id == bot_id and admin.can_promote_members for admin in admins)
                if not bot_is_admin:
                    message_text = (
                        escape_markdown(f"⚠️ Бот не имеет прав снимать админов в группе ") +
                        format_group_link(group) + escape_markdown(". Дайте боту права.")
                    )
                    logger.debug(f"Отправка сообщения: {message_text}")
                    await call.message.answer(
                        message_text,
                        parse_mode="MarkdownV2",
                        reply_markup=get_start_reply_keyboard()
                    )
                    logger.warning(f"Бот не имеет прав в группе {group.group_id}")
                    continue

                # Снимаем права
                if await demote_admin_in_group(bot, group.group_id, admin_id):
                    # Удаляем группу из admin.groups
                    if any(g.group_id == group.group_id for g in admin.groups):
                        admin.groups = [g for g in admin.groups if g.group_id != group.group_id]
                        await db_session.commit()
                        logger.info(f"Группа {group.group_id} удалена из admin.groups для {admin_id}")
                    successful_groups.append(group)
                    message_text = (
                        escape_markdown(f"✅ Права админа сняты для @{admin_username or str(admin_id)} в группе ") +
                        format_group_link(group) + escape_markdown(".")
                    )
                    logger.debug(f"Отправка сообщения об успехе: {message_text}")
                    await call.message.answer(
                        message_text,
                        parse_mode="MarkdownV2",
                        reply_markup=get_start_reply_keyboard()
                    )
                    message_text = (
                        escape_markdown(f"ℹ️ Вы больше не админ в группе ") +
                        format_group_link(group) + escape_markdown(".")
                    )
                    logger.debug(f"Отправка уведомления админу {admin_id}: {message_text}")
                    await bot.send_message(
                        chat_id=admin_id,
                        text=message_text,
                        parse_mode="MarkdownV2"
                    )
                    logger.info(f"Права админа {admin_id} сняты в группе {group.group_id}")
                else:
                    message_text = (
                        escape_markdown(f"⚠️ Не удалось снять права в группе ") +
                        format_group_link(group) + escape_markdown(": операция не выполнена.")
                    )
                    logger.debug(f"Отправка сообщения об ошибке: {message_text}")
                    await call.message.answer(
                        message_text,
                        parse_mode="MarkdownV2",
                        reply_markup=get_start_reply_keyboard()
                    )
                    logger.warning(f"Не удалось снять права админа {admin_id} в группе {group.group_id}")
            except Exception as e:
                logger.error(f"Ошибка снятия прав админа {admin_id} в группе {group.group_id}: {e}")
                message_text = (
                    escape_markdown(f"⚠️ Не удалось снять права в группе ") +
                    format_group_link(group) + escape_markdown(f": {str(e)}.")
                )
                logger.debug(f"Отправка сообщения об ошибке: {message_text}")
                await call.message.answer(
                    message_text,
                    parse_mode="MarkdownV2",
                    reply_markup=get_start_reply_keyboard()
                )

        # Формируем итоговое сообщение
        group_names = ", ".join([format_group_link(group) for group in successful_groups]) if successful_groups else escape_markdown("ни в одной группе")
        escaped_username = escape_markdown(admin_username or str(admin_id))
        message_text = (
            escape_markdown(f"✅ Права админа @") +
            f"[{escaped_username}](https://t.me/{admin_username if admin_username else admin_id})" +
            escape_markdown(" сняты в группах: ") + group_names + escape_markdown(".")
        )
        logger.debug(f"Отправка итогового сообщения: {message_text}")
        await call.message.answer(
            message_text,
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )

        # Уведомляем админа
        try:
            await notify_admin(bot=bot, action="updated", admin=admin)
            logger.debug(f"Уведомление отправлено админу {admin_id}")
        except Exception as e:
            logger.error(f"Ошибка уведомления админа {admin_id}: {e}")

        # Удаляем сообщение с подтверждением
        if confirmation_message_id:
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                logger.debug(f"Сообщение {confirmation_message_id} успешно удалено")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")

        # Возвращаемся к списку групп
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        admin_groups = admin.groups
        escaped_username = escape_markdown(admin_username or str(admin_id))
        if not admin_groups:
            message_text = (
                escape_markdown(f"ℹ️ У админа @") +
                f"[{escaped_username}](https://t.me/{admin_username if admin_username else admin_id})" +
                escape_markdown(" нет групп.")
            )
            logger.debug(f"Отправка сообщения о пустых группах: {message_text}")
            await call.message.answer(
                message_text,
                parse_mode="MarkdownV2",
                reply_markup=get_start_reply_keyboard()
            )
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="Добавить группы ➕", callback_data="add_groups")])
        else:
            for group in admin_groups:
                keyboard.inline_keyboard.append(
                    [InlineKeyboardButton(
                        text=f"@{escape_markdown(group.username or str(group.group_id))}",
                        callback_data=f"view_group:{group.group_id}"
                    ),
                    InlineKeyboardButton(
                        text="Снять права 🗑️",
                        callback_data=f"remove_group:{group.group_id}"
                    )]
                )
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="Снять все права 🗑️", callback_data="remove_all_groups")])
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="Добавить группы ➕", callback_data="add_groups")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="Готово ✅", callback_data="finish")])

        message_text = (
            escape_markdown(f"📋 Группы админа @") +
            f"[{escaped_username}](https://t.me/{admin_username if admin_username else admin_id})" +
            escape_markdown(":")
        )
        logger.debug(f"Отправка сообщения о группах админа: {message_text}")
        groups_message = await call.message.answer(
            message_text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )
        await state.update_data(groups_message_id=groups_message.message_id, selected_groups=[])
        await state.set_state(ManageAdminGroupsStates.waiting_for_group_action)

    except Exception as e:
        logger.error(f"Ошибка обработки снятия прав админа {admin_id}: {e}")
        message_text = escape_markdown(f"❌ Ошибка: {str(e)}.")
        logger.debug(f"Отправка сообщения об общей ошибке: {message_text}")
        await call.message.answer(
            message_text,
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )
        if confirmation_message_id:
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
                logger.debug(f"Сообщение {confirmation_message_id} успешно удалено (ошибка)")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")
        await state.clear()




@router.callback_query(ManageAdminGroupsStates.waiting_for_groups_to_add,
                      F.data.startswith("add_group_") | F.data.in_(["confirm_groups", "cancel"]))
async def process_add_groups(call: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot) -> None:
    """
    Обрабатывает выбор групп для добавления прав администратора.

    Args:
        call: CallbackQuery от inline-кнопки.
        state: Контекст FSM для хранения данных.
        db_session: Асинхронная сессия SQLAlchemy.
        bot: Экземпляр Aiogram Bot.

    Raises:
        TelegramBadRequest: Если не удалось отправить или удалить сообщение.
        Exception: Для других ошибок при обработке.
    """
    data = await state.get_data()
    admin_id = data.get("admin_id")
    admin_username = data.get("admin_username")
    selected_groups = data.get("selected_groups", [])
    groups_message_id = data.get("groups_message_id")

    if call.data.startswith("add_group_"):
        group_id = int(call.data.replace("add_group_", ""))
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

    await call.answer()

    if call.data == "cancel":
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
            logger.debug(f"Сообщение {groups_message_id} успешно удалено (отмена)")
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось удалить сообщение {groups_message_id}: {e}")
        message_text = escape_markdown("❌ Операция отменена.")
        await call.message.answer(message_text, parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
        await state.clear()
        return

    if call.data == "confirm_groups":
        if not selected_groups:
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
                logger.debug(f"Сообщение {groups_message_id} успешно удалено (нет групп)")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить сообщение {groups_message_id}: {e}")
            message_text = escape_markdown("ℹ️ Не выбрано ни одной группы.")
            await call.message.answer(message_text, parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
            await state.clear()
            return

        # Подтверждение добавления
        group_names = ", ".join([format_group_link(group) for group in selected_groups])
        escaped_username = escape_markdown(admin_username or str(admin_id))
        text = (
            escape_markdown(f"Назначить админа @") +
            f"[{escaped_username}](https://t.me/{admin_username if admin_username else admin_id})" +
            escape_markdown(" в группах?\nГруппы: ") + group_names
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить ✅", callback_data="confirm_add_groups")],
            [InlineKeyboardButton(text="Отмена 🚫", callback_data="cancel")]
        ])
        confirmation_message = await call.message.reply(text, parse_mode="MarkdownV2", reply_markup=keyboard)
        await state.update_data(confirmation_message_id=confirmation_message.message_id)
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=groups_message_id)
            logger.debug(f"Сообщение {groups_message_id} успешно удалено (перед подтверждением)")
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось удалить сообщение {groups_message_id}: {e}")
        await state.set_state(ManageAdminGroupsStates.waiting_for_groups_to_add)





# @router.callback_query(ManageAdminGroupsStates.waiting_for_groups_to_remove,
#                        F.data.in_(["confirm_remove_groups", "cancel"]))
# async def confirm_remove_groups(call: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot):
#     """
#     Подтверждает или отменяет снятие прав админа в выбранных группах.
#
#     Args:
#         call: CallbackQuery от inline-кнопки.
#         state: Контекст FSM.
#         db_session: Асинхронная сессия SQLAlchemy.
#         bot: Экземпляр Aiogram Bot.
#     """
#     data = await state.get_data()
#     admin_id = data.get("admin_id")
#     admin_username = data.get("admin_username")
#     selected_groups = data.get("selected_groups", [])
#     confirmation_message_id = data.get("confirmation_message_id")
#
#     # Логируем входные данные для отладки
#     logger.debug(f"confirm_remove_groups: admin_id={admin_id}, admin_username={admin_username}, "
#                  f"selected_groups={[group.group_id for group in selected_groups]}, "
#                  f"confirmation_message_id={confirmation_message_id}")
#
#     await call.answer()
#
#     if call.data == "cancel":
#         if confirmation_message_id:
#             try:
#                 await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
#                 logger.debug(f"Сообщение {confirmation_message_id} успешно удалено (отмена)")
#             except Exception as e:
#                 logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")
#         message_text = escape_markdown("❌ Операция отменена.")
#         logger.debug(f"Отправка сообщения об отмене: {message_text}")
#         await call.message.answer(
#             message_text,
#             parse_mode="MarkdownV2",
#             reply_markup=get_start_reply_keyboard()
#         )
#         await state.clear()
#         return
#
#     successful_groups = []
#
#     try:
#         # Получаем админа
#         query = select(TelegramAdmin).where(TelegramAdmin.telegram_id == admin_id).options(selectinload(TelegramAdmin.groups))
#         result = await db_session.execute(query)
#         admin = result.scalar_one_or_none()
#
#         if not admin:
#             if confirmation_message_id:
#                 try:
#                     await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
#                     logger.debug(f"Сообщение {confirmation_message_id} успешно удалено (админ не найден)")
#                 except Exception as e:
#                     logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")
#             message_text = escape_markdown("❌ Админ не найден.")
#             logger.debug(f"Отправка сообщения об отсутствии админа: {message_text}")
#             await call.message.answer(
#                 message_text,
#                 parse_mode="MarkdownV2",
#                 reply_markup=get_start_reply_keyboard()
#             )
#             await state.clear()
#             return
#
#         # Логируем группы админа
#         logger.debug(f"Admin groups for {admin_id}: {[group.group_id for group in admin.groups]}")
#
#         # Снимаем права в выбранных группах
#         for group in selected_groups:
#             try:
#                 # Проверяем права бота
#                 admins = await bot.get_chat_administrators(chat_id=group.group_id)
#                 bot_id = (await bot.get_me()).id
#                 bot_is_admin = any(admin.user.id == bot_id and admin.can_promote_members for admin in admins)
#                 if not bot_is_admin:
#                     message_text = f"⚠️ Бот не имеет прав снимать админов в группе {escape_markdown(group.username or str(group.group_id))}. Дайте боту права."
#                     logger.debug(f"Отправка сообщения о правах бота: {message_text}")
#                     await call.message.answer(
#                         message_text,
#                         parse_mode="MarkdownV2",
#                         reply_markup=get_start_reply_keyboard()
#                     )
#                     logger.warning(f"Бот не имеет прав в группе {group.group_id}")
#                     continue
#
#                 # Снимаем права
#                 await bot.promote_chat_member(
#                     chat_id=group.group_id,
#                     user_id=admin_id,
#                     can_manage_chat=False,
#                     can_delete_messages=False,
#                     can_manage_video_chats=False,
#                     can_restrict_members=False,
#                     can_promote_members=False,
#                     can_change_info=False,
#                     can_invite_users=False,
#                     can_pin_messages=False,
#                     can_manage_topics=False
#                 )
#                 logger.info(f"Права админа {admin_id} сняты в группе {group.group_id}")
#
#                 # Удаляем группу из списка админа, если она там есть
#                 if group in admin.groups:
#                     admin.groups.remove(group)
#                     await db_session.commit()
#                     successful_groups.append(group)
#                     message_text = f"✅ Пользователь @{escape_markdown(admin_username or str(admin_id))} больше не админ в группе {escape_markdown(group.username or str(group.group_id))}."
#                     logger.debug(f"Отправка сообщения об успехе: {message_text}")
#                     await call.message.answer(
#                         message_text,
#                         parse_mode="MarkdownV2",
#                         reply_markup=get_start_reply_keyboard()
#                     )
#                     message_text = f"ℹ️ Вы больше не админ в группе {escape_markdown(group.username or str(group.group_id))}."
#                     logger.debug(f"Отправка уведомления админу {admin_id}: {message_text}")
#                     await bot.send_message(
#                         chat_id=admin_id,
#                         text=message_text,
#                         parse_mode="MarkdownV2"
#                     )
#                 else:
#                     logger.warning(f"Группа {group.group_id} не найдена в списке групп админа {admin_id}")
#
#             except Exception as e:
#                 logger.error(f"Ошибка снятия прав админа {admin_id} в группе {group.group_id}: {e}")
#                 message_text = f"⚠️ Не удалось снять права админа в группе {escape_markdown(group.username or str(group.group_id))}: {escape_markdown(str(e))}."
#                 logger.debug(f"Отправка сообщения об ошибке: {message_text}")
#                 await call.message.answer(
#                     message_text,
#                     parse_mode="MarkdownV2",
#                     reply_markup=get_start_reply_keyboard()
#                 )
#
#         # Формируем итоговое сообщение
#         group_names = ", ".join(
#             [escape_markdown(group.username or str(group.group_id)) for group in successful_groups]
#         ) if successful_groups else escape_markdown("ни в одной группе")
#         message_text = f"✅ Права админа @{escape_markdown(admin_username or str(admin_id))} сняты в группах: {group_names}."
#         logger.debug(f"Отправка итогового сообщения: {message_text}")
#         await call.message.answer(
#             message_text,
#             parse_mode="MarkdownV2",
#             reply_markup=get_start_reply_keyboard()
#         )
#
#         # Уведомляем админа
#         try:
#             await notify_admin(bot=bot, action="updated", admin=admin)
#             logger.debug(f"Уведомление отправлено админу {admin_id}")
#         except Exception as e:
#             logger.error(f"Ошибка уведомления админа {admin_id}: {e}")
#
#         # Удаляем сообщение с подтверждением
#         if confirmation_message_id:
#             try:
#                 await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
#                 logger.debug(f"Сообщение {confirmation_message_id} успешно удалено (конец обработки)")
#             except Exception as e:
#                 logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")
#
#         # Возвращаемся к списку групп
#         keyboard = InlineKeyboardMarkup(inline_keyboard=[])
#         admin_groups = admin.groups
#         if not admin_groups:
#             message_text = f"ℹ️ У админа @{escape_markdown(admin_username or str(admin_id))} нет групп."
#             logger.debug(f"Отправка сообщения о пустых группах: {message_text}")
#             await call.message.answer(
#                 message_text,
#                 parse_mode="MarkdownV2",
#                 reply_markup=get_start_reply_keyboard()
#             )
#             keyboard.inline_keyboard.append([InlineKeyboardButton(text="Добавить группы ➕", callback_data="add_groups")])
#         else:
#             for group in admin_groups:
#                 keyboard.inline_keyboard.append(
#                     [InlineKeyboardButton(
#                         text=f"@{escape_markdown(group.username or str(group.group_id))}",
#                         callback_data=f"view_group:{group.group_id}"
#                     ),
#                     InlineKeyboardButton(
#                         text="Снять права 🗑️",
#                         callback_data=f"remove_group:{group.group_id}"
#                     )]
#                 )
#             keyboard.inline_keyboard.append([InlineKeyboardButton(text="Снять все права 🗑️", callback_data="remove_all_groups")])
#             keyboard.inline_keyboard.append([InlineKeyboardButton(text="Добавить группы ➕", callback_data="add_groups")])
#         keyboard.inline_keyboard.append([InlineKeyboardButton(text="Готово ✅", callback_data="finish")])
#
#         message_text = f"📋 Группы админа @{escape_markdown(admin_username or str(admin_id))}:"
#         logger.debug(f"Отправка сообщения о группах админа: {message_text}")
#         groups_message = await call.message.answer(
#             message_text,
#             parse_mode="MarkdownV2",
#             reply_markup=keyboard
#         )
#         await state.update_data(groups_message_id=groups_message.message_id, selected_groups=[])
#         await state.set_state(ManageAdminGroupsStates.waiting_for_group_action)
#
#     except Exception as e:
#         logger.error(f"Ошибка обработки снятия прав админа {admin_id}: {e}")
#         message_text = f"❌ Ошибка: {escape_markdown(str(e))}."
#         logger.debug(f"Отправка сообщения об общей ошибке: {message_text}")
#         await call.message.answer(
#             message_text,
#             parse_mode="MarkdownV2",
#             reply_markup=get_start_reply_keyboard()
#         )
#         if confirmation_message_id:
#             try:
#                 await bot.delete_message(chat_id=call.message.chat.id, message_id=confirmation_message_id)
#                 logger.debug(f"Сообщение {confirmation_message_id} успешно удалено (ошибка)")
#             except Exception as e:
#                 logger.warning(f"Не удалось удалить сообщение {confirmation_message_id}: {e}")
#         await state.clear()





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
            admin_list = escape_markdown("👥 Нет админов.")
        else:
            admin_list = escape_markdown("👥 Список админов:\n")
            for admin in admins:
                escaped_username = escape_markdown(admin.username or "Нет username")
                username_link = f"[{escaped_username}](https://t.me/{admin.username.lstrip('@')})" if admin.username else escape_markdown("Нет username")
                group_names = ", ".join([format_group_link(g) for g in admin.groups]) if admin.groups else escape_markdown("нет групп")
                line = f"• {username_link} \\(ID: {admin.telegram_id}, Groups: {group_names}\\)"
                admin_list += f"{line}\n"

        await call.message.answer(admin_list, parse_mode="MarkdownV2", reply_markup=get_start_reply_keyboard())
        await call.answer()
        logger.debug("Список админов отправлен")
    except Exception as e:
        logger.error(f"Ошибка в callback_list_admins: {e}")
        await call.message.answer(
            escape_markdown(f"❌ Ошибка при отправке списка админов: {str(e)}."),
            parse_mode="MarkdownV2",
            reply_markup=get_start_reply_keyboard()
        )
        await call.answer()