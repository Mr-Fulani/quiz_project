# bot/handlers/start.py

import logging
import os

from aiogram import Router, Bot, F
from aiogram.types import ContentType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from django.contrib.auth.hashers import make_password
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.reply_keyboards import get_start_reply_keyboard
from bot.states.admin_states import PasswordStates, RegistrationStates
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
            "👋 Привет! Со мной ты будешь развиваться.\nНажимай кнопку 'Меню' и погнали!",
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






@router.message(PasswordStates.waiting_for_password)
async def handle_password(message: Message, db_session: "AsyncSession", state: FSMContext):
    """
    Обрабатывает саморегистрацию администратора.

    Пользователь вводит секретный пароль. Если пароль верный,
    бот запрашивает данные в следующем формате:
      telegram_id, username, first_name, last_name, password

    Для саморегистрации фактический telegram_id берётся из профиля Telegram.
    Если введённое значение не совпадает – используется фактический.
    """
    try:
        entered_password = message.text.strip()
        correct_password = os.getenv("ADMIN_SECRET_PASSWORD")
        if entered_password == correct_password:
            await message.answer(
                "✅ Пароль верный. Пожалуйста, введите ваши данные в следующем формате:\n"
                "`telegram_id, username, first_name, last_name, password`\n\n"
                "Пример: `975113235, myusername, Ivan, Ivanov, mypassword`",
                parse_mode='Markdown'
            )
            await state.set_state(RegistrationStates.waiting_for_details)
        else:
            await message.answer("❌ Неверный пароль. Доступ запрещён.")
            await state.clear()
    except Exception as e:
        logger.exception("Ошибка в handle_password: %s", e)
        await message.answer("❌ Произошла ошибка. Попробуйте ещё раз.")
        await state.clear()






@router.message(RegistrationStates.waiting_for_details, F.content_type == ContentType.TEXT)
async def process_registration_details(message: Message, db_session: "AsyncSession", state: FSMContext):
    try:
        parts = [p.strip() for p in message.text.split(',')]
        if len(parts) != 5:
            raise ValueError("Неверное количество полей")
        telegram_id_input, username, first_name, last_name, raw_password = parts
        actual_telegram_id = message.from_user.id
        if str(actual_telegram_id) != telegram_id_input:
            logger.warning(
                "Введённый telegram_id (%s) не совпадает с вашим фактическим ID (%s). Будет использован фактический ID.",
                telegram_id_input, actual_telegram_id)
        telegram_id = actual_telegram_id

    except Exception as e:
        logger.error("Ошибка разбора данных для регистрации: %s", e)
        await message.reply(
            "❌ Неверный формат данных. Пожалуйста, введите данные в формате:\n"
            "`telegram_id, username, first_name, last_name, password`\n\n"
            "Пример: `975113235, myusername, Ivan, Ivanov, mypassword`"
        )
        return

    # Проверим, нет ли такого в admins:
    existing_admin = await db_session.execute(
        select(Admin).where(Admin.telegram_id == telegram_id)
    )
    if existing_admin.scalar_one_or_none():
        await message.answer("❌ Администратор с таким Telegram ID уже существует.")
        await state.clear()
        return

    try:
        new_admin = Admin(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            # используем make_password из django, если нужно шифрование
            password=make_password(raw_password),

            # Задаём дефолты, если у вас в БД стоит NOT NULL
            # и/или если хотите явно указать
            language="ru",
            is_active=True,
            is_django_admin=False,
            is_superuser=False,
            is_staff=False,
            is_super_admin=False,
            email="tguser@gmail.com",  # пустая строка вместо null
        )
        db_session.add(new_admin)
        await db_session.commit()

        await message.answer(
            "✅ Доступ предоставлен. Вы теперь администратор.",
            reply_markup=get_admin_menu_keyboard()
        )
    except IntegrityError as ie:
        await db_session.rollback()
        logger.error("IntegrityError при регистрации администратора: %s", ie)
        # Проверяем текст ошибки
        if "admins_telegram_id_key" in str(ie.orig):
            await message.answer("❌ Пользователь с таким Telegram ID уже существует.")
        else:
            await message.answer("❌ Ошибка: не удалось сохранить администратора (NOT NULL?).")
    except Exception as e:
        await db_session.rollback()
        logger.exception("Ошибка при регистрации администратора: %s", e)
        await message.answer("❌ Произошла ошибка при регистрации. Проверьте, что данные введены правильно.")
    finally:
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