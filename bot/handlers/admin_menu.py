import datetime
import logging
import os


from sqlalchemy.future import select

from aiogram import Router, Bot
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.publication_service import publish_task_by_id, publish_task_by_translation_group
from bot.services.deletion_service import delete_task_by_id  # Импорт функции удаления
from bot.services.task_bd_status_service import get_task_status
from bot.utils.image_generator import generate_detailed_task_status_image
from database.models import Task

logger = logging.getLogger(__name__)
router = Router()




class TaskActions(StatesGroup):
    awaiting_publish_id = State()
    awaiting_delete_id = State()








# Обработчик для кнопки "Загрузить JSON"
@router.callback_query(lambda call: call.data == "upload_json")
async def upload_json(call: CallbackQuery, db_session: AsyncSession):
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Загрузить JSON'")
    await call.message.answer("Загрузите JSON файл с задачами.")




@router.callback_query(lambda call: call.data == "publish_by_id")
async def publish_by_id(call: CallbackQuery, state: FSMContext):
    logger.info(f"📢 Запрошена публикация задачи пользователем {call.from_user.id}")
    await state.set_state(TaskActions.awaiting_publish_id)
    await call.message.answer("📝 Пожалуйста, введите ID задачи для публикации:")
    await call.answer()



@router.callback_query(lambda call: call.data == "delete_task")
async def delete_task(call: CallbackQuery, state: FSMContext):
    logger.info(f"🗑️ Запрошено удаление задачи пользователем {call.from_user.id}")
    await state.set_state(TaskActions.awaiting_delete_id)
    await call.message.answer("📝 Введите ID задачи для удаления:")
    await call.answer()



@router.message(StateFilter(TaskActions.awaiting_publish_id))
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




@router.message(StateFilter(TaskActions.awaiting_delete_id))
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




@router.callback_query(lambda call: call.data == "create_quiz")
async def create_quiz(call: CallbackQuery, db_session: AsyncSession):
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Создать опрос'")
    await call.message.answer("Функция создания опроса в разработке.")




@router.callback_query(lambda query: query.data == "database_status")
async def handle_database_status(callback: CallbackQuery, db_session: AsyncSession):
    unpublished_tasks, published_tasks, old_published_tasks, total_tasks, all_tasks, topics = await get_task_status(
        db_session)
    image_path = await generate_detailed_task_status_image(unpublished_tasks, old_published_tasks, total_tasks, topics,
                                                           published_tasks)
    image_file = FSInputFile(image_path)
    await callback.message.answer_photo(photo=image_file)
    os.remove(image_path)
    await callback.answer("Отчет о состоянии базы данных отправлен.", show_alert=True)





@router.callback_query(lambda call: call.data == "publish_task_with_translations")
async def publish_task_with_translations(call: CallbackQuery, db_session: AsyncSession, bot: Bot):
    logger.info(
        f"🟢 Пользователь {call.from_user.username} (ID: {call.from_user.id}) начал процесс публикации задачи с переводами.")
    await call.message.answer(
        f"🟢 Процесс публикации задачи с переводами запущен для пользователя {call.from_user.username}.")

    # Шаг 1: Поиск самой старой неопубликованной задачи
    logger.info("🔍 Поиск самой старой неопубликованной задачи...")
    await call.message.answer("🔍 Поиск самой старой неопубликованной задачи...")

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
        await call.message.answer(
            "🔍 Не найдены неопубликованные задачи. Поиск задач, опубликованных более месяца назад...")

        one_month_ago = datetime.now() - datetime.timedelta(days=30)
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
                f"📊 Результаты:\n"
                f"Всего переводов: {total_count}\n"
                f"Успешно опубликовано: {published_count}\n"
                f"С ошибками: {failed_count}"
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







