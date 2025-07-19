# bot/handlers/start.py

import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import TelegramAdmin  # Убедитесь, что модель Admin импортирована
from bot.keyboards.quiz_keyboards import get_admin_menu_keyboard  # Убедитесь, что путь корректен
from bot.keyboards.reply_keyboards import get_start_reply_keyboard, get_admin_start_reply_keyboard
from bot.services.admin_service import is_admin  # Импорт функции проверки администратора

logger = logging.getLogger(__name__)
logger.info("✅ Модуль handlers/start.py импортирован")

router = Router(name="start_router")



@router.message(Command(commands=["start"]))
async def start_command(message: types.Message, db_session: AsyncSession):
    """
    Обработчик команды /start. Отправляет приветственное сообщение и клавиатуру.
    """
    logger.info(f"🔔 Пользователь {message.from_user.username or 'None'} (ID: {message.from_user.id}) отправил /start")
    try:
        # Проверяем, является ли пользователь админом
        is_user_admin = await is_admin(message.from_user.id, db_session)
        
        if is_user_admin:
            # Для админов показываем клавиатуру с кнопкой "Меню Администратора"
            await message.answer(
                "👋 Привет, администратор!",
                reply_markup=get_admin_start_reply_keyboard()
            )
            # Обновляем username если изменился
            query = select(TelegramAdmin).where(TelegramAdmin.telegram_id == message.from_user.id)
            result = await db_session.execute(query)
            admin = result.scalar_one_or_none()
            if admin and admin.username != message.from_user.username:
                admin.username = message.from_user.username
                await db_session.commit()
                logger.debug(f"Обновлён username для админа {message.from_user.id}")
        else:
            # Для обычных пользователей показываем клавиатуру только с "🆘 Поддержка-Support"
            await message.answer(
                "👋 Привет! \nЕсли у тебя есть вопросы, нажми '🆘 Поддержка-Support'.",
                reply_markup=get_start_reply_keyboard()
            )
    except Exception as e:
        logger.exception(f"Ошибка в start_command: {e}")
        await message.reply("❌ Произошла ошибка.")


@router.message(lambda message: message.text == "Меню Администратора")
async def handle_start_button(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает нажатие кнопки "Меню Администратора". Отправляет админ-меню админам.
    """
    logger.info(f"Пользователь {message.from_user.username or 'None'} нажал 'Меню Администратора'")
    try:
        # Кнопка показывается только админам, поэтому дополнительная проверка не нужна
        await message.answer("👋 Привет, администратор! Вот ваше меню:", reply_markup=get_admin_menu_keyboard())
    except Exception as e:
        logger.exception(f"Ошибка в handle_start_button: {e}")
        await message.reply("❌ Произошла ошибка.")