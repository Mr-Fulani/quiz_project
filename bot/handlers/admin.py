# bot/admin.py

import logging
import os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv

from bot.services.admin_service import is_admin, add_admin, remove_admin
from bot.keyboards.quiz_keyboards import get_admin_menu_keyboard
from bot.states.admin_states import AddAdminStates, RemoveAdminStates

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
        logger.error(f"IntegrityError при добавлении администратора с ID {new_admin_id}.")
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
            "🔄 Возвращаюсь в главное меню.",
            reply_markup=get_admin_menu_keyboard()
        )
    except Exception as e:
        await message.reply(f"❌ Произошла ошибка: {e}")
        logger.error(f"Ошибка при удалении администратора: {e}")
    await state.clear()

# Команда /start для приветствия
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("👋 Привет! Я бот для управления администраторами.\nИспользуйте /add_admin для добавления администратора и /remove_admin для удаления.")