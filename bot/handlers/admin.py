# bot/admin.py
import asyncio
import datetime
import logging
import os
import uuid
from datetime import datetime, timedelta


from aiogram import F, Bot
from aiogram import Router, types
from aiogram.filters import Command, StateFilter, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ContentType, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from dotenv import load_dotenv
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.add_admin import async_session_maker
from bot.database.models import FeedbackMessage
from bot.keyboards.quiz_keyboards import get_admin_menu_keyboard, get_feedback_keyboard
from bot.keyboards.reply_keyboards import get_start_reply_keyboard
from bot.services.admin_service import is_admin, add_admin, remove_admin
from bot.services.webhook_sender import is_valid_url
from bot.services.webhook_service import WebhookService
from bot.states.admin_states import AddAdminStates, RemoveAdminStates, WebhookStates, FeedbackStates
from bot.utils.markdownV2 import escape_markdown

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
        await message.reply(
            "⛔ У вас нет прав для выполнения этой команды.",
            reply_markup=get_start_reply_keyboard()
        )
        logger.warning(f"Пользователь {message.from_user.username} ({user_id}) попытался добавить администратора без прав.")
        return
    await message.reply(
        "🔒 Введите секретный пароль для добавления нового администратора:",
        reply_markup=ForceReply(selective=True)
    )
    logger.debug("Просьба ввести пароль для добавления администратора через команду /add_admin")
    await AddAdminStates.waiting_for_password.set()



# Обработка пароля для добавления администратора
@router.message(AddAdminStates.waiting_for_password, F.content_type == ContentType.TEXT)
async def process_add_admin_password(message: Message, state: FSMContext, db_session: AsyncSession):
    if message.text != ADMIN_SECRET_PASSWORD:
        await message.reply(
            "❌ Неверный пароль. Доступ запрещен.",
            reply_markup=get_start_reply_keyboard()
        )
        logger.warning(f"Неверный пароль от пользователя {message.from_user.username} ({message.from_user.id}).")
        await state.clear()
        return
    await message.reply(
        "✅ Пароль верный. Пожалуйста, введите Telegram ID пользователя, которого хотите добавить:",
        reply_markup=ForceReply(selective=True)
    )
    logger.debug("Пароль верен. Просьба ввести Telegram ID нового администратора")
    await AddAdminStates.waiting_for_user_id.set()





@router.message(AddAdminStates.waiting_for_user_id, F.content_type == ContentType.TEXT)
async def process_add_admin_user_id(message: Message, state: FSMContext, db_session: AsyncSession):
    logger.info("Обработчик ввода Telegram ID для добавления администратора вызван")
    if not message.text:
        await message.reply(
            "❌ Сообщение не содержит текста. Пожалуйста, введите корректный Telegram ID пользователя.",
            reply_markup=ForceReply(selective=True)
        )
        logger.warning(f"Пользователь {message.from_user.username} ({message.from_user.id}) отправил сообщение без текста.")
        return

    try:
        new_admin_id = int(message.text)
    except (ValueError, TypeError):
        await message.reply(
            "❌ Пожалуйста, введите корректный числовой Telegram ID (например, 123456789).",
            reply_markup=ForceReply(selective=True)
        )
        logger.debug(f"Пользователь {message.from_user.username} ({message.from_user.id}) ввёл некорректный ID: {message.text}")
        return

    # Проверка, не является ли пользователь уже администратором
    if await is_admin(new_admin_id, db_session):
        await message.reply(
            "ℹ️ Этот пользователь уже является администратором.",
            reply_markup=get_start_reply_keyboard()
        )
        logger.info(f"Пользователь с ID {new_admin_id} уже является администратором.")
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
            await message.reply(
                "❌ Не удалось найти пользователя с таким Telegram ID. Проверьте корректность ID.",
                reply_markup=get_start_reply_keyboard()
            )
            logger.error(f"Не удалось получить информацию о пользователе с ID {new_admin_id}: {e}")
            await state.clear()
            return

        await add_admin(new_admin_id, username, db_session)
        await message.reply(
            f"🎉 Пользователь @{username} (ID: {new_admin_id}) успешно добавлен как администратор",
            reply_markup=get_start_reply_keyboard()
        )
        logger.info(f"Пользователь @{username} (ID: {new_admin_id}) добавлен как администратор")

        # Уведомление нового администратора (опционально)
        try:
            await message.bot.send_message(new_admin_id, "🎉 Вы были добавлены как администратор бота.")
            logger.debug(f"Уведомление отправлено пользователю {new_admin_id}")
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {new_admin_id}: {e}")

        # Возврат в главное меню с кнопкой "Меню"
        await message.answer(
            "🔄 Возвращаюсь в главное меню.",
            reply_markup=get_start_reply_keyboard()
        )
        await state.clear()
    except IntegrityError:
        await message.reply(
            "❌ Не удалось добавить администратора. Возможно, пользователь уже существует.",
            reply_markup=get_start_reply_keyboard()
        )
        logger.error(f"IntegrityError при добавлении администратора с ID {new_admin_id}")
        await state.clear()
    except Exception as e:
        await message.reply(
            f"❌ Произошла ошибка: {e}",
            reply_markup=get_start_reply_keyboard()
        )
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
            "🔄 Возвращаюсь в главное меню.",
            reply_markup=get_admin_menu_keyboard()
        )
    except Exception as e:
        await message.reply(f"❌ Произошла ошибка: {e}")
        logger.error(f"Ошибка при удалении администратора: {e}")
    await state.clear()








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






# Обработчик кнопки "Написать Администратору" - БЕЗ ИЗМЕНЕНИЙ
@router.message(lambda message: message.text and message.text.lower() == "написать администратору")
async def handle_write_to_admin(message: types.Message):
    await message.answer("Ваше сообщение для администратора. Напишите текст, и он будет передан.")


# ИСПРАВЛЕННЫЙ обработчик для сохранения сообщения пользователя
class UserMessageFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        current_state = await state.get_state()
        return (
            message.text
            and message.text.lower() != "написать администратору"
            and current_state != FeedbackStates.awaiting_reply
        )

# Используем фильтр в обработчике
@router.message(UserMessageFilter())
async def save_feedback_message(message: types.Message):
    async with async_session_maker() as session:
        feedback = FeedbackMessage(
            user_id=message.from_user.id,
            username=message.from_user.username,
            message=message.text,
            created_at=datetime.utcnow(),
            is_processed=False
        )
        session.add(feedback)
        await session.commit()
    await message.answer("Ваше сообщение сохранено, Мы ответим Вам в ближайшее время. Спасибо!")


# Обработчик для просмотра необработанных сообщений - БЕЗ ИЗМЕНЕНИЙ
@router.callback_query(lambda c: c.data == "view_feedback")
async def show_unprocessed_feedback(callback_query: types.CallbackQuery):
    logging.info("Обработчик 'Просмотреть сообщения' вызван.")
    async with async_session_maker() as session:
        result = await session.execute(
            select(FeedbackMessage).where(FeedbackMessage.is_processed == False)
        )
        feedbacks = result.scalars().all()

    if not feedbacks:
        await callback_query.message.answer("Нет необработанных сообщений.")
        await callback_query.answer()
        return

    for feedback in feedbacks:
        feedback_text = (
            f"ID: {feedback.id}\n"
            f"Пользователь: @{feedback.username or 'Неизвестно'} (ID: {feedback.user_id})\n"
            f"Сообщение: {feedback.message}"
        )
        await callback_query.message.answer(feedback_text, reply_markup=get_feedback_keyboard(feedback.id))

    await callback_query.answer()


# Обработчик для пометки сообщения как обработанного - БЕЗ ИЗМЕНЕНИЙ
@router.callback_query(lambda c: c.data.startswith("mark_processed:"))
async def mark_feedback_processed(callback_query: types.CallbackQuery):
    feedback_id = int(callback_query.data.split(":")[1])

    async with async_session_maker() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await callback_query.answer("Сообщение не найдено или уже обработано.", show_alert=True)
            return

        feedback.is_processed = True
        await session.commit()

    await callback_query.answer("Сообщение помечено как обработанное.", show_alert=True)
    await callback_query.message.delete()


# ИСПРАВЛЕННЫЙ обработчик для ответа на feedback
@router.message(StateFilter(FeedbackStates.awaiting_reply))
async def handle_feedback_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    feedback_id = data.get("feedback_id")
    user_id = data.get("user_id")

    if not feedback_id or not user_id:
        await message.answer("Ошибка: невозможно найти данные для ответа.")
        await state.clear()
        return

    async with async_session_maker() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await message.answer("Сообщение пользователя не найдено.")
            await state.clear()
            return

        try:
            # Отправляем сообщение пользователю
            await message.bot.send_message(
                chat_id=user_id,
                text=f"Ответ от администратора:\n\nВаше сообщение: {feedback.message}\n\nОтвет: {message.text}"
            )
            feedback.is_processed = True
            await session.commit()

            # Подтверждение администратору
            await message.answer(f"✅ Ответ успешно отправлен пользователю @{feedback.username}")

            # Удаляем сообщение с кнопками
            try:
                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=message.message_id - 1
                )
            except Exception as e:
                logging.warning(f"Не удалось удалить сообщение с кнопками: {e}")

        except Exception as e:
            await message.answer(f"❌ Ошибка при отправке ответа: {str(e)}")
            logging.error(f"Ошибка отправки ответа: {e}")
        finally:
            await state.clear()

# Обработчик для начала ответа на сообщение - БЕЗ ИЗМЕНЕНИЙ
@router.callback_query(lambda c: c.data.startswith("reply_to_feedback:"))
async def start_feedback_reply(callback_query: types.CallbackQuery, state: FSMContext):
    feedback_id = int(callback_query.data.split(":")[1])

    async with async_session_maker() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await callback_query.answer("Сообщение не найдено.", show_alert=True)
            return

    # Сначала устанавливаем данные
    await state.update_data(feedback_id=feedback_id, user_id=feedback.user_id)
    # Затем устанавливаем состояние
    await state.set_state(FeedbackStates.awaiting_reply)

    await callback_query.message.answer(
        f"Введите ваш ответ для пользователя @{feedback.username}:\n"
        f"Исходное сообщение: {feedback.message}"
    )
    await callback_query.answer()

# Обработчик для удаления сообщения - БЕЗ ИЗМЕНЕНИЙ
@router.callback_query(lambda c: c.data.startswith("delete_feedback:"))
async def delete_feedback(callback_query: types.CallbackQuery):
    feedback_id = int(callback_query.data.split(":")[1])

    async with async_session_maker() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await callback_query.answer("Сообщение не найдено или уже удалено.", show_alert=True)
            return

        await session.delete(feedback)
        await session.commit()

    await callback_query.answer("Сообщение удалено.", show_alert=True)
    await callback_query.message.delete()






