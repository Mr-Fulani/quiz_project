# bot/handlers/admin_menu.py
import html
import logging
import os
import datetime

from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from aiogram import Router, F, Bot, types
from aiogram.types import CallbackQuery, Message, ForceReply, ContentType, InlineKeyboardButton, InputFile, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.quiz_keyboards import get_admin_menu_keyboard
from bot.keyboards.reply_keyboards import get_location_type_keyboard
from bot.services.admin_service import is_admin, add_admin, remove_admin
from bot.services.publication_service import publish_task_by_id, publish_task_by_translation_group
from bot.services.deletion_service import delete_task_by_id
from bot.services.task_bd_status_service import get_task_status, get_zero_task_topics
from bot.services.topic_services import delete_topic_from_db, add_topic_to_db
from bot.utils.image_generator import generate_detailed_task_status_image, \
    generate_zero_task_topics_text
from bot.states.admin_states import AddAdminStates, RemoveAdminStates, TaskActions, ChannelStates, AdminStates
from config import ALLOWED_USERS
from database.database import get_session
from database.models import Admin, Task, Group, Topic
import re


logger = logging.getLogger(__name__)
router = Router(name="admin_menu_router")








def escape_markdown(text: str) -> str:
    """
    Экранирует специальные символы для MarkdownV2.
    """
    escape_chars = r"*_[]()~`>#+\-=|{}.!\\"
    return re.sub(r'([*_`\[\]()~`>#+\-=|{}.!\\])', r'\\\1', text)


# Обработчик кнопки "Добавить администратора"
@router.callback_query(F.data == "add_admin_button")
async def callback_add_admin(call: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    logger.info("Обработчик кнопки 'Добавить администратора' вызван")
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.message.answer("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {call.from_user.username} ({user_id}) попытался добавить администратора без прав.")
        await call.answer()
        return
    await call.message.answer(
        "🔒 Введите секретный пароль для добавления нового администратора:\n\n"
        "_Обратите внимание: вводимые символы будут видны только вам._",
        parse_mode='Markdown',
        reply_markup=ForceReply(selective=True)
    )
    logger.debug("Просьба ввести пароль для добавления администратора")
    await state.set_state(AddAdminStates.waiting_for_password)
    await call.answer()



# Обработчик пароля для добавления администратора
@router.message(AddAdminStates.waiting_for_password, F.content_type == ContentType.TEXT)
async def process_add_admin_password(message: Message, state: FSMContext, db_session: AsyncSession):
    logger.info("Обработчик ввода пароля для добавления администратора вызван")
    if message.text != os.getenv("ADMIN_SECRET_PASSWORD"):
        await message.reply("❌ Неверный пароль. Доступ запрещён.")
        logger.warning(f"Неверный пароль от пользователя {message.from_user.username} ({message.from_user.id}).")
        await state.clear()
        return
    await message.reply("✅ Пароль верный. Пожалуйста, введите Telegram ID пользователя, которого хотите добавить:")
    logger.debug("Пароль верен, просим ввести Telegram ID")
    await state.set_state(AddAdminStates.waiting_for_user_id)



# Обработчик Telegram ID для добавления администратора
@router.message(AddAdminStates.waiting_for_user_id, F.content_type == ContentType.TEXT)
async def process_add_admin_user_id(message: Message, state: FSMContext, db_session: AsyncSession):
    logger.info("Обработчик ввода Telegram ID для добавления администратора вызван")
    if not message.text:
        await message.reply("❌ Сообщение не содержит текста. Пожалуйста, введите корректный Telegram ID пользователя.")
        logger.warning(f"Пользователь {message.from_user.username} ({message.from_user.id}) отправил сообщение без текста.")
        return

    try:
        new_admin_id = int(message.text)
    except (ValueError, TypeError):
        await message.reply("❌ Пожалуйста, введите корректный числовой Telegram ID (например, 123456789).")
        logger.debug(f"Пользователь {message.from_user.username} ({message.from_user.id}) ввёл некорректный ID: {message.text}")
        return

    # Проверка, не является ли пользователь уже администратором
    if await is_admin(new_admin_id, db_session):
        await message.reply("ℹ️ Этот пользователь уже является администратором.")
        logger.info(f"Пользователь с ID {new_admin_id} уже является администратором.")
        await state.clear()
        await message.answer(
            "🔄 Возвращаюсь в главное меню.",
            reply_markup=get_admin_menu_keyboard()
        )
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



# Обработчик кнопки "Удалить администратора"
@router.callback_query(F.data == "remove_admin_button")
async def callback_remove_admin(call: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    user_id = call.from_user.id
    if not await is_admin(user_id, db_session):
        await call.message.answer("⛔ У вас нет прав для выполнения этой команды.")
        logger.warning(f"Пользователь {call.from_user.username} ({user_id}) попытался удалить администратора без прав.")
        await call.answer()
        return
    await call.message.answer(
        "🔒 Введите секретный пароль для удаления администратора:\n\n"
        "_Обратите внимание: вводимые символы будут видны только вам._",
        parse_mode='Markdown',
        reply_markup=ForceReply(selective=True)
    )
    logger.debug("Просьба ввести пароль для удаления администратора")
    await state.set_state(RemoveAdminStates.waiting_for_password)
    await call.answer()



# Обработчик пароля для удаления администратора
@router.message(RemoveAdminStates.waiting_for_password, F.content_type == ContentType.TEXT)
async def process_remove_admin_password(message: Message, state: FSMContext, db_session: AsyncSession):
    if message.text != os.getenv("ADMIN_REMOVE_SECRET_PASSWORD"):
        await message.reply("❌ Неверный пароль. Доступ запрещён.")
        logger.warning(f"Неверный пароль от пользователя {message.from_user.username} ({message.from_user.id}).")
        await state.clear()
        return
    await message.reply("✅ Пароль верный. Пожалуйста, введите Telegram ID администратора, которого хотите удалить:")
    await state.set_state(RemoveAdminStates.waiting_for_user_id)



# Обработчик Telegram ID для удаления администратора
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



# Обработчик кнопки "Список администраторов"
@router.callback_query(lambda c: c.data == "list_admins_button")
async def callback_list_admins(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Список администраторов". Отправляет список администраторов.
    """
    logger.info(
        f"Пользователь {call.from_user.username or 'None'} (ID: {call.from_user.id}) нажал кнопку 'Список администраторов'")

    try:
        # Получаем всех администраторов из базы данных
        query = select(Admin)
        result = await db_session.execute(query)
        admins = result.scalars().all()

        if not admins:
            admin_list = "👥 Нет зарегистрированных администраторов."
        else:
            admin_list = ""
            for admin in admins:
                username = admin.username if admin.username else "Нет username"
                # Формируем строку с экранированием
                line = f"• {username} (ID: {admin.telegram_id})"
                safe_line = escape_markdown(line)
                admin_list += f"{safe_line}\n"

        # Отправляем сообщение с экранированными символами
        await call.message.answer(f"👥 **Список администраторов:**\n{admin_list}", parse_mode='MarkdownV2')
        await call.answer()  # Отвечаем на callback_query
        logger.debug("Список администраторов отправлен")
    except Exception as e:
        logger.exception(f"Ошибка в обработчике callback_list_admins: {e}")
        await call.message.answer("❌ Произошла ошибка при отправке списка администраторов.")
        await call.answer()



# Обработчик кнопки "Загрузить JSON"
@router.callback_query(F.data == "upload_json")
async def upload_json_handler(call: CallbackQuery, db_session: AsyncSession):
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Загрузить JSON'")
    await call.message.answer("Загрузите JSON файл с задачами.")
    await call.answer()



# Обработчик кнопки "Опубликовать по ID"
@router.callback_query(F.data == "publish_by_id")
async def publish_by_id_handler(call: CallbackQuery, state: FSMContext):
    logger.info(f"📢 Запрошена публикация задачи пользователем {call.from_user.id}")
    await state.set_state(TaskActions.awaiting_publish_id)
    await call.message.answer("📝 Пожалуйста, введите ID задачи для публикации:")
    await call.answer()



# Обработчик кнопки "Удалить задачу по ID"
@router.callback_query(F.data == "delete_task")
async def delete_task_handler(call: CallbackQuery, state: FSMContext):
    logger.info(f"🗑️ Запрошено удаление задачи пользователем {call.from_user.id}")
    await state.set_state(TaskActions.awaiting_delete_id)
    await call.message.answer("📝 Введите ID задачи для удаления:")
    await call.answer()



# Обработчик состояния публикации задачи
@router.message(StateFilter(TaskActions.awaiting_publish_id), F.content_type == ContentType.TEXT)
async def handle_publish_id(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    current_state = await state.get_state()
    logger.debug(f"Текущее состояние (публикация): {current_state}")

    if not message.text or not message.text.isdigit():
        await message.answer("❌ Пожалуйста, введите корректный ID задачи (только цифры)")
        return

    task_id = int(message.text)
    logger.info(f"📢 Публикация задачи с ID: {task_id}")

    try:
        success = await publish_task_by_id(task_id, message, db_session, bot)
        if success:
            await message.answer(f"✅ Задача с ID {task_id} успешно опубликована!")
        else:
            await message.answer(f"❌ Не удалось опубликовать задачу с ID {task_id}.")
    except Exception as e:
        logger.error(f"Ошибка при публикации задачи {task_id}: {e}")
        await message.answer(f"❌ Произошла ошибка при публикации задачи: {str(e)}")

    await state.clear()



# Обработчик состояния удаления задачи
@router.message(StateFilter(TaskActions.awaiting_delete_id), F.content_type == ContentType.TEXT)
async def handle_delete_id(message: Message, state: FSMContext, db_session: AsyncSession):
    current_state = await state.get_state()
    logger.debug(f"Текущее состояние (удаление): {current_state}")

    if not message.text or not message.text.isdigit():
        await message.answer("❌ Пожалуйста, введите корректный ID задачи (только цифры)")
        return

    task_id = int(message.text)
    logger.info(f"🗑️ Получен запрос на удаление задачи с ID: {task_id}")

    try:
        deletion_info = await delete_task_by_id(task_id, db_session)
        if deletion_info:
            # Формирование подробного сообщения
            task_info = f"✅ Задачи с ID {', '.join(map(str, deletion_info['deleted_task_ids']))} успешно удалены!"
            topic_info = f"🏷️ Топик задач: {deletion_info['topic_name'] or 'неизвестен'}"
            translations_info = (
                f"🌍 Удалено переводов: {deletion_info['deleted_translation_count']}\n"
                f"📜 Языки переводов: {', '.join(deletion_info['deleted_translation_languages']) if deletion_info['deleted_translation_languages'] else 'нет переводов'}\n"
                f"🏷️ Каналы: {', '.join(deletion_info['group_names']) if deletion_info['group_names'] else 'группы не найдены'}"
            )

            # Отправляем информацию о том, что было удалено
            deleted_info = f"{task_info}\n{topic_info}\n{translations_info}"
            logger.debug(f"Информация об удалении:\n{deleted_info}")
            await message.answer(deleted_info)
        else:
            await message.answer(f"❌ Не удалось удалить задачу с ID {task_id}. Возможно, задача не найдена.")
    except Exception as e:
        logger.error(f"Ошибка при удалении задачи {task_id}: {e}")
        await message.answer(f"❌ Произошла ошибка при удалении задачи с ID {task_id}.")

    await state.clear()



# Обработчик кнопки "Создать опрос"
@router.callback_query(F.data == "create_quiz")
async def create_quiz_handler(call: CallbackQuery, db_session: AsyncSession):
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Создать опрос'")
    await call.message.answer("Функция создания опроса в разработке.")
    await call.answer()



# Обработчик кнопки "Состояние базы"
@router.callback_query(F.data == "database_status")
async def handle_database_status(callback: CallbackQuery, db_session: AsyncSession):
    try:
        unpublished_tasks, published_tasks, old_published_tasks, total_tasks, all_tasks, topics = await get_task_status(db_session)
        image_path = await generate_detailed_task_status_image(
            unpublished_tasks, old_published_tasks, total_tasks, topics, published_tasks
        )
        image_file = FSInputFile(image_path)
        await callback.message.answer_photo(photo=image_file)
        os.remove(image_path)
        await callback.answer("Отчет о состоянии базы данных отправлен.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при генерации отчета о состоянии базы данных: {e}")
        await callback.message.answer("❌ Произошла ошибка при генерации отчета о состоянии базы данных.")
        await callback.answer("Ошибка при генерации отчета.", show_alert=True)



# Обработчик кнопки "Опубликовать задачу с переводами"
@router.callback_query(F.data == "publish_task_with_translations")
async def publish_task_with_translations_handler(call: CallbackQuery, db_session: AsyncSession, bot: Bot):
    logger.info(f"🟢 Пользователь {call.from_user.username} (ID: {call.from_user.id}) начал процесс публикации задачи с переводами.")
    await call.message.answer(f"🟢 Процесс публикации задачи с переводами запущен для пользователя {call.from_user.username}.")

    # Шаг 1: Поиск самой старой неопубликованной задачи
    logger.info("🔍 Поиск самой старой неопубликованной задачи...")
    await call.message.answer("🔍 Поиск самой старой неопубликованной задачи...")

    try:
        result = await db_session.execute(
            select(Task.translation_group_id)
            .where(Task.published.is_(False))
            .order_by(Task.id.asc())  # Самая старая неопубликованная задача
            .limit(1)
        )
        translation_group_id = result.scalar_one_or_none()

        # Шаг 2: Если неопубликованные задачи не найдены, ищем опубликованные более месяца назад
        if not translation_group_id:
            logger.info("🔍 Не найдены неопубликованные задачи. Поиск задач, опубликованных более месяца назад...")
            await call.message.answer("🔍 Не найдены неопубликованные задачи. Поиск задач, опубликованных более месяца назад...")

            one_month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
            result = await db_session.execute(
                select(Task.translation_group_id)
                .where(Task.published.is_(True))
                .where(Task.publish_date < one_month_ago)
                .order_by(Task.publish_date.asc())  # Самая старая опубликованная задача
                .limit(1)
            )
            translation_group_id = result.scalar_one_or_none()

        # Шаг 3: Если задача найдена, публикуем
        if translation_group_id:
            logger.info(f"🟡 Найдена задача с группой переводов {translation_group_id}. Начинаем публикацию.")
            await call.message.answer(f"🟡 Найдена задача с группой переводов {translation_group_id}. Начинаем публикацию.")

            # Выполнение публикации
            success, published_count, failed_count, total_count = await publish_task_by_translation_group(
                translation_group_id, call.message, db_session, bot
            )

            # Логируем результат публикации
            if success:
                logger.info(f"✅ Задача с группой переводов {translation_group_id} успешно опубликована.")
                logger.info(
                    f"📊 Результаты публикации: всего переводов — {total_count}, успешно опубликовано — {published_count}, с ошибками — {failed_count}.")
                await call.message.answer(
                    f"✅ Задача с группой переводов {translation_group_id} успешно опубликована.\n"
                )
            else:
                logger.error(f"❌ Произошла ошибка при публикации задачи с группой переводов {translation_group_id}.")
                await call.message.answer(
                    f"❌ Произошла ошибка при публикации задачи с группой переводов {translation_group_id}.\n"
                    f"📊 Результаты:\n"
                    f"Всего переводов: {total_count}\n"
                    f"Успешно опубликовано: {published_count}\n"
                    f"С ошибками: {failed_count}"
                )
        else:
            # Если нет неопубликованных и старых задач
            logger.info(
                "⚠️ Не найдены задачи для публикации: все задачи уже опубликованы или не требуют повторной публикации.")
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
    """
    logger.info(
        f"Пользователь {call.from_user.username or 'None'} (ID: {call.from_user.id}) нажал кнопку 'Добавить канал/группу'")

    await call.message.answer("🔽 Начнём добавление новой группы или канала.\nВведите имя группы/канала:")
    await state.set_state(ChannelStates.waiting_for_group_name)
    await call.answer()  # Отвечаем на callback_query





@router.message(ChannelStates.waiting_for_group_name)
async def process_group_name(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает ввод имени группы или канала.
    """
    group_name = message.text.strip()
    if not group_name:
        await message.reply("❌ Имя группы или канала не может быть пустым. Пожалуйста, введите корректное имя:")
        return

    await state.update_data(group_name=group_name)
    logger.info(f"Введено имя группы/канала: {group_name}")
    await message.answer("📌 Введите Telegram ID группы/канала (начинается с -100):")
    await state.set_state(ChannelStates.waiting_for_group_id)




@router.message(ChannelStates.waiting_for_group_id)
async def process_group_id(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает ввод Telegram ID группы или канала.
    """
    group_id_text = message.text.strip()
    if not re.match(r'^-100\d+$', group_id_text):
        await message.reply(
            "❌ Некорректный формат Telegram ID. Он должен начинаться с -100 и содержать цифры после него.\nПожалуйста, введите корректный Telegram ID группы/канала:")
        return

    group_id = int(group_id_text)
    await state.update_data(group_id=group_id)
    logger.info(f"Введён Telegram ID группы/канала: {group_id}")
    await message.answer("📄 Введите название темы:")
    await state.set_state(ChannelStates.waiting_for_topic)




@router.message(ChannelStates.waiting_for_topic)
async def process_topic_name(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает ввод названия темы.
    """
    topic_name = message.text.strip()
    if not topic_name:
        await message.reply("❌ Название темы не может быть пустым. Пожалуйста, введите корректное название темы:")
        return

    # Проверка существования темы
    result = await db_session.execute(select(Topic).where(Topic.name.ilike(topic_name)))
    topic = result.scalar_one_or_none()

    if not topic:
        # Тема не найдена, предложить создать новую
        await state.update_data(topic_name=topic_name)
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="Да, создать тему")],
                [types.KeyboardButton(text="Нет, отменить добавление")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(f"❓ Тема '{topic_name}' не найдена. Хотите создать новую тему?", reply_markup=keyboard)
        await state.set_state(ChannelStates.waiting_for_topic_creation)
    else:
        # Тема найдена, продолжаем
        await state.update_data(topic_id=topic.id)
        logger.info(f"Тема '{topic_name}' найдена, ID: {topic.id}")
        await message.answer("🗣️ Введите язык группы/канала (например, 'en', 'ru', 'tr'):")
        await state.set_state(ChannelStates.waiting_for_language)




@router.message(ChannelStates.waiting_for_topic_creation)
async def process_topic_creation(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает решение администратора о создании новой темы.
    """
    decision = message.text.strip().lower()
    if decision == "да, создать тему":
        data = await state.get_data()
        topic_name = data.get("topic_name")
        # Создание новой темы
        new_topic = Topic(name=topic_name)
        db_session.add(new_topic)
        try:
            await db_session.commit()
            await message.answer(f"✅ Тема '{topic_name}' успешно создана.")
            # Получаем ID созданной темы
            result = await db_session.execute(select(Topic).where(Topic.name.ilike(topic_name)))
            topic = result.scalar_one()
            await state.update_data(topic_id=topic.id)
            # Продолжаем процесс добавления группы/канала
            await message.answer("🗣️ Введите язык группы/канала (например, 'en', 'ru', 'tr'):")
            await state.set_state(ChannelStates.waiting_for_language)
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Ошибка при создании темы '{topic_name}': {e}")
            await message.reply("❌ Произошла ошибка при создании темы. Попробуйте ещё раз.")
            await state.clear()
    elif decision == "нет, отменить добавление":
        await message.reply("❌ Добавление группы или канала отменено.", reply_markup=get_admin_menu_keyboard())
        await state.clear()
    else:
        await message.reply("❌ Пожалуйста, выберите 'Да, создать тему' или 'Нет, отменить добавление'.")




@router.message(ChannelStates.waiting_for_language)
async def process_language(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает ввод языка группы или канала.
    """
    language = message.text.strip().lower()
    if not re.match(r'^[a-z]{2,3}$', language):
        await message.reply(
            "❌ Некорректный формат языка. Используйте, например, 'en', 'ru', 'tr'.\nПожалуйста, введите корректный язык:")
        return

    await state.update_data(language=language)
    logger.info(f"Введён язык группы/канала: {language}")
    await message.answer("🔄 Выберите тип локации:", reply_markup=get_location_type_keyboard())
    await state.set_state(ChannelStates.waiting_for_location_type)




@router.message(ChannelStates.waiting_for_location_type)
async def process_location_type(message: types.Message, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает выбор типа локации (channel или group).
    """
    location_type = message.text.strip().lower()
    if location_type not in ["channel", "group"]:
        await message.reply("❌ Некорректный выбор. Пожалуйста, выберите 'channel' или 'group':")
        return

    await state.update_data(location_type=location_type)
    logger.info(f"Выбран тип локации: {location_type}")

    # Получаем все данные из состояния
    data = await state.get_data()
    group_name = data.get("group_name")
    group_id = data.get("group_id")
    topic_name = data.get("topic_id")
    language = data.get("language")

    # Поиск топика по названию
    result = await db_session.execute(select(Topic).where(Topic.id == topic_name))
    topic = result.scalar_one_or_none()

    if not topic:
        await message.reply(
            f"❌ Тема '{topic_name}' не найдена в базе данных. Пожалуйста, убедитесь, что тема существует.")
        await state.clear()
        return

    # Проверка существования группы или канала с таким же group_id
    result = await db_session.execute(select(Group).where(Group.group_id == group_id))
    existing_group = result.scalar_one_or_none()

    if existing_group:
        await message.reply(f"❌ Группа или канал с ID {group_id} уже существует в базе данных.")
        await state.clear()
        return

    # Создание новой группы или канала
    new_group = Group(
        group_name=group_name,
        group_id=group_id,
        topic_id=topic.id,
        language=language,
        location_type=location_type
    )

    db_session.add(new_group)
    try:
        await db_session.commit()
        logger.info(f"Локация '{group_name}' успешно добавлена.")
        await message.answer(
            f"✅ {'Канал' if location_type == 'channel' else 'Группа'} '{group_name}' успешно добавлен{' в базу данных'}.",
            reply_markup=get_admin_menu_keyboard())
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Ошибка при добавлении локации '{group_name}': {e}")
        await message.reply("❌ Произошла ошибка при добавлении локации. Попробуйте ещё раз.")

    await state.clear()







@router.callback_query(lambda c: c.data == "remove_channel_button")
async def callback_remove_channel(call: types.CallbackQuery, db_session: AsyncSession, state: FSMContext):
    """
    Обрабатывает нажатие кнопки "Удалить канал". Начинает процесс удаления канала.
    """
    logger.info(
        f"Пользователь {call.from_user.username or 'None'} (ID: {call.from_user.id}) нажал кнопку 'Удалить канал'")

    await call.message.answer(
        "🔽 Начнём удаление канала.\nВведите Telegram ID канала, который хотите удалить (начинается с -100):")
    await state.set_state(ChannelStates.waiting_for_remove_group_id)
    await call.answer()  # Отвечаем на callback_query



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

    # Проверяем существование канала
    result = await db_session.execute(select(Group).where(Group.group_id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        await message.reply(f"❌ Канал с ID {group_id} не найден в базе данных.")
        await state.clear()
        return

    # Удаляем канал из базы данных
    try:
        await db_session.delete(group)
        await db_session.commit()
        logger.info(f"Канал '{group.group_name}' (ID: {group_id}) успешно удалён.")
        await message.answer(f"✅ Канал '{group.group_name}' (ID: {group_id}) успешно удалён из базы данных.",
                             reply_markup=get_admin_menu_keyboard())
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Ошибка при удалении канала: {e}")
        await message.reply("❌ Произошла ошибка при удалении канала. Попробуйте ещё раз.")

    await state.clear()








@router.callback_query(lambda c: c.data == "list_channels_groups_button")
async def callback_list_channels_groups(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Обрабатывает нажатие кнопки "Список каналов и групп". Отправляет список каналов и групп с указанием языка.
    """
    logger.info(
        f"Пользователь {call.from_user.username or 'None'} (ID: {call.from_user.id}) нажал кнопку 'Список каналов и групп'")

    try:
        # Получаем все группы и каналы из базы данных
        query = select(Group)
        result = await db_session.execute(query)
        groups = result.scalars().all()

        if not groups:
            channels_groups_list = "📭 <b>Список каналов и групп:</b>\n\n📭 Нет добавленных каналов или групп."
        else:
            # Разделяем каналы и группы
            channels = [group for group in groups if group.location_type.lower() == "channel"]
            groups_only = [group for group in groups if group.location_type.lower() == "group"]

            channels_list = ""
            groups_list = ""

            if channels:
                channels_list += "📢 <b>Каналы:</b>\n"
                for channel in channels:
                    channel_name = html.escape(channel.group_name)
                    channel_id = channel.group_id
                    channel_language = html.escape(channel.language) if channel.language else "Не указан"
                    channels_list += f"• {channel_name} (ID: {channel_id}) - Язык: {channel_language}\n"
                channels_list += "\n"  # Добавляем дополнительный перенос строки

            if groups_only:
                groups_list += "👥 <b>Группы:</b>\n"
                for group in groups_only:
                    group_name = html.escape(group.group_name)
                    group_id = group.group_id
                    group_language = html.escape(group.language) if group.language else "Не указан"
                    groups_list += f"• {group_name} (ID: {group_id}) - Язык: {group_language}\n"
                groups_list += "\n"  # Добавляем дополнительный перенос строки

            channels_groups_list = f"📭 <b>Список каналов и групп:</b>\n\n{channels_list}{groups_list}"

        # Логирование сформированного списка
        logger.debug(f"Сформированный список каналов и групп:\n{channels_groups_list}")

        # Отправляем сообщение с использованием HTML
        await call.message.answer(channels_groups_list, parse_mode='HTML')
        await call.answer()  # Отвечаем на callback_query
        logger.debug("Список каналов и групп отправлен")
    except TelegramBadRequest as e:
        # Логирование специфических ошибок Telegram API
        logger.error(f"Ошибка в обработчике callback_list_channels_groups: {e}")
        await call.message.answer("❌ Произошла ошибка при отправке списка каналов и групп.")
        await call.answer()
    except Exception as e:
        # Общая обработка исключений
        logger.exception(f"Неизвестная ошибка в обработчике callback_list_channels_groups: {e}")
        await call.message.answer("❌ Произошла непредвиденная ошибка.")
        await call.answer()











@router.callback_query(lambda c: c.data == "zero_task_topics_report")
async def handle_zero_task_topics_report(callback_query: types.CallbackQuery, db_session: AsyncSession):
    """
    Обработчик для кнопки "Отчет топиков без задач".
    Генерирует текстовый отчет и отправляет его администратору.
    """
    user_id = callback_query.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback_query.answer("У вас нет доступа к этой команде.", show_alert=True)
        logger.warning(f"Пользователь с ID {user_id} попытался получить доступ к отчету без прав.")
        return

    logger.info(f"Пользователь {callback_query.from_user.username} запросил отчет топиков без задач.")

    await callback_query.answer("Генерация отчета...", show_alert=True)

    try:
        zero_task_topics = await get_zero_task_topics(db_session)
        report_path = await generate_zero_task_topics_text(zero_task_topics)

        if report_path:
            # Получаем абсолютный путь к файлу
            absolute_path = os.path.abspath(report_path)
            logger.debug(f"Абсолютный путь к отчету: {absolute_path}")

            # Проверяем, существует ли файл
            if not os.path.isfile(absolute_path):
                logger.error(f"Файл отчета не найден по пути: {absolute_path}")
                await callback_query.message.answer("❌ Не удалось найти сгенерированный отчет.")
                return

            # Используем FSInputFile для отправки документа
            report_file = FSInputFile(absolute_path)
            await callback_query.message.answer_document(
                document=report_file,
                caption="📊 *Отчет топиков без задач:*",
                parse_mode="Markdown"
            )
            logger.info(f"Отчет топиков без задач отправлен пользователю {callback_query.from_user.username}.")

            # Удаление файла после отправки
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
async def handle_add_topic(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback_query.answer("У вас нет доступа к этой команде.", show_alert=True)
        logger.warning(f"Пользователь с ID {user_id} попытался добавить топик без прав.")
        return

    await callback_query.message.answer("Пожалуйста, введите название топика для добавления:")
    await state.set_state(AdminStates.waiting_for_topic_name)  # Исправлено
    await callback_query.answer()
    logger.info(f"Пользователь {callback_query.from_user.username} инициировал добавление топика.")



@router.message(AdminStates.waiting_for_topic_name)
async def process_add_topic(message: types.Message, state: FSMContext, db_session: AsyncSession):
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
async def handle_delete_topic(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if user_id not in ALLOWED_USERS:
        await callback_query.answer("У вас нет доступа к этой команде.", show_alert=True)
        logger.warning(f"Пользователь с ID {user_id} попытался удалить топик без прав.")
        return

    await callback_query.message.answer("Пожалуйста, введите ID топика для удаления:")
    await state.set_state(AdminStates.waiting_for_topic_id)  # Исправлено
    await callback_query.answer()
    logger.info(f"Пользователь {callback_query.from_user.username} инициировал удаление топика.")



@router.message(AdminStates.waiting_for_topic_id)
async def process_delete_topic(message: types.Message, state: FSMContext, db_session: AsyncSession):
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


