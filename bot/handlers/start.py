import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.quiz_keyboards import get_start_inline_keyboard, get_admin_menu_keyboard
from bot.services.admin_service import is_admin

router = Router()


# Настройка локального логирования
logger = logging.getLogger(__name__)


@router.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    print(f"Telegram ID: {user_id}, Username: {username}")

    logger.info(f"Пользователь {username} ({user_id}) отправил команду /start")

    # Отправляем сообщение с Inline-кнопкой "Старт"
    await message.reply("Нажмите кнопку 'Старт', чтобы продолжить", reply_markup=get_admin_menu_keyboard())



# Обработчик нажатий на Inline-кнопку "Старт"
@router.callback_query(lambda call: call.data == "start_pressed")
async def inline_start_pressed(call: CallbackQuery, db_session: AsyncSession):
    user_id = call.from_user.id
    username = call.from_user.username

    logger.info(f"Пользователь {username} ({user_id}) нажал на кнопку 'Старт'")

    # Проверяем, является ли пользователь администратором
    if await is_admin(user_id, db_session):
        logger.info(f"Пользователь {username} ({user_id}) является администратором")
        await call.message.answer("Добро пожаловать, администратор! Теперь вам доступны следующие функции:")
        # Здесь можно добавить дальнейший функционал для администраторов (например, клавиатуры для управления ботом)
    else:
        logger.info(f"Пользователь {username} ({user_id}) не является администратором")
        await call.message.answer("У вас нет прав для доступа к функционалу.")
    await call.answer()  # Закрываем всплывающее уведомление