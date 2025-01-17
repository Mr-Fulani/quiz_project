# bot/handlers/start.py

import logging
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.reply_keyboards import get_start_reply_keyboard
from bot.states.admin_states import PasswordStates
from bot.utils.db_utils import fetch_one  # Убедитесь, что этот модуль существует и корректен
from bot.config import ADMIN_SECRET_PASSWORD
from bot.database.models import Task, TaskTranslation, Admin  # Убедитесь, что модель Admin импортирована
from bot.keyboards.quiz_keyboards import get_admin_menu_keyboard   # Убедитесь, что путь корректен

from bot.services.admin_service import is_admin  # Импорт функции проверки администратора




logger = logging.getLogger(__name__)
logger.info("✅ Модуль handlers/start.py импортирован")

router = Router(name="start_router")



@router.message(Command(commands=["start"]))
async def start_command(message: Message, db_session: AsyncSession):
    """
    Обработчик команды /start. Отправляет приветственное сообщение и клавиатуру с кнопкой "Меню" для всех пользователей.
    """
    logger.info("Обработчик /start вызван")
    user_id = message.from_user.id
    username = message.from_user.username or "None"
    logger.info(f"🔔 Пользователь {username} (ID: {user_id}) отправил команду /start")

    try:
        await message.answer(
            "👋 Привет! Я бот для управления администраторами.\nНажмите кнопку 'Меню', чтобы продолжить.",
            reply_markup=get_start_reply_keyboard()
        )
        logger.debug("Стартовое меню отправлено")

        # Если пользователь уже администратор, обновим его username
        admin_status = await is_admin(user_id, db_session)
        if admin_status:
            # Обновляем username
            query = select(Admin).where(Admin.telegram_id == user_id)
            result = await db_session.execute(query)
            admin = result.scalar_one_or_none()
            if admin:
                admin.username = message.from_user.username
                await db_session.commit()
                logger.debug(f"Обновлён username для админа {user_id} на {admin.username}")
    except Exception as e:
        logger.exception(f"Ошибка в обработчике start_command: {e}")
        await message.reply("❌ Произошла ошибка при обработке команды /start.")




@router.message(lambda message: message.text == "Меню Администратора")
async def handle_start_button(message: Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает нажатие кнопки "Меню". Отправляет админ-меню админам,
    или запрос пароля для неадминов.
    """
    logger.info(f"Пользователь {message.from_user.username or 'None'} (ID: {message.from_user.id}) нажал кнопку 'Меню'")
    user_id = message.from_user.id

    try:
        admin_status = await is_admin(user_id, db_session)
        logger.debug(f"Результат проверки администратора: {admin_status}")

        if admin_status:
            logger.debug("Пользователь является администратором. Отправка админ-меню.")
            await message.answer(
                "👋 Привет, администратор! Вот ваше меню:",
                reply_markup=get_admin_menu_keyboard()
            )
            logger.debug("Админ-меню отправлено")
        else:
            logger.debug("Пользователь не является администратором. Отправка запроса на пароль.")
            await message.answer("ℹ️ У вас нет доступа к админ-меню.\nВведите пароль администратора:")
            await state.set_state(PasswordStates.waiting_for_password)
    except Exception as e:
        logger.exception(f"Ошибка в обработчике handle_start_button: {e}")
        await message.reply("❌ Произошла ошибка при обработке кнопки 'Меню'.")




# Обработчик ввода пароля
@router.message(PasswordStates.waiting_for_password)
async def handle_password(message: Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает ввод пароля администратора.
    """
    entered_password = message.text.strip()
    correct_password = ADMIN_SECRET_PASSWORD  # Замените на ваш пароль

    if entered_password == correct_password:
        logger.info(f"Пользователь {message.from_user.username or 'None'} (ID: {message.from_user.id}) ввёл корректный пароль.")
        # Получаем username пользователя
        username = message.from_user.username
        new_admin = Admin(telegram_id=message.from_user.id, username=username)
        db_session.add(new_admin)
        try:
            await db_session.commit()
            logger.debug(f"Добавлен новый администратор: {message.from_user.id} с username={username}")
            await message.answer("✅ Доступ предоставлен. Вы теперь администратор.", reply_markup=get_admin_menu_keyboard())
        except Exception as e:
            await db_session.rollback()
            logger.exception(f"Ошибка при добавлении администратора в базу данных: {e}")
            await message.answer("❌ Произошла ошибка при добавлении вас в список администраторов.")
    else:
        logger.warning(f"Пользователь {message.from_user.username or 'None'} (ID: {message.from_user.id}) ввёл неверный пароль.")
        await message.answer("❌ Неверный пароль. Доступ запрещён.")

    # Сброс состояния
    await state.clear()



# Обработчик команды /start quiz_{message_id}
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

        # Отправляем опрос
        poll_message = await bot.send_poll(
            chat_id=message.chat.id,
            question=translation.question,
            options=translation.answers,
            type="quiz",
            correct_option_id=correct_option_id,
            is_anonymous=task.is_anonymous,
            allows_multiple_answers=task.allows_multiple_answers
        )

        # Если вы хотите сохранить poll_message_id, но у вас нет поля, вы можете закомментировать следующую строку
        # task.poll_message_id = poll_message.message_id  # Удалено, так как поля нет
        # await db_session.commit()

        logger.info(f"✅ Опрос отправлен для задачи ID {task.id} с message_id {poll_message.message_id}")

        await message.reply("✅ Опрос успешно отправлен.")

    except Exception as e:
        # Если вы не сохраняете poll_message_id, вы можете опустить откат транзакции
        # await db_session.rollback()
        logger.exception(f"❌ Ошибка при обработке команды /start quiz: {e}")
        await message.reply("❌ Произошла ошибка при запуске опроса.")