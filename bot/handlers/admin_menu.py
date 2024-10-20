import logging
import os
from datetime import datetime, timedelta

from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession


from bot.services.publication_service import publish_task_by_id, publish_task_by_translation_group

from bot.services.task_bd_status_service import get_task_status
from bot.utils.image_generator import generate_detailed_task_status_image
from database.models import Task








# Логгер для отслеживания действий
logger = logging.getLogger(__name__)



router = Router()



# Храним введенный ID от пользователя
temp_data = {}






# Обработчик для кнопки "Создать опрос"
@router.callback_query(lambda call: call.data == "create_quiz")
async def create_quiz(call: CallbackQuery, db_session: AsyncSession):
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Создать опрос'")
    await call.message.answer("Функция создания опроса в разработке.")






# Обработчик для кнопки "Опубликовать опрос по ID"
@router.callback_query(lambda call: call.data == "publish_by_id")
async def publish_by_id(call: types.CallbackQuery):
    """
    Запрашивает у пользователя ID задачи для публикации.
    """
    user_id = call.from_user.id
    username = call.from_user.username

    logger.info(f"📢 Пользователь {username} (ID: {user_id}) нажал на 'Опубликовать опрос по ID'")

    # Отправляем запрос на ввод ID задачи
    await call.message.answer("📝 Пожалуйста, введите ID задачи для публикации:")

    # Устанавливаем временное состояние для ожидания ID
    temp_data[user_id] = 'awaiting_task_id'

    logger.info(f"⏳ Ожидание ввода ID задачи от пользователя {username} (ID: {user_id})")






# Обработчик для получения ID от пользователя
@router.message(F.text.regexp(r'^\d+$'))  # Ожидаем только число (ID задачи)
async def receive_task_id(message: types.Message, db_session: AsyncSession, bot: Bot, state: FSMContext):
    """
    Получает ID задачи от пользователя и публикует её.
    """
    user_id = message.from_user.id

    if temp_data.get(user_id) == 'awaiting_task_id':
        try:
            task_id = int(message.text)
            logger.info(f"📥 Получен ID задачи для публикации: {task_id} от пользователя {message.from_user.username}")

            # Публикуем задачу через сервис
            success = await publish_task_by_id(task_id, message, db_session, bot)

            if success:
                success_message = f"✅ Задача с ID {task_id} успешно опубликована!"
                logger.info(success_message)
                await message.answer(success_message)
            else:
                failure_message = f"❌ Не удалось опубликовать задачу с ID {task_id}."
                logger.error(failure_message)
                await message.answer(failure_message)

        except ValueError:
            logger.error(f"⛔ Ошибка: некорректный формат ID задачи. Пользователь: {message.from_user.username}, ID: {message.text}")
            await message.answer("⛔ Ошибка: Пожалуйста, введите корректный числовой ID задачи.")
        except Exception as e:
            logger.error(f"⚠️ Ошибка при обработке ID задачи: {e}")
            await message.answer("⚠️ Произошла ошибка при обработке задачи. Попробуйте позже.")
        finally:
            # Очищаем состояние и удаляем временные данные пользователя
            temp_data.pop(user_id, None)
            await state.clear()

    else:
        logger.warning(f"⚠️ Пользователь {message.from_user.username} отправил неожиданный ID задачи.")
        await message.answer("⚠️ Я не ожидал ID задачи. Пожалуйста, воспользуйтесь соответствующей командой.")





# Обработчик для кнопки "Загрузить JSON"
@router.callback_query(lambda call: call.data == "upload_json")
async def upload_json(call: CallbackQuery, db_session: AsyncSession):
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Загрузить JSON'")
    await call.message.answer("Загрузите JSON файл с задачами.")







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

        one_month_ago = datetime.now() - timedelta(days=30)
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














@router.callback_query(lambda query: query.data == "database_status")
async def handle_database_status(callback: CallbackQuery, db_session):
    """
    Обработчик для кнопки "Состояние базы". Отправляет информацию о задачах.
    """
    # Получаем данные из базы
    unpublished_tasks, published_tasks, old_published_tasks, total_tasks, all_tasks, topics = await get_task_status(db_session)

    # Генерируем изображение
    image_path = await generate_detailed_task_status_image(unpublished_tasks, old_published_tasks, total_tasks, topics, published_tasks)

    # Используем FSInputFile для работы с файлами
    image_file = FSInputFile(image_path)  # Передаем путь к файлу

    # Отправляем изображение
    await callback.message.answer_photo(photo=image_file)

    # Удаляем временное изображение
    os.remove(image_path)

    # Уведомляем пользователя о выполнении команды
    await callback.answer("Отчет о состоянии базы данных отправлен.", show_alert=True)