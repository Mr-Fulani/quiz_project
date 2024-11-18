# handlers/start.py

import logging
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from bot.utils.db_utils import fetch_one  # Импортируем утилиты для БД
from database.models import Task, TaskTranslation
from bot.keyboards.quiz_keyboards import get_admin_menu_keyboard, get_start_reply_keyboard  # Убедитесь, что путь корректен

logger = logging.getLogger(__name__)
logger.info("✅ Модуль handlers/start.py импортирован")

router = Router()

# Обработчик команды /start
@router.message(Command(commands=["start"]))
async def start_command(message: Message):
    """
    Обработчик команды /start. Выводит приветственное сообщение и клавиатуру с кнопкой "Меню".
    """
    logger.info("Обработчик /start вызван")
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"🔔 Пользователь {username} (ID: {user_id}) отправил команду /start")

    try:
        # Отправляем сообщение с reply-клавиатурой
        await message.answer(
            "👋 Добро пожаловать! Нажмите кнопку 'Меню', чтобы продолжить.",
            reply_markup=get_start_reply_keyboard()  # Показываем клавиатуру с кнопкой "Меню"
        )
    except Exception as e:
        logger.exception(f"Ошибка в обработчике start_command: {e}")


# Обработчик нажатия кнопки "Меню"
@router.message(lambda message: message.text == "Меню")
async def handle_start_button(message: Message):
    """
    Обрабатывает нажатие кнопки "Меню" и выводит admin меню с инлайн-кнопками.
    """
    try:
        await message.answer(
            "Выберите действие из меню ниже:",
            reply_markup=get_admin_menu_keyboard()  # Показываем инлайн-клавиатуру
        )
    except Exception as e:
        logger.exception(f"Ошибка в обработчике handle_start_button: {e}")


# Добавляем новый обработчик для команды /start quiz_{message_id}
@router.message(lambda message: message.text and message.text.startswith("/start quiz_"))
async def handle_quiz_start(message: Message, bot: Bot, db_session: AsyncSession):
    """
    Обработчик команды /start quiz_{message_id}. Создаёт и отправляет опрос на основе message_id.
    """
    try:
        # Извлечение message_id из команды
        parts = message.text.split("_")
        if len(parts) != 2:
            await message.reply("❌ Неверный формат команды. Используйте /start quiz_{message_id}")
            return

        poll_message_id_str = parts[1]
        if not poll_message_id_str.isdigit():
            await message.reply("❌ message_id должно быть числом.")
            return

        poll_message_id = int(poll_message_id_str)

        # Получаем задачу по message_id
        query_task = select(Task).where(Task.message_id == poll_message_id)
        task = await fetch_one(db_session, query_task)
        if not task:
            await message.reply("❌ Задача не найдена.")
            return

        # Получаем перевод задачи
        query_translation = select(TaskTranslation).where(TaskTranslation.task_id == task.id)
        translation = await fetch_one(db_session, query_translation)
        if not translation:
            await message.reply("❌ Перевод задачи не найден.")
            return

        # Определяем индекс правильного ответа
        correct_answer_text = translation.correct_answer
        try:
            correct_option_id = translation.answers.index(correct_answer_text)
        except ValueError:
            correct_option_id = 0  # По умолчанию, если правильный ответ не найден в списке

        # Отправляем опрос и сохраняем message_id
        poll_message = await bot.send_poll(
            chat_id=message.chat.id,
            question=translation.question,
            options=translation.answers,
            type="quiz",
            correct_option_id=correct_option_id,
            is_anonymous=task.is_anonymous,
            allows_multiple_answers=task.allows_multiple_answers
        )

        # Сохраняем message_id опроса в задаче
        task.message_id = poll_message.message_id
        await db_session.commit()
        logger.info(f"✅ Опрос отправлен для задачи ID {task.id} с message_id {poll_message.message_id}")

        await message.reply("✅ Опрос успешно отправлен.")

    except Exception as e:
        await db_session.rollback()
        logger.exception(f"❌ Ошибка при обработке команды /start quiz: {e}")
        await message.reply("❌ Произошла ошибка при запуске опроса.")




















# @router.message(Command("start"))
# async def start_command(message: Message):
#     """
#     Обработчик команды /start. Выводит приветственное сообщение и клавиатуру.
#     """
#     user_id = message.from_user.id
#     username = message.from_user.username
#     logger.info(f"🔔 Пользователь {username} (ID: {user_id}) отправил команду /start")
#
#     # Отправляем сообщение с Inline-кнопкой "Старт"
#     await message.reply(
#         "👋 Добро пожаловать! Нажмите кнопку 'Старт', чтобы продолжить.",
#         reply_markup=get_admin_menu_keyboard()
#     )








# # Обработчик нажатий на Inline-кнопку "Старт"
# @router.callback_query(lambda call: call.data == "start_pressed")
# async def inline_start_pressed(call: CallbackQuery, db_session: AsyncSession):
#     """
#     Обрабатывает нажатие на кнопку 'Старт'. Проверяет, является ли пользователь администратором.
#     """
#     user_id = call.from_user.id
#     username = call.from_user.username
#
#     logger.info(f"🟢 Пользователь {username} (ID: {user_id}) нажал на кнопку 'Старт'")
#
#     # Проверяем, является ли пользователь администратором
#     if await is_admin(user_id, db_session):
#         logger.info(f"✅ Пользователь {username} (ID: {user_id}) является администратором")
#         await call.message.answer(
#             "🔑 Добро пожаловать, администратор! Теперь вам доступны следующие функции:"
#         )
#         # Здесь можно добавить дальнейший функционал для администраторов
#     else:
#         logger.info(f"🚫 Пользователь {username} (ID: {user_id}) не является администратором")
#         await call.message.answer("❌ У вас нет прав для доступа к функционалу.")
#
#     await call.answer()  # Закрываем всплывающее уведомление







