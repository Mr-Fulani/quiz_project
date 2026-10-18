# bot/handlers/admin_menu.py
import asyncio
import datetime
import html
import logging
import os
import re
from datetime import datetime, timedelta

from aiogram import Router, F, Bot, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ContentType, FSInputFile, InlineKeyboardMarkup, \
    InlineKeyboardButton
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.database.models import Task, TelegramGroup, Topic, UserChannelSubscription
from bot.keyboards.quiz_keyboards import get_admin_menu_keyboard
from bot.keyboards.reply_keyboards import get_location_type_keyboard, get_start_reply_keyboard
from bot.services.admin_service import IsAdminFilter, is_admin
from bot.services.default_link_service import DefaultLinkService
from bot.services.deletion_service import delete_task_by_id
from bot.services.publication_service import publish_task_by_id, publish_task_by_translation_group
from bot.services.task_bd_status_service import get_task_status, get_zero_task_topics
from bot.services.topic_services import delete_topic_from_db, add_topic_to_db
from bot.states.admin_states import TaskActions, ChannelStates, AdminStates, \
    DefaultLinkStates
from bot.utils.languages_utils import LANGUAGE_MESSAGES
from bot.utils.markdownV2 import escape_markdown
from bot.utils.report_csv_generator import generate_zero_task_topics_text, generate_detailed_task_status_csv
from bot.utils.url_validator import is_valid_url

logger = logging.getLogger(__name__)
router = Router(name="admin_menu_router")
# Все хендлеры админ-меню (публикация, удаление задач, каналы, ссылки) — только для админов.
# Без фильтра любой мог прислать callback_data (например, "delete_task") и выполнить действие.
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())







@router.callback_query(F.data == "upload_json")
async def upload_json_handler(call: CallbackQuery, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Загрузить JSON".

    Запрашивает JSON-файл с задачами.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Загрузить JSON'")
    await call.message.answer("Загрузите JSON файл с задачами.")
    await call.answer()


@router.callback_query(F.data == "publish_by_id")
async def publish_by_id_handler(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки "Опубликовать по ID".

    Запрашивает ID задачи для публикации.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        state (FSMContext): Контекст состояния FSM.
    """
    logger.info(f"📢 Запрошена публикация задачи пользователем {call.from_user.id}")
    await state.set_state(TaskActions.awaiting_publish_id)
    await call.message.answer("📝 Пожалуйста, введите ID задачи для публикации:")
    await call.answer()


@router.callback_query(F.data == "delete_task")
async def delete_task_handler(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки "Удалить задачу по ID".

    Запрашивает ID задачи для удаления.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        state (FSMContext): Контекст состояния FSM.
    """
    logger.info(f"🗑️ Запрошено удаление задачи пользователем {call.from_user.id}")
    await state.set_state(TaskActions.awaiting_delete_id)
    await call.message.answer("📝 Введите ID задачи для удаления:")
    await call.answer()


@router.message(StateFilter(TaskActions.awaiting_publish_id), F.content_type == ContentType.TEXT)
async def handle_publish_id(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    """
    Обрабатывает ввод ID задачи для публикации.

    Публикует задачу по указанному ID.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        bot (Bot): Объект бота Aiogram.
    """
    current_state = await state.get_state()
    logger.debug(f"Текущее состояние (публикация): {current_state}")

    if not message.text or not message.text.isdigit():
        await message.answer("❌ Пожалуйста, введите корректный ID задачи (только цифры)")
        return

    task_id = int(message.text)
    logger.info(f"📢 Публикация задачи с ID: {task_id}")

    user_chat_id = message.chat.id

    try:
        success = await publish_task_by_id(task_id, message, db_session, bot, user_chat_id)
        if success:
            await message.answer(f"✅ Задача с ID {task_id} успешно опубликована!")
        else:
            await message.answer(f"❌ Не удалось опубликовать задачу с ID {task_id}.")
    except Exception as e:
        logger.error(f"Ошибка при публикации задачи {task_id}: {e}")
        await message.answer(f"❌ Произошла ошибка при публикации задачи: {str(e)}")

    await state.clear()


@router.message(StateFilter(TaskActions.awaiting_delete_id), F.content_type == ContentType.TEXT)
async def handle_delete_id(message: Message, state: FSMContext, db_session: AsyncSession):
    """
    Обработчик для удаления задачи по ID.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    current_state = await state.get_state()
    logger.debug(f"Текущее состояние (удаление): {current_state}")

    if not message.text or not message.text.isdigit():
        await message.answer("❌ Пожалуйста, введите корректный ID задачи (только цифры)")
        return

    task_id = int(message.text)
    logger.info(f"🗑️ Получен запрос на удаление задачи с ID: {task_id}")
    logger.debug(f"Получен запрос на удаление задачи с ID: {task_id}")

    try:
        deletion_info = await delete_task_by_id(task_id, db_session)
        if deletion_info:
            task_info = f"✅ Задачи с ID {', '.join(map(str, deletion_info['deleted_task_ids']))} успешно удалены!"
            topic_info = f"🏷️ Топик задач: {deletion_info['topic_name']}"
            translations_info = (
                f"🌍 Удалено переводов: {deletion_info['deleted_translation_count']}\n"
                f"📜 Языки переводов: {', '.join(deletion_info['deleted_translation_languages'])}\n"
                f"🏷️ Каналы: {', '.join(deletion_info['group_names'])}"
            )

            deleted_info = f"{task_info}\n{topic_info}\n{translations_info}"
            logger.debug(f"Информация об удалении:\n{deleted_info}")
            await message.answer(deleted_info)
        else:
            await message.answer(f"❌ Не удалось удалить задачу с ID {task_id}. Возможно, задача не найдена.")
    except Exception as e:
        logger.error(f"Ошибка при удалении задачи {task_id}: {e}")
        await message.answer(f"❌ Произошла ошибка при удалении задачи с ID {task_id}.")

    await state.clear()


@router.callback_query(F.data == "create_quiz")
async def create_quiz_handler(call: CallbackQuery, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Создать опрос".

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Создать опрос'")
    await call.message.answer("Функция создания опроса в разработке.")
    await call.answer()


@router.callback_query(F.data == "database_status")
async def handle_database_status(callback: CallbackQuery, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Состояние базы".

    Генерирует и отправляет CSV-отчёт о состоянии задач.

    Args:
        callback (CallbackQuery): Объект callback-запроса от Aiogram.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    try:
        unpublished_tasks, published_tasks, old_published_tasks, total_tasks, topics = await get_task_status(db_session)
        csv_path = await generate_detailed_task_status_csv(
            unpublished_tasks,
            published_tasks,
            old_published_tasks,
            total_tasks,
            topics,
            db_session
        )

        if csv_path is None:
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text="📝 В базе данных нет задач для отображения или произошла ошибка при генерации отчета."
            )
            await callback.answer("Отчет не был сгенерирован.", show_alert=True)
            return

        csv_file = FSInputFile(csv_path)
        await callback.message.answer_document(document=csv_file, caption="📄 Отчет о состоянии базы данных")
        os.remove(csv_path)
        logger.info(f"CSV отчет отправлен и удален: {csv_path}")
        await callback.answer("Отчет о состоянии базы данных отправлен.", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка при генерации отчета о состоянии базы данных: {e}")
        await callback.message.answer("❌ Произошла ошибка при генерации отчета о состоянии базы данных.")
        await callback.answer("Ошибка при генерации отчета.", show_alert=True)


@router.callback_query(F.data == "publish_task_with_translations")
async def publish_task_with_translations_handler(call: CallbackQuery, db_session: AsyncSession, bot: Bot):
    """
    Обрабатывает нажатие кнопки "Опубликовать задачу с переводами".

    Публикует самую старую неопубликованную задачу или задачу, опубликованную более месяца назад.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        bot (Bot): Объект бота Aiogram.
    """
    logger.info(f"🟢 Пользователь {call.from_user.username} (ID: {call.from_user.id}) начал процесс публикации задачи с переводами.")
    await call.message.answer(f"🟢 Процесс публикации задачи с переводами запущен для пользователя {call.from_user.username}.")

    logger.info("🔍 Поиск самой старой неопубликованной задачи...")
    await call.message.answer("🔍 Поиск самой старой неопубликованной задачи...")

    try:
        result = await db_session.execute(
            select(Task.translation_group_id)
            .where(Task.published.is_(False))
            .order_by(Task.id.asc())
            .limit(1)
        )
        translation_group_id = result.scalar_one_or_none()

        if not translation_group_id:
            logger.info("🔍 Не найдены неопубликованные задачи. Поиск задач, опубликованных более месяца назад...")
            await call.message.answer("🔍 Не найдены неопубликованные задачи. Поиск задач, опубликованных более месяца назад...")

            one_month_ago = datetime.now() - timedelta(days=30)
            result = await db_session.execute(
                select(Task.translation_group_id)
                .where(Task.published.is_(True))
                .where(Task.publish_date < one_month_ago)
                .order_by(Task.publish_date.asc())
                .limit(1)
            )
            translation_group_id = result.scalar_one_or_none()

        if translation_group_id:
            logger.info(f"🟡 Найдена задача с группой переводов {translation_group_id}. Начинаем публикацию.")
            user_chat_id = call.from_user.id
            success, published_count, failed_count, total_count = await publish_task_by_translation_group(
                translation_group_id, call.message, db_session, bot, user_chat_id
            )

            if success:
                logger.info(f"✅ Задача с группой переводов {translation_group_id} успешно опубликована.")
                logger.info(
                    f"📊 Результаты публикации: всего переводов — {total_count}, "
                    f"успешно опубликовано — {published_count}, с ошибками — {failed_count}."
                )
            else:
                logger.error(f"❌ Произошла ошибка при публикации задачи с группой переводов {translation_group_id}.")
        else:
            logger.info(
                "⚠️ Не найдены задачи для публикации: все задачи уже опубликованы или не требуют повторной публикации."
            )
            await call.message.answer("⚠️ Все задачи уже опубликованы или не требуют повторной публикации.")

        logger.info(f"🔚 Завершение публикации для пользователя {call.from_user.username} (ID: {call.from_user.id}).")
        await call.message.answer(f"🔚 Процесс публикации завершен для пользователя {call.from_user.username}.")
    except Exception as e:
        logger.exception(f"Ошибка при публикации задачи с переводами: {e}")
        await call.message.answer("❌ Произошла ошибка при процессе публикации задачи с переводами.")






@router.callback_query(lambda c: c.data == "add_channel_group_button")
async def callback_add_channel_group(call: types.CallbackQuery, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает нажатие кнопки "Добавить канал/группу". Начинает процесс добавления.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.message.answer("⛔ У вас нет прав для выполнения этой команды.")
        await call.answer()
        return

    logger.info(f"[AddChannelGroup] Пользователь {call.from_user.username or 'None'} (ID={call.from_user.id}) "
                f"нажал кнопку 'Добавить канал/группу'")
    await call.message.answer(
        "🔽 Начинаем добавление новой локации.\n"
        "1️⃣ Введите название (имя) канала или группы (супергруппы):"
    )
    await state.set_state(ChannelStates.waiting_for_group_name)
    await call.answer()


@router.message(ChannelStates.waiting_for_group_name)
async def process_group_name(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Сохраняет название (имя) канала/группы.

    Args:
        message (Message): Сообщение от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    group_name = message.text.strip()
    if not group_name:
        await message.reply("❌ Название не может быть пустым. Повторите ввод:")
        return

    await state.update_data(group_name=group_name)
    logger.info(f"[AddChannelGroup] Шаг1: получено group_name={group_name}")

    await message.answer(
        "2️⃣ Введите Telegram ID (начинается с -100...), например: -1001234567890"
    )
    await state.set_state(ChannelStates.waiting_for_group_id)


@router.message(ChannelStates.waiting_for_group_id)
async def process_group_id(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Сохраняет Telegram ID канала/группы.

    Args:
        message (Message): Сообщение от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    group_id_text = message.text.strip()
    if not re.match(r'^-100\d+$', group_id_text):
        await message.reply("❌ Неверный формат. ID должен начинаться с -100 и содержать цифры. Повторите ввод:")
        return

    group_id = int(group_id_text)
    await state.update_data(group_id=group_id)
    logger.info(f"[AddChannelGroup] Шаг2: получен group_id={group_id}")

    await message.answer(
        "3️⃣ Введите название темы (Topic), например: 'Python', 'Golang', 'Java'."
    )
    await state.set_state(ChannelStates.waiting_for_topic)


@router.message(ChannelStates.waiting_for_topic)
async def process_topic_name(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Сохраняет тему канала/группы. Если тема не существует, предлагает создать новую.

    Args:
        message (Message): Сообщение от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    topic_name = message.text.strip()
    if not topic_name:
        await message.reply("❌ Тема не может быть пустой. Повторите ввод:")
        return

    result = await db_session.execute(select(Topic).where(Topic.name.ilike(topic_name)))
    topic = result.scalar_one_or_none()

    if not topic:
        await state.update_data(topic_name=topic_name)
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="Да, создать тему")],
                [types.KeyboardButton(text="Нет, отменить добавление")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            f"❓ Тема '{topic_name}' не найдена. Создать новую тему?",
            reply_markup=keyboard
        )
        await state.set_state(ChannelStates.waiting_for_topic_creation)
    else:
        await state.update_data(topic_id=topic.id)
        logger.info(f"[AddChannelGroup] Тема '{topic_name}' найдена, ID={topic.id}")

        await message.answer(
            "4️⃣ Введите язык канала/группы (2-3 буквы), например: 'ru', 'en', 'tr'.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(ChannelStates.waiting_for_language)


@router.message(ChannelStates.waiting_for_topic_creation)
async def process_topic_creation(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Создаёт новую тему, если администратор выбрал "Да, создать тему".

    Args:
        message (Message): Сообщение от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    decision = message.text.strip().lower()
    if decision == "да, создать тему":
        data = await state.get_data()
        new_topic_name = data.get("topic_name")

        new_topic = Topic(name=new_topic_name)
        db_session.add(new_topic)
        try:
            await db_session.commit()
            res = await db_session.execute(select(Topic).where(Topic.name.ilike(new_topic_name)))
            created_topic = res.scalar_one()
            await state.update_data(topic_id=created_topic.id)

            logger.info(f"[AddChannelGroup] Тема '{new_topic_name}' создана, ID={created_topic.id}")

            await message.answer(
                f"✅ Тема '{new_topic_name}' успешно создана.\n"
                "4️⃣ Введите язык канала/группы (например, 'ru'):"
            )
            await state.set_state(ChannelStates.waiting_for_language)
        except Exception as e:
            await db_session.rollback()
            logger.error(f"[AddChannelGroup] Ошибка при создании темы '{new_topic_name}': {e}")
            await message.reply("❌ Ошибка при создании темы. Попробуйте ещё раз.")
            await state.clear()

    elif decision == "нет, отменить добавление":
        await message.reply(
            "❌ Добавление локации отменено.",
            reply_markup=get_admin_menu_keyboard()
        )
        await state.clear()
    else:
        await message.reply("❌ Выберите: 'Да, создать тему' или 'Нет, отменить добавление'.")


@router.message(ChannelStates.waiting_for_language)
async def process_language(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Сохраняет язык канала/группы (например, 'ru', 'en', 'tr').

    Args:
        message (Message): Сообщение от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    language = message.text.strip().lower()
    if not re.match(r'^[a-z]{2,3}$', language):
        await message.reply("❌ Некорректный формат языка ('ru', 'en', 'tr'). Повторите ввод:")
        return

    await state.update_data(language=language)
    logger.info(f"[AddChannelGroup] Шаг4: язык={language}")

    await message.answer(
        "5️⃣ Выберите тип локации:",
        reply_markup=get_location_type_keyboard()
    )
    await state.set_state(ChannelStates.waiting_for_location_type)


@router.message(ChannelStates.waiting_for_location_type)
async def process_location_type(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Сохраняет тип локации (channel или group).

    Args:
        message (Message): Сообщение от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    loc_type = message.text.strip().lower()
    if loc_type not in ["channel", "group"]:
        await message.reply("❌ Некорректный выбор. Пожалуйста, выберите 'channel' или 'group':")
        return

    await state.update_data(location_type=loc_type)
    logger.info(f"[AddChannelGroup] Шаг5: location_type={loc_type}")

    await message.answer(
        "6️⃣ Введите username канала/группы (без @).\n"
        "Если у локации нет username, введите '-' или оставьте поле пустым."
    )
    await state.set_state(ChannelStates.waiting_for_channel_username)


@router.message(ChannelStates.waiting_for_channel_username)
async def process_channel_username(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Сохраняет username канала/группы. Если введено "-", сохраняется как None.
    Проверяет корректность формата username и предупреждает о допустимых символах.
    В случае ошибки или отката удаляет текущие кнопки и возвращает кнопки главного меню.

    Args:
        message (Message): Сообщение от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    try:
        uname_input = message.text.strip()
        if uname_input in ["-", ""]:
            uname_input = None
        elif uname_input.startswith("@"):
            uname_input = uname_input[1:].strip()

        if uname_input and not re.match(r'^[A-Za-z0-9_]{5,32}$', uname_input):
            instructions = (
                "❌ Некорректный формат username.\n\n"
                "Требования к username:\n"
                "- Длина: от 5 до 32 символов\n"
                "- Допустимые символы: латинские буквы (A-Z, a-z), цифры (0-9) и нижнее подчеркивание (_)\n"
                "- Специальные символы (!@#$ и т.д.) не допускаются\n\n"
                "Пожалуйста, повторите ввод:"
            )
            await message.reply(instructions)
            return

        await state.update_data(username=uname_input)
        logger.info(f"[AddChannelGroup] Шаг6: username={uname_input or '—'}")

        data = await state.get_data()
        await create_group_or_channel_record(message, db_session, state, data)

    except Exception as e:
        logger.error(f"[AddChannelGroup] Ошибка при обработке username: {e}")
        # Удаляем текущие кнопки и возвращаем главное меню
        markup = await get_start_reply_keyboard(message.from_user.id, db_session)
        await message.reply(
            "❌ Произошла ошибка при обработке данных. Возврат в главное меню.",
            reply_markup=markup
        )
        # Сбрасываем состояние FSM
        await state.clear()


async def create_group_or_channel_record(
    message: types.Message,
    db_session: AsyncSession,
    state: FSMContext,
    data: dict
):
    """
    Создаёт запись в таблице TelegramGroup для нового канала или группы.

    Args:
        message (Message): Сообщение от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
        data (dict): Данные, собранные в процессе добавления (group_name, group_id, topic_id, language, location_type, username).
    """
    group_name = data.get("group_name")
    group_id = data.get("group_id")
    topic_id = data.get("topic_id")
    language = data.get("language")
    location_type = data.get("location_type")
    username = data.get("username")

    res = await db_session.execute(select(Topic).where(Topic.id == topic_id))
    topic = res.scalar_one_or_none()
    if not topic:
        await message.reply(f"❌ Ошибка: тема c ID={topic_id} не найдена.")
        await state.clear()
        return

    res = await db_session.execute(select(TelegramGroup).where(TelegramGroup.group_id == group_id))
    existing_group = res.scalar_one_or_none()
    if existing_group:
        await message.reply(f"❌ Локация с ID {group_id} уже существует!")
        await state.clear()
        return

    new_group = TelegramGroup(
        group_name=group_name,
        group_id=group_id,
        topic_id=topic.id,
        language=language,
        location_type=location_type,
        username=username
    )
    db_session.add(new_group)

    try:
        await db_session.commit()
        logger.info(f"[AddChannelGroup] Создана локация '{group_name}' (ID={group_id}), username={username or '—'}")
        await message.answer(
            f"✅ {location_type.capitalize()} '{group_name}' успешно добавлен в базу.\n"
            f"ID: {group_id}\n"
            f"Username: {username or '—'}\n"
            f"Тема: {topic.name}\n"
            f"Язык: {language}",
            reply_markup=get_start_reply_keyboard()
        )
    except Exception as e:
        await db_session.rollback()
        logger.error(f"[AddChannelGroup] Ошибка при добавлении '{group_name}': {e}")
        await message.reply("❌ Произошла ошибка при добавлении. Попробуйте ещё раз.")

    await state.clear()


@router.callback_query(lambda c: c.data == "remove_channel_button")
async def callback_remove_channel(call: types.CallbackQuery, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает нажатие кнопки "Удалить канал". Начинает процесс удаления канала.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    logger.info(
        f"Пользователь {call.from_user.username or 'None'} (ID: {call.from_user.id}) нажал кнопку 'Удалить канал'"
    )

    await call.message.answer(
        "🔽 Начнём удаление канала.\nВведите Telegram ID канала, который хотите удалить (начинается с -100):")
    await state.set_state(ChannelStates.waiting_for_remove_group_id)
    await call.answer()


@router.message(ChannelStates.waiting_for_remove_group_id)
async def process_remove_group_id(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает ввод Telegram ID канала для удаления.
    """
    group_id_text = message.text.strip()
    if not re.match(r'^-100\d+$', group_id_text):
        await message.reply(
            "❌ Некорректный формат Telegram ID. Он должен начинаться с -100 и содержать цифры после него.\nПожалуйста, введите корректный Telegram ID канала:")
        return

    group_id = int(group_id_text)
    await state.update_data(group_id=group_id)
    logger.info(f"Введён Telegram ID канала для удаления: {group_id}")

    result = await db_session.execute(select(TelegramGroup).where(TelegramGroup.group_id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        await message.reply(f"❌ Канал с ID {group_id} не найден в базе данных.")
        await state.clear()
        return

    try:
        # Удаляем связанные подписки
        await db_session.execute(
            delete(UserChannelSubscription).where(UserChannelSubscription.channel_id == group.group_id)
        )
        # Удаляем связанные задачи
        await db_session.execute(
            delete(Task).where(Task.group_id == group.id)
        )
        # Удаляем канал
        await db_session.execute(
            delete(TelegramGroup).where(TelegramGroup.group_id == group.group_id)
        )
        await db_session.commit()
        logger.info(f"Канал '{group.group_name}' (ID: {group_id}) успешно удалён.")
        await message.answer(f"✅ Канал '{group.group_name}' (ID: {group_id}) успешно удалён из базы данных.")
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Ошибка при удалении канала: {e}")
        await message.reply("❌ Произошла ошибка при удалении канала. Попробуйте ещё раз.")

    await state.clear()


@router.callback_query(lambda c: c.data == "list_channels_groups_button")
async def callback_list_channels_groups(call: CallbackQuery, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Список каналов и групп".
    Отправляет отсортированный по названиям список каналов и групп.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    logger.info(
        f"Пользователь {call.from_user.username or 'None'} (ID: {call.from_user.id}) "
        f"нажал кнопку 'Список каналов и групп'"
    )

    try:
        query = select(TelegramGroup)
        result = await db_session.execute(query)
        groups = result.scalars().all()

        if not groups:
            channels_groups_list = (
                "📭 <b>Список каналов и групп:</b>\n\n"
                "📭 Нет добавленных каналов или групп."
            )
        else:
            def sort_key(x):
                name = x.group_name.lower()
                main_word = name.split()[0]
                return (main_word, name)

            channels = sorted(
                [g for g in groups if g.location_type.lower() == "channel"],
                key=sort_key
            )
            groups_only = sorted(
                [g for g in groups if g.location_type.lower() == "group"],
                key=sort_key
            )

            channels_list = ""
            groups_list = ""

            if channels:
                channels_list += "📢 <b>Каналы:</b>\n"
                for channel in channels:
                    channel_name_html = html.escape(channel.group_name or "Без имени")
                    channel_id = channel.group_id
                    channel_language = html.escape(channel.language) if channel.language else "Не указан"
                    if channel.username:
                        username_escaped = html.escape(channel.username)
                        link = f'<a href="https://t.me/{username_escaped}">{channel_name_html}</a>'
                    else:
                        link = channel_name_html
                    channels_list += f"• {link} (ID: {channel_id}) - Язык: {channel_language}\n"
                channels_list += "\n"

            if groups_only:
                groups_list += "👥 <b>Группы:</b>\n"
                for group in groups_only:
                    group_name_html = html.escape(group.group_name or "Без имени")
                    group_id = group.group_id
                    group_language = html.escape(group.language) if group.language else "Не указан"
                    if group.username:
                        username_escaped = html.escape(group.username)
                        link = f'<a href="https://t.me/{username_escaped}">{group_name_html}</a>'
                    else:
                        link = group_name_html
                    groups_list += f"• {link} (ID: {group_id}) - Язык: {group_language}\n"
                groups_list += "\n"

            channels_groups_list = (
                "📭 <b>Список каналов и групп:</b>\n\n"
                f"{channels_list}{groups_list}"
            )

        logger.debug(f"Сформированный список каналов и групп:\n{channels_groups_list}")
        await call.message.answer(channels_groups_list, parse_mode='HTML')
        await call.answer()
        logger.debug("Отсортированный список каналов и групп отправлен пользователю.")
    except TelegramBadRequest as e:
        logger.error(f"Ошибка Telegram в callback_list_channels_groups: {e}")
        await call.message.answer("❌ Произошла ошибка при отправке списка каналов и групп.")
        await call.answer()
    except Exception as e:
        logger.exception(f"Неизвестная ошибка в callback_list_channels_groups: {e}")
        await call.message.answer("❌ Произошла непредвиденная ошибка.")
        await call.answer()





@router.callback_query(lambda c: c.data == "zero_task_topics_report")
async def handle_zero_task_topics_report(callback_query: types.CallbackQuery, db_session: AsyncSession):
    """
    Обработчик для кнопки "Отчет топиков без задач".
    Генерирует текстовый отчет и отправляет его администратору.

    Args:
        callback_query (CallbackQuery): Объект callback-запроса от Aiogram.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    user_id = callback_query.from_user.id
    if not await is_admin(user_id, db_session):
        await callback_query.answer("У вас нет доступа к этой команде.", show_alert=True)
        logger.warning(f"Пользователь с ID {user_id} попытался получить доступ к отчету без прав.")
        return

    logger.info(f"Пользователь {callback_query.from_user.username} запросил отчет топиков без задач.")

    await callback_query.answer("Генерация отчета...", show_alert=True)

    try:
        zero_task_topics = await get_zero_task_topics(db_session)
        report_path = await generate_zero_task_topics_text(zero_task_topics)

        if report_path:
            absolute_path = os.path.abspath(report_path)
            logger.debug(f"Абсолютный путь к отчету: {absolute_path}")

            if not os.path.isfile(absolute_path):
                logger.error(f"Файл отчета не найден по пути: {absolute_path}")
                await callback_query.message.answer("❌ Не удалось найти сгенерированный отчет.")
                return

            report_file = FSInputFile(absolute_path)
            await callback_query.message.answer_document(
                document=report_file,
                caption="📊 *Отчет топиков без задач:*",
                parse_mode="Markdown"
            )
            logger.info(f"Отчет топиков без задач отправлен пользователю {callback_query.from_user.username}.")

            try:
                os.remove(absolute_path)
                logger.debug(f"Файл отчета удален: {absolute_path}")
            except Exception as e:
                logger.error(f"Не удалось удалить файл отчета: {absolute_path}. Ошибка: {e}")
        else:
            await callback_query.message.answer(
                "ℹ️ Все топики имеют хотя бы одну задачу или произошла ошибка при генерации отчета."
            )
            logger.warning("Отчет топиков без задач не был сгенерирован или отправлен.")
    except Exception as e:
        logger.error(f"Ошибка при генерации или отправке отчета: {e}")
        await callback_query.message.answer("❌ Произошла ошибка при генерации или отправке отчета.")


@router.callback_query(lambda c: c.data == "add_topic")
async def handle_add_topic(callback_query: types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Обработчик для кнопки "Добавить топик".

    Args:
        callback_query (CallbackQuery): Объект callback-запроса от Aiogram.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    user_id = callback_query.from_user.id
    if not await is_admin(user_id, db_session):
        await callback_query.answer("У вас нет доступа к этой команде.", show_alert=True)
        logger.warning(f"Пользователь с ID {user_id} попытался добавить топик без прав.")
        return

    await callback_query.message.answer("Пожалуйста, введите название топика для добавления:")
    await state.set_state(AdminStates.waiting_for_topic_name)
    await callback_query.answer()
    logger.info(f"Пользователь {callback_query.from_user.username} инициировал добавление топика.")


@router.message(AdminStates.waiting_for_topic_name)
async def process_add_topic(message: types.Message, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает ввод названия топика для добавления.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    topic_name = message.text.strip()
    if not topic_name:
        await message.answer("Название топика не может быть пустым. Пожалуйста, введите корректное название:")
        return

    try:
        new_topic = await add_topic_to_db(db_session, topic_name)
        await message.answer(
            f"✅ Топик '{new_topic.name}' (ID: {new_topic.id}) успешно добавлен в базу данных.",
            reply_markup=get_admin_menu_keyboard()
        )
        logger.info(
            f"Топик '{new_topic.name}' (ID: {new_topic.id}) добавлен пользователем {message.from_user.username}."
        )
    except ValueError as ve:
        await message.answer(f"❌ {ve}")
    except Exception as e:
        logger.error(f"Ошибка при добавлении топика '{topic_name}': {e}")
        await message.answer(f"❌ Произошла ошибка при добавлении топика '{topic_name}'.")

    await state.clear()


@router.callback_query(lambda c: c.data == "delete_topic")
async def handle_delete_topic(callback_query: types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Обработчик для кнопки "Удалить топик".

    Args:
        callback_query (CallbackQuery): Объект callback-запроса от Aiogram.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    user_id = callback_query.from_user.id
    if not await is_admin(user_id, db_session):
        await callback_query.answer("У вас нет доступа к этой команде.", show_alert=True)
        logger.warning(f"Пользователь с ID {user_id} попытался удалить топик без прав.")
        return

    await callback_query.message.answer("Пожалуйста, введите ID топика для удаления:")
    await state.set_state(AdminStates.waiting_for_topic_id)
    await callback_query.answer()
    logger.info(f"Пользователь {callback_query.from_user.username} инициировал удаление топика.")


@router.message(AdminStates.waiting_for_topic_id)
async def process_delete_topic(message: types.Message, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает ввод ID топика для удаления.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    topic_id_str = message.text.strip()
    if not topic_id_str.isdigit():
        await message.answer("ID топика должен быть числом. Пожалуйста, введите корректный ID:")
        return

    topic_id = int(topic_id_str)

    try:
        deleted_topic = await delete_topic_from_db(db_session, topic_id)
        if deleted_topic:
            await message.answer(
                f"✅ Топик '{deleted_topic.name}' (ID: {deleted_topic.id}) успешно удалён из базы данных.",
                reply_markup=get_admin_menu_keyboard()
            )
            logger.info(
                f"Топик '{deleted_topic.name}' (ID: {deleted_topic.id}) удалён пользователем {message.from_user.username}."
            )
        else:
            await message.answer(
                f"❌ Топик с ID {topic_id} не найден.", reply_markup=get_admin_menu_keyboard()
            )
            logger.warning(f"Пользователь {message.from_user.username} попытался удалить несуществующий топик с ID {topic_id}.")
    except Exception as e:
        logger.error(f"Ошибка при удалении топика с ID {topic_id}: {e}")
        await message.answer(f"❌ Произошла ошибка при удалении топика с ID {topic_id}.")

    await state.clear()


@router.callback_query(F.data == "add_default_link")
async def callback_add_default_link(call: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Добавить ссылку".

    Запрашивает язык для новой ссылки.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал кнопку 'Добавить ссылку'")
    await call.message.answer("Начинаем добавление ссылки. 📌 Введите язык для ссылки (например, 'en', 'ru', 'tr'):")
    await state.set_state(DefaultLinkStates.waiting_for_language)
    await call.answer()


@router.message(DefaultLinkStates.waiting_for_language, F.content_type == ContentType.TEXT)
async def process_default_link_language(message: Message, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает ввод языка для добавления ссылки.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    language = message.text.strip().lower()
    if not re.match(r'^[a-z]{2,3}$', language):
        await message.reply("❌ Некорректный формат языка. Попробуйте ещё раз.")
        return
    logger.info(f"Получен язык для ссылки: {language}")
    await state.update_data(language=language)
    await message.reply("📌 Введите тему для ссылки:")
    await state.set_state(DefaultLinkStates.waiting_for_topic)


@router.message(DefaultLinkStates.waiting_for_topic, F.content_type == ContentType.TEXT)
async def process_default_link_topic(message: Message, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает ввод темы для добавления ссылки.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    topic = message.text.strip()
    if not topic:
        await message.reply("❌ Тема не может быть пустой. Попробуйте ещё раз.")
        return
    logger.info(f"Получена тема для ссылки: {topic}")
    await state.update_data(topic=topic)
    await message.reply("🔗 Введите ссылку для этой комбинации языка и темы:")
    await state.set_state(DefaultLinkStates.waiting_for_link)


@router.message(DefaultLinkStates.waiting_for_link, F.content_type == ContentType.TEXT)
async def process_default_link_link(message: types.Message, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает ввод ссылки для добавления.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    link = message.text.strip()
    if not is_valid_url(link):
        await message.reply("❌ Некорректный URL. Попробуйте ещё раз.")
        return
    data = await state.get_data()
    language = data.get("language")
    topic = data.get("topic")
    logger.info(f"Попытка добавить ссылку: Язык={language}, Тема={topic}, Ссылка={link}")
    try:
        default_link_service = DefaultLinkService(db_session)
        await default_link_service.add_default_link(language, topic, link)
        escaped_language = escape_markdown(language)
        escaped_topic = escape_markdown(topic)
        escaped_link = escape_markdown(link)
        reply_text = (
            f"✅ Ссылка успешно добавлена:\n"
            f"Язык: `{escaped_language}`\n"
            f"Тема: `{escaped_topic}`\n"
            f"Ссылка: {escaped_link}"
        )
        await message.reply(reply_text, parse_mode="MarkdownV2")
        logger.info(f"Успешно добавлена ссылка: Язык={language}, Тема={topic}, Ссылка={link}")
    except Exception as e:
        await message.reply("❌ Произошла ошибка при добавлении ссылки.")
        logger.error(f"Ошибка при добавлении ссылки: {e}")
    await state.clear()


@router.callback_query(F.data == "remove_default_link")
async def callback_remove_default_link(call: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Удалить ссылку".

    Запрашивает язык для удаления ссылки.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал кнопку 'Удалить ссылку'")
    await call.message.answer("Начинаем удаление ссылки. 📌 Введите язык для удаления ссылки (например, 'en', 'ru', 'tr'):")
    await state.set_state(DefaultLinkStates.waiting_for_remove_language)
    await call.answer()


@router.message(DefaultLinkStates.waiting_for_remove_language, F.content_type == ContentType.TEXT)
async def process_remove_default_link_language(message: Message, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает ввод языка для удаления ссылки.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    language = message.text.strip().lower()
    if not re.match(r'^[a-z]{2,3}$', language):
        await message.reply("❌ Некорректный формат языка. Попробуйте ещё раз.")
        return
    logger.info(f"Получен язык для удаления ссылки: {language}")
    await state.update_data(language=language)
    await message.reply("📌 Введите тему для удаления ссылки:")
    await state.set_state(DefaultLinkStates.waiting_for_remove_topic)


@router.message(DefaultLinkStates.waiting_for_remove_topic, F.content_type == ContentType.TEXT)
async def process_remove_default_link_topic(message: Message, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает ввод темы для удаления ссылки.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    topic = message.text.strip()
    if not topic:
        await message.reply("❌ Тема не может быть пустой. Попробуйте ещё раз.")
        return
    data = await state.get_data()
    language = data.get("language")
    logger.info(f"Попытка удалить ссылку: Язык={language}, Тема={topic}")
    try:
        default_link_service = DefaultLinkService(db_session)
        success = await default_link_service.remove_default_link(language, topic)
        if success:
            await message.reply(f"✅ Ссылка удалена:\nЯзык: `{language}`\nТема: `{topic}`", parse_mode="MarkdownV2")
            logger.info(f"Успешно удалена ссылка: Язык={language}, Тема={topic}")
        else:
            await message.reply(f"❌ Ссылка не найдена:\nЯзык: `{language}`\nТема: `{topic}`", parse_mode="MarkdownV2")
            logger.warning(f"Ссылка для удаления не найдена: Язык={language}, Тема={topic}")
    except Exception as e:
        await message.reply("❌ Произошла ошибка при удалении ссылки.")
        logger.error(f"Ошибка при удалении ссылки: {e}")
    await state.clear()


@router.callback_query(F.data == "list_default_links")
async def callback_list_default_links(call: CallbackQuery, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Список ссылок".

    Отправляет список всех ссылок по умолчанию.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) запросил список ссылок")
    try:
        default_link_service = DefaultLinkService(db_session)
        default_links = await default_link_service.list_default_links()
        if not default_links:
            await call.message.answer("📭 Ссылки по умолчанию не найдены.")
            logger.info("Список ссылок пуст.")
        else:
            message = "📋 **Список ссылок по умолчанию:**\n\n"
            for link in default_links:
                escaped_language = escape_markdown(link.language)
                escaped_topic = escape_markdown(link.topic)
                escaped_link = escape_markdown(link.link)
                message += f"• Язык: `{escaped_language}`, Тема: `{escaped_topic}`, Ссылка: {escaped_link}\n"
            await call.message.answer(message, parse_mode="MarkdownV2")
            logger.info("Список ссылок успешно отправлен.")
    except Exception as e:
        await call.message.answer("❌ Произошла ошибка при получении списка ссылок.")
        logger.error(f"Ошибка при получении списка ссылок: {e}")
    await call.answer()


async def validate_chat(bot, username):
    """
    Проверяет доступность чата по username.

    Args:
        bot: Объект бота Aiogram.
        username (str): Username чата (без @).

    Returns:
        bool: True, если чат доступен, иначе False.
    """
    try:
        await bot.get_chat(f"@{username}")
        return True
    except Exception as e:
        logger.error(f"Чат с username @{username} недоступен: {e}")
        return False


@router.callback_query(F.data == "post_subscription_buttons")
async def post_subscription_buttons(call: types.CallbackQuery, db_session, bot):
    """
    Обработчик для публикации и закрепления кнопок с подписками на всех каналах/группах.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        db_session: Асинхронная сессия SQLAlchemy.
        bot: Объект бота Aiogram.
    """
    admin_id = call.from_user.id

    if not await is_admin(admin_id, db_session):
        await call.message.reply("❌ У вас нет прав для выполнения этого действия.")
        await call.answer()
        return

    await call.answer("Начинаю отправку сообщений...")

    result = await db_session.execute(
        select(TelegramGroup.group_name, TelegramGroup.username, TelegramGroup.group_id, TelegramGroup.location_type, TelegramGroup.language)
        .where(TelegramGroup.username.isnot(None))
    )
    destinations = result.all()

    if not destinations:
        await call.message.reply("Нет данных о каналах или группах в базе.")
        return

    for group_name, username, group_id, location_type, language in destinations:
        if not await validate_chat(bot, username):
            logger.warning(f"Пропускаем недоступный чат: @{username}")
            continue

        messages = LANGUAGE_MESSAGES.get(language, LANGUAGE_MESSAGES["en"])
        message_text = messages["message_text"]

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=LANGUAGE_MESSAGES[language]["button_text"].format(group_name=destination_group_name),
                        url=f"https://t.me/{destination_username}"
                    )
                ]
                for destination_group_name, destination_username, _, _, _ in destinations
            ]
        )

        try:
            sent_message = await bot.send_message(
                chat_id=group_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            logger.info(f"Сообщение отправлено в {location_type} '{group_name}' ({group_id}).")
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение в {location_type} '{group_name}' ({group_id}): {e}")

        await asyncio.sleep(3)

    await call.message.reply("✅ Сообщения успешно отправлены.")


@router.callback_query(lambda c: c.data == "set_main_fallback_link")
async def callback_set_main_fallback_link(call: types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Установить главную ссылку".
    Запрашивает у администратора выбор языка для установки ссылки.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.answer("У вас нет доступа к этой команде.", show_alert=True)
        logger.warning(f"Пользователь с ID {user_id} попытался установить главную ссылку без прав.")
        return

    await call.message.answer("Пожалуйста, введите язык, для которого хотите установить главную статическую ссылку (например, 'en', 'ru'):")
    await state.set_state(AdminStates.waiting_for_set_fallback_language)
    await call.answer()
    logger.info(f"Пользователь {call.from_user.username} инициировал установку главной статической ссылки.")


@router.message(AdminStates.waiting_for_set_fallback_language)
async def process_set_fallback_language(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает ввод языка для установки главной статической ссылки.

    Args:
        message (Message): Сообщение от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    user_id = message.from_user.id
    if not await is_admin(user_id, db_session):
        await message.answer("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь с ID {user_id} попытался установить главную ссылку без прав.")
        await state.clear()
        return

    language = message.text.strip().lower()
    if not language.isalpha():
        await message.answer("Пожалуйста, введите корректный язык (только буквы, например, 'en', 'ru').")
        return

    await state.update_data(set_fallback_language=language)
    await message.answer(f"Пожалуйста, введите новую главную статическую ссылку для языка '{language}' (начинающуюся с http:// или https://):")
    await state.set_state(AdminStates.waiting_for_set_fallback_link)
    logger.info(f"Пользователь {message.from_user.username} выбрал язык '{language}' для установки главной статической ссылки.")


@router.message(AdminStates.waiting_for_set_fallback_link)
async def process_set_main_fallback_link(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает ввод новой главной статической ссылки.

    Args:
        message (Message): Сообщение от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    user_id = message.from_user.id
    if not await is_admin(user_id, db_session):
        await message.answer("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь с ID {user_id} попытался установить главную ссылку без прав.")
        await state.clear()
        return

    new_link = message.text.strip()
    if not (new_link.startswith("http://") or new_link.startswith("https://")):
        await message.answer("Пожалуйста, введите корректный URL (начинающийся с http:// или https://).")
        return

    if not is_valid_url(new_link):
        await message.answer("Пожалуйста, введите корректный URL.")
        return

    data = await state.get_data()
    language = data.get("set_fallback_language")

    default_link_service = DefaultLinkService(db_session)
    try:
        fallback_link = await default_link_service.set_main_fallback_link(language, new_link)
        await message.answer(f"✅ Главная статическая ссылка для языка '{language}' успешно установлена: [Ссылка]({fallback_link.link})", parse_mode='Markdown', disable_web_page_preview=False)
        logger.info(f"Пользователь {message.from_user.username} установил главную статическую ссылку для языка '{language}': {fallback_link.link}")
    except Exception as e:
        await message.answer("❌ Произошла ошибка при установке главной статической ссылки.")
        logger.error(f"Ошибка при установке главной статической ссылки: {e}")

    await state.clear()


@router.callback_query(lambda c: c.data == "remove_main_fallback_link")
async def callback_remove_main_fallback_link(call: types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Удалить главную ссылку".
    Запрашивает у администратора выбор языка для удаления ссылки.

    Args:
        call (CallbackQuery): Объект callback-запроса от Aiogram.
        state (FSMContext): Контекст состояния FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.answer("У вас нет доступа к этой команде.", show_alert=True)
        logger.warning(f"Пользователь с ID {user_id} попытался удалить главную ссылку без прав.")
        return

    await call.message.answer("Пожалуйста, введите язык, для которого хотите удалить главную статическую ссылку (например, 'en', 'ru'):")
    await state.set_state(AdminStates.waiting_for_remove_fallback_language)
    await call.answer()
    logger.info(f"Пользователь {call.from_user.username} инициировал удаление главной статической ссылки.")






@router.message(AdminStates.waiting_for_remove_fallback_language)
async def process_remove_fallback_language(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает ввод языка для удаления главной статической ссылки.

    Args:
        message (Message): Сообщение от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        state (FSMContext): Контекст состояния FSM.
    """
    user_id = message.from_user.id
    if not await is_admin(user_id, db_session):
        await message.answer("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь с ID {user_id} попытался удалить главную ссылку без прав.")
        await state.clear()
        return

    language = message.text.strip().lower()
    if not language.isalpha():
        await message.answer("Пожалуйста, введите корректный язык (только буквы, например, 'en', 'ru').")
        return

    default_link_service = DefaultLinkService(db_session)
    success = await default_link_service.remove_main_fallback_link(language)
    if success:
        await message.answer(
            f"✅ Главная статическая ссылка для языка '{language}' успешно удалена.",
            reply_markup=get_admin_menu_keyboard()
        )
        logger.info(f"Пользователь {message.from_user.username} удалил главную статическую ссылку для языка '{language}'.")
    else:
        await message.answer(
            f"❌ Главная статическая ссылка для языка '{language}' не найдена.",
            reply_markup=get_admin_menu_keyboard()
        )
        logger.warning(f"Главная статическая ссылка для языка '{language}' не найдена пользователем {message.from_user.username}.")

    await state.clear()


# Обработчик кнопки "Получить главную ссылку"
@router.callback_query(lambda c: c.data == "get_main_fallback_link")
async def callback_get_main_fallback_link(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Получить главную ссылку".
    Выводит списком все главные статические ссылки с указанием языка.
    """
    # Первый ответ на callback, чтобы уведомить телеграм что кнопка обрабатывается
    # и предупредить индикатор загрузки
    await call.answer("Получаем главные ссылки...")

    user_id = call.from_user.id
    logger.info(f"Запрос на получение главных ссылок от пользователя {user_id}")

    if not await is_admin(user_id, db_session):
        await call.answer("У вас нет доступа к этой команде.", show_alert=True)
        logger.warning(f"Пользователь с ID {user_id} попытался получить главную ссылку без прав.")
        return

    logger.debug(f"Пользователь {user_id} прошел проверку прав доступа, продолжаем...")
    default_link_service = DefaultLinkService(db_session)

    try:
        # Добавляем логирования для отладки
        logger.debug("Начинаем запрос all_main_fallback_links...")

        # Получаем все главные статические ссылки
        main_links = await default_link_service.get_all_main_fallback_links()
        logger.debug(f"Получены ссылки: {main_links}")

        if main_links:
            message_text = "📌 **Главные статические ссылки по языкам:**\n\n"
            for link in main_links:
                # Используем emoji флагов для наглядности (опционально)
                flag_emoji = get_flag_emoji(link.language)
                message_text += f"{flag_emoji} *{link.language}*: [Ссылка]({link.link})\n"

            logger.debug(f"Подготовлен текст сообщения: {message_text}")

            # Отправляем сообщение с ответом
            sent_message = await call.message.answer(
                message_text,
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
            logger.info(
                f"Пользователю {call.from_user.username} отправлен список главных ссылок, message_id: {sent_message.message_id}")
        else:
            # Если нет установленных главных ссылок, показать стандартную ссылку
            sent_message = await call.message.answer(
                "⚠️ Главные статические ссылки не установлены. Используется стандартная ссылка:\nhttps://t.me/proger_dude"
            )
            logger.info(
                f"Пользователь {user_id} запросил главные ссылки, но они не установлены. message_id: {sent_message.message_id}")
    except Exception as e:
        # Более подробное логирование ошибки
        logger.error(f"Ошибка при получении главных ссылок: {e}", exc_info=True)
        await call.message.answer(f"❌ Произошла ошибка при получении главных статических ссылок: {str(e)}")




def get_flag_emoji(language_code: str) -> str:
    """
    Возвращает эмодзи флага по коду языка.
    Например, 'en' -> 🇬🇧, 'ru' -> 🇷🇺
    """
    try:
        # Словарь соответствий языков флагам (можно расширить)
        flags = {
            'en': '🇬🇧',
            'ru': '🇷🇺',
            'tr': '🇹🇷',
            'ar': '🇸🇦',
            # Добавьте другие языки и соответствующие флаги
        }
        return flags.get(language_code, '🌐')  # 🌐 - глобус по умолчанию
    except Exception as e:
        logger.error(f"Ошибка при получении флага для языка '{language_code}': {e}")
        return '🌐'


