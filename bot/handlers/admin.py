# bot/admin.py

import logging
import os
import uuid

from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, ContentType, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv

from bot.keyboards.reply_keyboards import get_start_reply_keyboard
from bot.services.admin_service import is_admin, add_admin, remove_admin
from bot.keyboards.quiz_keyboards import get_admin_menu_keyboard
from bot.services.webhook_service import WebhookService
from bot.states.admin_states import AddAdminStates, RemoveAdminStates, WebhookStates
from bot.utils.markdownV2 import escape_markdown
from database.models import Webhook
from webhook_sender import is_valid_url


# Загрузка переменных окружения
load_dotenv()

# Инициализация маршрутизатора
router = Router(name="admin_router")

# Настройка логирования
logger = logging.getLogger(__name__)

# Секретный пароль для добавления и удаления администраторов
ADMIN_SECRET_PASSWORD = os.getenv("ADMIN_SECRET_PASSWORD")
ADMIN_REMOVE_SECRET_PASSWORD = os.getenv("ADMIN_REMOVE_SECRET_PASSWORD")

# Команда /add_admin
@router.message(Command("add_admin"))
async def cmd_add_admin(message: Message, state: FSMContext, db_session: AsyncSession):
    user_id = message.from_user.id
    if not await is_admin(user_id, db_session):
        await message.reply("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {message.from_user.username} ({user_id}) попытался добавить администратора без прав.")
        return
    await message.reply("🔒 Введите секретный пароль для добавления нового администратора:")
    await AddAdminStates.waiting_for_password.set()



# Обработка пароля для добавления администратора
@router.message(AddAdminStates.waiting_for_password, F.content_type == ContentType.TEXT)
async def process_add_admin_password(message: Message, state: FSMContext, db_session: AsyncSession):
    if message.text != ADMIN_SECRET_PASSWORD:
        await message.reply("❌ Неверный пароль. Доступ запрещен.")
        logger.warning(f"Неверный пароль от пользователя {message.from_user.username} ({message.from_user.id}).")
        await state.clear()
        return
    await message.reply("✅ Пароль верный. Пожалуйста, введите Telegram ID пользователя, которого хотите добавить:")
    await AddAdminStates.waiting_for_user_id.set()



# Обработка Telegram ID для добавления администратора
@router.message(AddAdminStates.waiting_for_user_id, F.content_type == ContentType.TEXT)
async def process_add_admin_user_id(message: Message, state: FSMContext, db_session: AsyncSession):
    try:
        new_admin_id = int(message.text)
    except ValueError:
        await message.reply("❌ Пожалуйста, введите корректный числовой Telegram ID.")
        return

    # Проверка, не является ли пользователь уже администратором
    if await is_admin(new_admin_id, db_session):
        await message.reply("ℹ️ Этот пользователь уже является администратором.")
        await state.clear()
        return

    # Добавление администратора
    try:
        # Получение username нового администратора (если доступен)
        try:
            user = await message.bot.get_chat(new_admin_id)
            username = user.username if user.username else "Без username"
            logger.debug(f"Получен username для нового администратора: {username}")
        except Exception as e:
            await message.reply("❌ Не удалось найти пользователя с таким Telegram ID. Проверьте корректность ID.")
            logger.error(f"Не удалось получить информацию о пользователе с ID {new_admin_id}: {e}")
            await state.clear()
            await message.answer(
                "🔄 Возвращаюсь в главное меню.",
                reply_markup=get_admin_menu_keyboard()
            )
            return

        await add_admin(new_admin_id, username, db_session)
        await message.reply(f"🎉 Пользователь @{username} (ID: {new_admin_id}) успешно добавлен как администратор.")
        logger.info(f"Пользователь @{username} (ID: {new_admin_id}) добавлен как администратор.")

        # Уведомление нового администратора (опционально)
        try:
            await message.bot.send_message(new_admin_id, "🎉 Вы были добавлены как администратор бота.")
            logger.debug(f"Уведомление отправлено пользователю {new_admin_id}")
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {new_admin_id}: {e}")

        # Возврат в главное меню
        await message.answer(
            "🔄 Возвращаюсь в главное меню.",
            reply_markup=get_admin_menu_keyboard()
        )
    except IntegrityError:
        await message.reply("❌ Не удалось добавить администратора. Возможно, пользователь уже существует.")
        logger.error(f"IntegrityError при добавлении администратора с ID {new_admin_id}\\.")
        await state.clear()
    except Exception as e:
        await message.reply(f"❌ Произошла ошибка: {e}")
        logger.error(f"Ошибка при добавлении администратора: {e}")
        await state.clear()



# Команда /remove_admin
@router.message(Command("remove_admin"))
async def cmd_remove_admin(message: Message, state: FSMContext, db_session: AsyncSession):
    user_id = message.from_user.id
    if not await is_admin(user_id, db_session):
        await message.reply("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {message.from_user.username} ({user_id}) попытался удалить администратора без прав.")
        return
    await message.reply("🔒 Введите секретный пароль для удаления администратора:")
    await RemoveAdminStates.waiting_for_password.set()



# Обработка пароля для удаления администратора
@router.message(RemoveAdminStates.waiting_for_password, F.content_type == ContentType.TEXT)
async def process_remove_admin_password(message: Message, state: FSMContext, db_session: AsyncSession):
    if message.text != ADMIN_REMOVE_SECRET_PASSWORD:
        await message.reply("❌ Неверный пароль. Доступ запрещён.")
        logger.warning(f"Неверный пароль от пользователя {message.from_user.username} ({message.from_user.id}).")
        await state.clear()
        return
    await message.reply("✅ Пароль верный. Пожалуйста, введите Telegram ID администратора, которого хотите удалить:")
    await RemoveAdminStates.waiting_for_user_id.set()



# Обработка Telegram ID для удаления администратора
@router.message(RemoveAdminStates.waiting_for_user_id, F.content_type == ContentType.TEXT)
async def process_remove_admin_user_id(message: Message, state: FSMContext, db_session: AsyncSession):
    try:
        admin_id = int(message.text)
    except ValueError:
        await message.reply("❌ Пожалуйста, введите корректный числовой Telegram ID.")
        return

    # Проверка, является ли пользователь администратором
    if not await is_admin(admin_id, db_session):
        await message.reply("ℹ️ Этот пользователь не является администратором.")
        logger.info(f"Пользователь с ID {admin_id} не является администратором.")
        await state.clear()
        return

    # Удаление администратора
    try:
        await remove_admin(admin_id, db_session)
        await message.reply(f"🗑️ Пользователь с Telegram ID {admin_id} успешно удалён из списка администраторов.")
        logger.info(f"Пользователь с Telegram ID {admin_id} удалён из списка администраторов.")
        # Возврат в главное меню
        await message.answer(
            reply_markup=get_start_reply_keyboard()
        )
    except Exception as e:
        await message.reply(f"❌ Произошла ошибка: {e}")
        logger.error(f"Ошибка при удалении администратора: {e}")
    await state.clear()



# Команда /start для приветствия
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("👋 Привет! Я бот для управления администраторами.\nИспользуйте /add_admin для добавления администратора и /remove_admin для удаления.")








# Обработчик кнопки "Добавить вебхук"
@router.callback_query(F.data == "add_webhook")
async def callback_add_webhook(call: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.message.answer("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {call.from_user.username} ({user_id}) попытался добавить вебхук без прав.")
        await call.answer()
        return
    await call.message.answer("🔗 Пожалуйста, отправьте URL вебхука:")
    await state.set_state(WebhookStates.waiting_for_webhook_url)  # Исправлено здесь
    await call.answer()



# Обработчик добавления вебхука через сообщение
@router.message(WebhookStates.waiting_for_webhook_url, F.content_type == ContentType.TEXT)
async def process_add_webhook_url(message: Message, state: FSMContext, db_session: AsyncSession):
    url = message.text.strip()
    if not is_valid_url(url):
        await message.reply("❌ Некорректный URL. Пожалуйста, отправьте валидный URL вебхука.")
        return
    await state.update_data(webhook_url=url)
    await message.reply("🔗 Если необходимо, укажите название сервиса (например, make.com, Zapier). Если нет, отправьте 'Нет':")
    await state.set_state(WebhookStates.waiting_for_service_name)  # Исправлено здесь






# Обработчик добавления вебхука через сообщение
@router.message(WebhookStates.waiting_for_service_name, F.content_type == ContentType.TEXT)
async def process_add_webhook_service_name(message: Message, state: FSMContext, db_session: AsyncSession):
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
            # Сообщаем пользователю, что вебхук с таким URL уже существует
            await message.reply("❌ Вебхук с таким URL уже существует.")
            await state.clear()
            return

        # Экранирование динамических частей сообщения
        escaped_id = escape_markdown(str(webhook.id))
        escaped_url = escape_markdown(webhook.url)
        escaped_service = escape_markdown(webhook.service_name or "Не указано")

        # Создание кнопки удаления
        delete_button = InlineKeyboardButton(
            text="🗑️ Удалить",
            callback_data=f"delete_webhook:{webhook.id}"
        )
        # Правильное создание клавиатуры
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
        await message.reply("❌ Произошла ошибка при добавлении вебхука.")
        logger.error(f"Ошибка при добавлении вебхука: {e}")
    await state.clear()




# Команда /listwebhooks
@router.message(Command("listwebhooks"))
async def cmd_list_webhooks(message: Message, db_session: AsyncSession):
    user_id = message.from_user.id
    if not await is_admin(user_id, db_session):
        await message.reply("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {message.from_user.username} ({user_id}) попытался просмотреть вебхуки без прав.")
        return

    webhook_service = WebhookService(db_session)
    webhooks = await webhook_service.list_webhooks(include_inactive=True)  # Передаем параметр
    if not webhooks:
        await message.reply("📭 Вебхуки не найдены.")
        return

    response = "📋 **Список вебхуков:**\n\n"
    buttons = []
    for wh in webhooks:
        # Экранирование динамических частей сообщения
        escaped_id = escape_markdown(str(wh.id))
        escaped_url = escape_markdown(wh.url)
        escaped_service = escape_markdown(wh.service_name or "Не указано")
        status = "Активен" if wh.is_active else "Неактивен"

        # Формирование текста вебхука
        webhook_info = (
            f"• **ID:** `{escaped_id}`\n"
            f"  **URL:** {escaped_url}\n"
            f"  **Сервис:** {escaped_service}\n"
            f"  **Статус:** {status}\n"
        )
        response += f"{webhook_info}\n"

        # Создание кнопки удаления для каждого вебхука
        delete_button = InlineKeyboardButton(
            text=f"🗑️ Удалить {wh.id}",
            callback_data=f"delete_webhook:{wh.id}"
        )
        buttons.append([delete_button])  # Каждая кнопка в отдельном списке

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.reply(response, parse_mode="MarkdownV2", reply_markup=keyboard)
    logger.debug(f"Форматированное сообщение для списка вебхуков: {response}")






@router.callback_query(F.data.startswith("delete_webhook:"))
async def callback_delete_webhook(call: CallbackQuery, db_session: AsyncSession):
    logger.debug(f"Получен callback_query с данными: {call.data}")
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.message.answer("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {call.from_user.username} ({user_id}) попытался удалить вебхук без прав\\.")
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
        logger.warning(f"Попытка удалить несуществующий вебхук с ID {webhook_id}\\.")
        await call.answer()
        return

    service_name = webhook.service_name or "Не указано"

    success = await webhook_service.delete_webhook(webhook_id)
    if success:
        escaped_service = escape_markdown(service_name)
        # Удаление точки после инлайн-кода или её экранирование
        message_text = (
            f"✅ Вебхук с ID `{webhook.id}` успешно удалён\\.\n"
            f"Сервис: {escaped_service}"
        )
        logger.debug(f"Отправляемое сообщение:\n{message_text}")
        await call.message.answer(message_text, parse_mode="MarkdownV2")
        logger.info(f"Вебхук с ID {webhook_id} и сервисом '{service_name}' успешно удалён.")
    else:
        message_text = f"❌ Вебхук с ID `{webhook.id}` не удалось удалить\\."
        logger.debug(f"Отправляемое сообщение:\n{message_text}")
        await call.message.answer(message_text, parse_mode="MarkdownV2")
        logger.error(f"Ошибка при удалении вебхука с ID {webhook_id}.")

    await call.answer()




# Обработчик кнопки "Список вебхуков"
@router.callback_query(F.data == "list_webhooks")
async def callback_list_webhooks(call: CallbackQuery, db_session: AsyncSession):
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.message.answer("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {call.from_user.username} ({user_id}) попытался просмотреть вебхуки без прав.")
        await call.answer()
        return

    webhook_service = WebhookService(db_session)
    webhooks = await webhook_service.list_webhooks(include_inactive=True)  # Передаём параметр include_inactive=True

    if not webhooks:
        await call.message.answer("📭 Вебхуки не найдены.")
        await call.answer()
        return

    response = "📋 **Список вебхуков:**\n\n"
    buttons = []
    for wh in webhooks:
        # Экранирование динамических частей сообщения
        escaped_id = escape_markdown(str(wh.id))
        escaped_url = escape_markdown(wh.url)
        escaped_service = escape_markdown(wh.service_name or "Не указано")
        status = "🟢 Активен" if wh.is_active else "🔴 Неактивен"

        # Формирование текста вебхука
        webhook_info = (
            f"• **ID:** `{escaped_id}`\n"
            f"  **URL:** {escaped_url}\n"
            f"  **Сервис:** {escaped_service}\n"
            f"  **Статус:** {status}\n"
        )
        response += f"{webhook_info}\n"

        # Создание кнопок управления для вебхука
        toggle_text = "Деактивировать" if wh.is_active else "Активировать"
        toggle_callback = f"toggle_webhook:{wh.id}"
        delete_callback = f"delete_webhook:{wh.id}"

        toggle_button = InlineKeyboardButton(text=toggle_text, callback_data=toggle_callback)
        delete_button = InlineKeyboardButton(text="🗑️ Удалить", callback_data=delete_callback)
        buttons.append([toggle_button, delete_button])  # Кнопки в одной строке

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.answer(response, parse_mode="MarkdownV2", reply_markup=keyboard)
    logger.debug(f"Форматированное сообщение для списка вебхуков: {response}")
    await call.answer()





@router.callback_query(F.data == "delete_webhook_menu")
async def callback_delete_webhook_menu(call: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.message.answer("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {call.from_user.username} ({user_id}) попытался удалить вебхук без прав\\.")
        await call.answer()
        return
    await call.message.answer("🗑️ Пожалуйста, отправьте ID вебхука, который хотите удалить:")
    await state.set_state(WebhookStates.waiting_for_webhook_id)
    await call.answer()




# Обработчик добавления вебхука через сообщение
@router.message(WebhookStates.waiting_for_service_name, F.content_type == ContentType.TEXT)
async def process_add_webhook_service_name(message: Message, state: FSMContext, db_session: AsyncSession):
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

        # Экранирование динамических частей сообщения
        escaped_id = escape_markdown(str(webhook.id))
        escaped_url = escape_markdown(webhook.url)
        escaped_service = escape_markdown(webhook.service_name or "Не указано")

        # Создание кнопки удаления
        delete_button = InlineKeyboardButton(
            text="🗑️ Удалить",
            callback_data=f"delete_webhook:{webhook.id}"
        )
        # Правильное создание клавиатуры
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
        await message.reply("❌ Произошла ошибка при добавлении вебхука.")
        logger.error(f"Ошибка при добавлении вебхука: {e}")
    await state.clear()



# Команда /listwebhooks
@router.message(Command("listwebhooks"))
async def cmd_list_webhooks(message: Message, db_session: AsyncSession):
    user_id = message.from_user.id
    if not await is_admin(user_id, db_session):
        await message.reply("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {message.from_user.username} ({user_id}) попытался просмотреть вебхуки без прав.")
        return

    webhook_service = WebhookService(db_session)
    webhooks = await webhook_service.list_webhooks(include_inactive=True)  # Получаем все вебхуки
    if not webhooks:
        await message.reply("📭 Вебхуки не найдены.")
        return

    response = "📋 **Список вебхуков:**\n\n"
    buttons = []
    for wh in webhooks:
        # Экранирование динамических частей сообщения
        escaped_id = escape_markdown(str(wh.id))
        escaped_url = escape_markdown(wh.url)
        escaped_service = escape_markdown(wh.service_name or "Не указано")
        status = "🟢 Активен" if wh.is_active else "🔴 Неактивен"

        # Формирование текста вебхука
        webhook_info = (
            f"• **ID:** `{escaped_id}`\n"
            f"  **URL:** {escaped_url}\n"
            f"  **Сервис:** {escaped_service}\n"
            f"  **Статус:** {status}\n"
        )
        response += f"{webhook_info}\n"

        # Создание кнопок управления для вебхука
        toggle_text = "🔄 Деактивировать" if wh.is_active else "🔄 Активировать"
        toggle_callback = f"toggle_webhook:{wh.id}"
        delete_callback = f"delete_webhook:{wh.id}"

        toggle_button = InlineKeyboardButton(text=toggle_text, callback_data=toggle_callback)
        delete_button = InlineKeyboardButton(text="🗑️ Удалить", callback_data=delete_callback)
        buttons.append([toggle_button, delete_button])  # Кнопки в одной строке

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.reply(response, parse_mode="MarkdownV2", reply_markup=keyboard)
    logger.debug(f"Форматированное сообщение для списка вебхуков: {response}")



# Обработчик удаления вебхука по UUID из состояния
@router.message(WebhookStates.waiting_for_webhook_id, F.content_type == ContentType.TEXT)
async def process_delete_webhook_id(message: Message, state: FSMContext, db_session: AsyncSession):
    webhook_id_str = message.text.strip()
    try:
        webhook_id = uuid.UUID(webhook_id_str)
    except ValueError:
        await message.reply("❌ Некорректный формат ID. Пожалуйста, отправьте валидный UUID.")
        return

    webhook_service = WebhookService(db_session)
    webhook = await webhook_service.get_webhook(webhook_id)  # Получаем информацию о вебхуке
    if not webhook:
        escaped_id = escape_markdown(str(webhook_id))
        await message.reply(f"❌ Вебхук с ID `{escaped_id}` не найден или уже удалён", parse_mode="MarkdownV2")
        logger.warning(f"Попытка удалить несуществующий вебхук с ID {webhook_id}.")
        return

    service_name = webhook.service_name or "Не указано"  # Получаем название сервиса
    success = await webhook_service.delete_webhook(webhook_id)
    if success:
        escaped_id = escape_markdown(str(webhook_id))
        escaped_service = escape_markdown(service_name)
        await message.reply(
            f"✅ Вебхук с ID `{escaped_id}` успешно удалён\\. \nСервис: {escaped_service}",
            parse_mode="MarkdownV2"
        )
        logger.info(f"Вебхук с ID {webhook_id} и сервисом '{service_name}' удалён.")
    else:
        escaped_id = escape_markdown(str(webhook_id))
        await message.reply(f"❌ Вебхук с ID `{escaped_id}` не удалось удалить", parse_mode="MarkdownV2")
        logger.error(f"Ошибка при удалении вебхука с ID {webhook_id}.")

    await state.clear()










@router.message(Command("activatewebhook"))
async def cmd_activate_webhook(message: types.Message, command: Command, db_session: AsyncSession):
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
        # Точка находится внутри инлайн-кода
        await message.reply(
            f"✅ Вебхук с ID `{escaped_id}` активирован\\.\n"
            f"Сервис: {escaped_service}",
            parse_mode="MarkdownV2"
        )
        logger.info(f"Вебхук с ID {webhook_id} и сервисом '{webhook.service_name}' активирован\\.")
    else:
        escaped_id = escape_markdown(str(webhook.id))
        message_text = f"❌ Не удалось активировать вебхук с ID `{escaped_id}`\\."
        await message.reply(message_text, parse_mode="MarkdownV2")
        logger.error(f"Ошибка при активации вебхука с ID {webhook_id}\\.")



@router.message(Command("deactivatewebhook"))
async def cmd_deactivate_webhook(message: types.Message, command: Command, db_session: AsyncSession):
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
        # Точка находится внутри инлайн-кода
        await message.reply(
            f"✅ Вебхук с ID `{escaped_id}` деактивирован \n"
            f"Сервис: {escaped_service}",
            parse_mode="MarkdownV2"
        )
        logger.info(f"Вебхук с ID {webhook_id} и сервисом '{webhook.service_name}' деактивирован\\.")
    else:
        escaped_id = escape_markdown(str(webhook.id))
        message_text = f"❌ Не удалось деактивировать вебхук с ID `{escaped_id}`"
        await message.reply(message_text, parse_mode="MarkdownV2")
        logger.error(f"Ошибка при деактивации вебхука с ID {webhook_id}\\.")



@router.callback_query(F.data.startswith("toggle_webhook:"))
async def callback_toggle_webhook(call: CallbackQuery, db_session: AsyncSession):
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

    if webhook.is_active:
        success = await webhook_service.deactivate_webhook(webhook_id)
        action = "деактивирован"
    else:
        success = await webhook_service.activate_webhook(webhook_id)
        action = "активирован"

    if success:
        escaped_service = escape_markdown(webhook.service_name or "Не указано")
        # Удаление точки после инлайн-кода или её экранирование
        message_text = (
            f"✅ Вебхук с ID `{webhook.id}` {action}\\.\n"
            f"Сервис: {escaped_service}"
        )
        logger.info(f"Вебхук с ID {webhook_id} и сервисом '{webhook.service_name}' {action}\\.")
        await call.message.answer(message_text, parse_mode="MarkdownV2")
    else:
        message_text = f"❌ Не удалось {action} вебхук с ID `{webhook.id}`\\."
        logger.error(f"Ошибка при {action} вебхука с ID {webhook_id}\\.")
        await call.message.answer(message_text, parse_mode="MarkdownV2")

    await call.answer()