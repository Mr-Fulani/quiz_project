import logging
import re
import uuid

from aiogram import F, Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ContentType, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.admin_service import is_admin
from bot.services.webhook_service import WebhookService
from bot.states.admin_states import WebhookStates
from bot.utils.markdownV2 import escape_markdown



# Инициализация маршрутизатора
router = Router(name="admin_router")

# Настройка логирования
logger = logging.getLogger(__name__)


# Обработчик кнопки "Добавить вебхук"
@router.callback_query(F.data == "add_webhook")
async def callback_add_webhook(call: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """Обрабатывает нажатие кнопки 'Добавить вебхук' и запрашивает URL.

    Args:
        call (CallbackQuery): Callback-запрос от нажатия кнопки.
        state (FSMContext): Контекст состояния для управления FSM.
        db_session (AsyncSession): Сессия базы данных.
    """
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.message.answer("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {call.from_user.username} ({user_id}) попытался добавить вебхук без прав.")
        await call.answer()
        return
    await call.message.answer(
        "🔗 Пожалуйста, отправьте URL вебхука.\n"
        "📌 URL может быть без 'https://', бот добавит его автоматически.\n"
        "Пример: example.com или https://example.com/webhook"
    )
    await state.set_state(WebhookStates.waiting_for_webhook_url)
    await call.answer()


# Обработчик добавления URL вебхука
@router.message(WebhookStates.waiting_for_webhook_url, F.content_type == ContentType.TEXT)
async def process_add_webhook_url(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    """Обрабатывает введенный URL вебхука, добавляет https://, если нужно, и проверяет валидность.

    Args:
        message (Message): Сообщение от пользователя с URL.
        state (FSMContext): Контекст состояния для хранения данных.
        db_session (AsyncSession): Сессия базы данных.
        bot (Bot): Экземпляр Telegram-бота.
    """
    # Удаляем предыдущее временное уведомление, если оно есть
    data = await state.get_data()
    temp_message_id = data.get('temp_message_id')
    chat_id = message.chat.id
    if temp_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=temp_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить временное сообщение {temp_message_id}: {e}")
        await state.update_data(temp_message_id=None)

    url = message.text.strip()
    # Исправление: автоматически добавляем https://, если протокол не указан
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    # Проверка URL через регулярное выражение
    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    if not re.match(url_pattern, url):
        await message.reply(
            "❌ Неверный формат URL. Введите корректный URL (например, example.com или https://example.com/webhook).\n"
            "Попробуйте снова:"
        )
        return
    await state.update_data(webhook_url=url)
    await message.reply("🔗 Если необходимо, укажите название сервиса (например, make.com, Zapier). Если нет, отправьте 'Нет':")
    await state.set_state(WebhookStates.waiting_for_service_name)



# Обработчик добавления названия сервиса
@router.message(WebhookStates.waiting_for_service_name, F.content_type == ContentType.TEXT)
async def process_add_webhook_service_name(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    """Обрабатывает введенное название сервиса и добавляет вебхук.

    Args:
        message (Message): Сообщение от пользователя с названием сервиса.
        state (FSMContext): Контекст состояния с данными вебхука.
        db_session (AsyncSession): Сессия базы данных.
        bot (Bot): Экземпляр Telegram-бота.
    """
    # Удаляем предыдущее временное уведомление, если оно есть
    data = await state.get_data()
    temp_message_id = data.get('temp_message_id')
    chat_id = message.chat.id
    if temp_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=temp_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить временное сообщение {temp_message_id}: {e}")
        await state.update_data(temp_message_id=None)

    service_name = message.text.strip()
    if service_name.lower() == "нет":
        service_name = None
    await state.update_data(service_name=service_name)
    webhook_data = await state.get_data()
    url = webhook_data.get("webhook_url")
    service = webhook_data.get("service_name")

    webhook_service = WebhookService(db_session)
    try:
        webhook = await webhook_service.add_webhook(url, service)

        if webhook is None:
            await message.reply(
                f"❌ Вебхук с URL `{escape_markdown(url)}` уже существует.\n"
                "Используйте другой URL или проверьте существующие вебхуки."
            )
            await state.clear()
            return

        escaped_id = escape_markdown(str(webhook.id))
        escaped_url = escape_markdown(webhook.url)
        escaped_service = escape_markdown(webhook.service_name or "Не указано")

        delete_button = InlineKeyboardButton(
            text="🗑️ Удалить",
            callback_data=f"delete_webhook:{webhook.id}"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[delete_button]])

        await message.reply(
            f"✅ Вебхук добавлен:\n"
            f"ID: `{escaped_id}`\n"
            f"URL: {escaped_url}\n"
            f"Сервис: {escaped_service}",
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )
        logger.info(f"Вебхук добавлен: ID={webhook.id}, URL={webhook.url}, Сервис={webhook.service_name}")
    except Exception as e:
        await message.reply(
            f"❌ Ошибка при добавлении вебхука: {str(e)}.\n"
            "Убедитесь, что URL корректен, и попробуйте снова."
        )
        logger.error(f"Ошибка при добавлении вебхука: {e}")
    await state.clear()



# Команда /listwebhooks
@router.message(Command("listwebhooks"))
async def cmd_list_webhooks(message: Message, db_session: AsyncSession, bot: Bot, state: FSMContext):
    """Обрабатывает команду /listwebhooks для отображения списка вебхуков.

    Args:
        message (Message): Сообщение с командой.
        db_session (AsyncSession): Сессия базы данных.
        bot (Bot): Экземпляр Telegram-бота.
        state (FSMContext): Контекст состояния.
    """
    # Удаляем предыдущее временное уведомление, если оно есть
    data = await state.get_data()
    temp_message_id = data.get('temp_message_id')
    chat_id = message.chat.id
    if temp_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=temp_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить временное сообщение {temp_message_id}: {e}")
        await state.update_data(temp_message_id=None)

    user_id = message.from_user.id
    if not await is_admin(user_id, db_session):
        await message.reply("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {message.from_user.username} ({user_id}) попытался просмотреть вебхуки без прав.")
        return

    webhook_service = WebhookService(db_session)
    webhooks = await webhook_service.list_webhooks(include_inactive=True)
    if not webhooks:
        await message.reply("📭 Вебхуки не найдены.")
        return

    response = "📋 **Список вебхуков:**\n\n"
    buttons = []
    for wh in webhooks:
        escaped_id = escape_markdown(str(wh.id))
        escaped_url = escape_markdown(wh.url)
        escaped_service = escape_markdown(wh.service_name or "Не указано")
        status = "🟢 Активен" if wh.is_active else "🔴 Неактивен"

        webhook_info = (
            f"• **ID:** `{escaped_id}`\n"
            f"  **URL:** {escaped_url}\n"
            f"  **Сервис:** {escaped_service}\n"
            f"  **Статус:** {status}\n"
        )
        response += f"{webhook_info}\n"

        toggle_text = "🔄 Деактивировать" if wh.is_active else "🔄 Активировать"
        toggle_callback = f"toggle_webhook:{wh.id}"
        delete_callback = f"delete_webhook:{wh.id}"

        toggle_button = InlineKeyboardButton(text=toggle_text, callback_data=toggle_callback)
        delete_button = InlineKeyboardButton(text="🗑️ Удалить", callback_data=delete_callback)
        buttons.append([toggle_button, delete_button])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.reply(response, parse_mode="MarkdownV2", reply_markup=keyboard)
    logger.debug(f"Форматированное сообщение для списка вебхуков: {response}")


# Обработчик удаления вебхука
@router.callback_query(F.data.startswith("delete_webhook:"))
async def callback_delete_webhook(call: CallbackQuery, db_session: AsyncSession, bot: Bot, state: FSMContext):
    """Обрабатывает нажатие кнопки удаления вебхука с временным уведомлением.

    Args:
        call (CallbackQuery): Callback-запрос с ID вебхука.
        db_session (AsyncSession): Сессия базы данных.
        bot (Bot): Экземпляр Telegram-бота.
        state (FSMContext): Контекст состояния.
    """
    logger.debug(f"Получен callback_query с данными: {call.data}")
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.message.answer("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {call.from_user.username} ({user_id}) попытался удалить вебхук без прав.")
        await call.answer()
        return

    try:
        webhook_id_str = call.data.split(":")[1]
        webhook_id = uuid.UUID(webhook_id_str)
        logger.debug(f"Попытка удалить вебхук с ID: {webhook_id}")
    except (IndexError, ValueError) as e:
        await call.message.answer("❌ Некорректный ID вебхука.")
        logger.error(f"Некорректный ID вебхука в callback_data: {call.data} - Ошибка: {e}")
        await call.answer()
        return

    webhook_service = WebhookService(db_session)
    webhook = await webhook_service.get_webhook(webhook_id)

    if not webhook:
        await call.message.answer(f"❌ Вебхук с ID `{webhook_id}` не найден или уже удалён", parse_mode="MarkdownV2")
        logger.warning(f"Попытка удалить несуществующий вебхук с ID {webhook_id}.")
        await call.answer()
        return

    service_name = webhook.service_name or "Не указано"

    # Исправление: отправляем временное уведомление
    temp_message = await call.message.answer("⏳ Удаление вебхука...")
    await state.update_data(temp_message_id=temp_message.message_id)

    success = await webhook_service.delete_webhook(webhook_id)
    if success:
        escaped_service = escape_markdown(service_name)
        message_text = (
            f"✅ Вебхук с ID `{webhook.id}` успешно удалён.\n"
            f"Сервис: {escaped_service}"
        )
        logger.debug(f"Отправляемое сообщение:\n{message_text}")
        await call.message.answer(message_text, parse_mode="MarkdownV2")
        logger.info(f"Вебхук с ID {webhook_id} и сервисом '{service_name}' успешно удалён.")
    else:
        message_text = f"❌ Вебхук с ID `{webhook.id}` не удалось удалить."
        logger.debug(f"Отправляемое сообщение:\n{message_text}")
        await call.message.answer(message_text, parse_mode="MarkdownV2")
        logger.error(f"Ошибка при удалении вебхука с ID {webhook_id}.")

    await call.answer()




# Обработчик кнопки "Список вебхуков"
@router.callback_query(F.data == "list_webhooks")
async def callback_list_webhooks(call: CallbackQuery, db_session: AsyncSession, bot: Bot, state: FSMContext):
    """Обрабатывает нажатие кнопки 'Список вебхуков'.

    Args:
        call (CallbackQuery): Callback-запрос от нажатия кнопки.
        db_session (AsyncSession): Сессия базы данных.
        bot (Bot): Экземпляр Telegram-бота.
        state (FSMContext): Контекст состояния.
    """
    # Удаляем предыдущее временное уведомление, если оно есть
    data = await state.get_data()
    temp_message_id = data.get('temp_message_id')
    chat_id = call.message.chat.id
    if temp_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=temp_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить временное сообщение {temp_message_id}: {e}")
        await state.update_data(temp_message_id=None)

    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.message.answer("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {call.from_user.username} ({user_id}) попытался просмотреть вебхуки без прав.")
        await call.answer()
        return

    webhook_service = WebhookService(db_session)
    webhooks = await webhook_service.list_webhooks(include_inactive=True)

    if not webhooks:
        await call.message.answer("📭 Вебхуки не найдены.")
        await call.answer()
        return

    response = "📋 **Список вебхуков:**\n\n"
    buttons = []
    for wh in webhooks:
        escaped_id = escape_markdown(str(wh.id))
        escaped_url = escape_markdown(wh.url)
        escaped_service = escape_markdown(wh.service_name or "Не указано")
        status = "🟢 Активен" if wh.is_active else "🔴 Неактивен"

        webhook_info = (
            f"• **ID:** `{escaped_id}`\n"
            f"  **URL:** {escaped_url}\n"
            f"  **Сервис:** {escaped_service}\n"
            f"  **Статус:** {status}\n"
        )
        response += f"{webhook_info}\n"

        toggle_text = "🔄 Деактивировать" if wh.is_active else "🔄 Активировать"
        toggle_callback = f"toggle_webhook:{wh.id}"
        delete_callback = f"delete_webhook:{wh.id}"

        toggle_button = InlineKeyboardButton(text=toggle_text, callback_data=toggle_callback)
        delete_button = InlineKeyboardButton(text="🗑️ Удалить", callback_data=delete_callback)
        buttons.append([toggle_button, delete_button])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.answer(response, parse_mode="MarkdownV2", reply_markup=keyboard)
    logger.debug(f"Форматированное сообщение для списка вебхуков: {response}")
    await call.answer()




# Обработчик кнопки удаления вебхука
@router.callback_query(F.data == "delete_webhook_menu")
async def callback_delete_webhook_menu(call: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot):
    """Обрабатывает нажатие кнопки меню удаления вебхука и запрашивает ID.

    Args:
        call (CallbackQuery): Callback-запрос от нажатия кнопки.
        state (FSMContext): Контекст состояния для управления FSM.
        db_session (AsyncSession): Сессия базы данных.
        bot (Bot): Экземпляр Telegram-бота.
    """
    # Удаляем предыдущее временное уведомление, если оно есть
    data = await state.get_data()
    temp_message_id = data.get('temp_message_id')
    chat_id = call.message.chat.id
    if temp_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=temp_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить временное сообщение {temp_message_id}: {e}")
        await state.update_data(temp_message_id=None)

    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.message.answer("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {call.from_user.username} ({user_id}) попытался удалить вебхук без прав.")
        await call.answer()
        return
    await call.message.answer("🗑️ Пожалуйста, отправьте ID вебхука, который хотите удалить:")
    await state.set_state(WebhookStates.waiting_for_webhook_id)
    await call.answer()





# Обработчик удаления вебхука по ID
@router.message(WebhookStates.waiting_for_webhook_id, F.content_type == ContentType.TEXT)
async def process_delete_webhook_id(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    """Обрабатывает введенный ID вебхука для удаления.

    Args:
        message (Message): Сообщение с ID вебхука.
        state (FSMContext): Контекст состояния.
        db_session (AsyncSession): Сессия базы данных.
        bot (Bot): Экземпляр Telegram-бота.
    """
    # Удаляем предыдущее временное уведомление, если оно есть
    data = await state.get_data()
    temp_message_id = data.get('temp_message_id')
    chat_id = message.chat.id
    if temp_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=temp_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить временное сообщение {temp_message_id}: {e}")
        await state.update_data(temp_message_id=None)

    webhook_id_str = message.text.strip()
    try:
        webhook_id = uuid.UUID(webhook_id_str)
    except ValueError:
        await message.reply("❌ Некорректный формат ID. Пожалуйста, отправьте валидный UUID.")
        return

    webhook_service = WebhookService(db_session)
    webhook = await webhook_service.get_webhook(webhook_id)
    if not webhook:
        escaped_id = escape_markdown(str(webhook_id))
        await message.reply(f"❌ Вебхук с ID `{escaped_id}` не найден или уже удалён", parse_mode="MarkdownV2")
        logger.warning(f"Попытка удалить несуществующий вебхук с ID {webhook_id}.")
        return

    service_name = webhook.service_name or "Не указано"
    success = await webhook_service.delete_webhook(webhook_id)
    if success:
        escaped_id = escape_markdown(str(webhook_id))
        escaped_service = escape_markdown(service_name)
        await message.reply(
            f"✅ Вебхук с ID `{escaped_id}` успешно удалён.\nСервис: {escaped_service}",
            parse_mode="MarkdownV2"
        )
        logger.info(f"Вебхук с ID {webhook_id} и сервисом '{service_name}' удалён.")
    else:
        escaped_id = escape_markdown(str(webhook_id))
        await message.reply(f"❌ Вебхук с ID `{escaped_id}` не удалось удалить", parse_mode="MarkdownV2")
        logger.error(f"Ошибка при удалении вебхука с ID {webhook_id}.")

    await state.clear()




# Команда /activatewebhook
@router.message(Command("activatewebhook"))
async def cmd_activate_webhook(message: Message, command: Command, db_session: AsyncSession, bot: Bot, state: FSMContext):
    """Обрабатывает команду /activatewebhook для активации вебхука.

    Args:
        message (Message): Сообщение с командой.
        command (Command): Объект команды с аргументами.
        db_session (AsyncSession): Сессия базы данных.
        bot (Bot): Экземпляр Telegram-бота.
        state (FSMContext): Контекст состояния.
    """
    # Удаляем предыдущее временное уведомление, если оно есть
    data = await state.get_data()
    temp_message_id = data.get('temp_message_id')
    chat_id = message.chat.id
    if temp_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=temp_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить временное сообщение {temp_message_id}: {e}")
        await state.update_data(temp_message_id=None)

    user_id = message.from_user.id
    if not await is_admin(user_id, db_session):
        await message.reply("⛔ У вас нет прав для выполнения этой команды.")
        return

    args = command.args
    if not args:
        await message.reply("❗ Пожалуйста, укажите ID вебхука для активации.")
        return

    try:
        webhook_id = uuid.UUID(args.strip())
    except ValueError:
        await message.reply("❌ Некорректный формат ID. Пожалуйста, отправьте валидный UUID.")
        return

    webhook_service = WebhookService(db_session)
    webhook = await webhook_service.get_webhook(webhook_id)

    if not webhook:
        escaped_id = escape_markdown(str(webhook_id))
        await message.reply(f"❌ Вебхук с ID `{escaped_id}` не найден", parse_mode="MarkdownV2")
        return

    success = await webhook_service.activate_webhook(webhook_id)
    if success:
        escaped_id = escape_markdown(str(webhook.id))
        escaped_service = escape_markdown(webhook.service_name or "Не указано")
        await message.reply(
            f"✅ Вебхук с ID `{escaped_id}` активирован.\n"
            f"Сервис: {escaped_service}",
            parse_mode="MarkdownV2"
        )
        logger.info(f"Вебхук с ID {webhook_id} и сервисом '{webhook.service_name}' активирован.")
    else:
        escaped_id = escape_markdown(str(webhook.id))
        message_text = f"❌ Не удалось активировать вебхук с ID `{escaped_id}`."
        await message.reply(message_text, parse_mode="MarkdownV2")
        logger.error(f"Ошибка при активации вебхука с ID {webhook_id}.")



# Команда /deactivatewebhook
@router.message(Command("deactivatewebhook"))
async def cmd_deactivate_webhook(message: Message, command: Command, db_session: AsyncSession, bot: Bot, state: FSMContext):
    """Обрабатывает команду /deactivatewebhook для деактивации вебхука.

    Args:
        message (Message): Сообщение с командой.
        command (Command): Объект команды с аргументами.
        db_session (AsyncSession): Сессия базы данных.
        bot (Bot): Экземпляр Telegram-бота.
        state (FSMContext): Контекст состояния.
    """
    # Удаляем предыдущее временное уведомление, если оно есть
    data = await state.get_data()
    temp_message_id = data.get('temp_message_id')
    chat_id = message.chat.id
    if temp_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=temp_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить временное сообщение {temp_message_id}: {e}")
        await state.update_data(temp_message_id=None)

    user_id = message.from_user.id
    if not await is_admin(user_id, db_session):
        await message.reply("⛔ У вас нет прав для выполнения этой команды.")
        return

    args = command.args
    if not args:
        await message.reply("❗ Пожалуйста, укажите ID вебхука для деактивации.")
        return

    try:
        webhook_id = uuid.UUID(args.strip())
    except ValueError:
        await message.reply("❌ Некорректный формат ID. Пожалуйста, отправьте валидный UUID.")
        return

    webhook_service = WebhookService(db_session)
    webhook = await webhook_service.get_webhook(webhook_id)

    if not webhook:
        escaped_id = escape_markdown(str(webhook_id))
        await message.reply(f"❌ Вебхук с ID `{escaped_id}` не найден", parse_mode="MarkdownV2")
        return

    success = await webhook_service.deactivate_webhook(webhook_id)
    if success:
        escaped_id = escape_markdown(str(webhook.id))
        escaped_service = escape_markdown(webhook.service_name or "Не указано")
        await message.reply(
            f"✅ Вебхук с ID `{escaped_id}` деактивирован.\n"
            f"Сервис: {escaped_service}",
            parse_mode="MarkdownV2"
        )
        logger.info(f"Вебхук с ID {webhook_id} и сервисом '{webhook.service_name}' деактивирован.")
    else:
        escaped_id = escape_markdown(str(webhook.id))
        message_text = f"❌ Не удалось деактивировать вебхук с ID `{escaped_id}`."
        await message.reply(message_text, parse_mode="MarkdownV2")
        logger.error(f"Ошибка при деактивации вебхука с ID {webhook_id}.")




# Обработчик переключения статуса вебхука
@router.callback_query(F.data.startswith("toggle_webhook:"))
async def callback_toggle_webhook(call: CallbackQuery, db_session: AsyncSession, bot: Bot, state: FSMContext):
    """Обрабатывает нажатие кнопки переключения статуса вебхука с временным уведомлением.

    Args:
        call (CallbackQuery): Callback-запрос с ID вебхука.
        db_session (AsyncSession): Сессия базы данных.
        bot (Bot): Экземпляр Telegram-бота.
        state (FSMContext): Контекст состояния.
    """
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.answer("⛔ У вас нет прав для выполнения этой команды.", show_alert=True)
        return

    try:
        webhook_id_str = call.data.split(":")[1]
        webhook_id = uuid.UUID(webhook_id_str)
    except (IndexError, ValueError):
        await call.answer("❌ Некорректный ID вебхука.", show_alert=True)
        return

    webhook_service = WebhookService(db_session)
    webhook = await webhook_service.get_webhook(webhook_id)
    if not webhook:
        await call.message.answer(f"❌ Вебхук с ID `{webhook_id}` не найден", parse_mode="MarkdownV2")
        return

    # Исправление: отправляем временное уведомление
    action = "деактивации" if webhook.is_active else "активации"
    temp_message = await call.message.answer(f"⏳ Выполняется {action} вебхука...")
    await state.update_data(temp_message_id=temp_message.message_id)

    if webhook.is_active:
        success = await webhook_service.deactivate_webhook(webhook_id)
        action = "деактивирован"
    else:
        success = await webhook_service.activate_webhook(webhook_id)
        action = "активирован"

    if success:
        escaped_service = escape_markdown(webhook.service_name or "Не указано")
        message_text = (
            f"✅ Вебхук с ID `{webhook.id}` {action}.\n"
            f"Сервис: {escaped_service}"
        )
        logger.info(f"Вебхук с ID {webhook_id} и сервисом '{webhook.service_name}' {action}.")
        await call.message.answer(message_text, parse_mode="MarkdownV2")
    else:
        message_text = f"❌ Не удалось {action} вебхук с ID `{webhook.id}`."
        logger.error(f"Ошибка при {action} вебхука с ID {webhook_id}.")
        await call.message.answer(message_text, parse_mode="MarkdownV2")

    await call.answer()


