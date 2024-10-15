import logging
from datetime import datetime, timedelta

from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.services.publication_service import publish_task_by_id
from bot.services.task_service import publish_task_by_translation_group
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
    logger.info(f"Пользователь {call.from_user.username} нажал на 'Опубликовать опрос по ID'")
    await call.message.answer("Введите ID задачи для публикации.")
    temp_data[call.from_user.id] = 'awaiting_task_id'




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
            logger.info(f"Получен ID задачи для публикации: {task_id} от пользователя {message.from_user.username}")

            # Публикуем задачу через сервис
            success = await publish_task_by_id(task_id, message, db_session, bot)

            if success:
                logger.info(f"Задача с ID {task_id} успешно опубликована.")
            else:
                logger.error(f"Задача с ID {task_id} не опубликована.")

        except Exception as e:
            logger.error(f"Ошибка при обработке ID задачи: {e}")
            await message.answer("Произошла ошибка при обработке задачи.")

        finally:
            temp_data.pop(user_id, None)
            await state.clear()

    else:
        await message.answer("Я не ожидал ID задачи. Пожалуйста, воспользуйтесь соответствующей командой.")


# Обработчик для кнопки "Загрузить JSON"
@router.callback_query(lambda call: call.data == "upload_json")
async def upload_json(call: CallbackQuery, db_session: AsyncSession):
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Загрузить JSON'")
    await call.message.answer("Загрузите JSON файл с задачами.")






# Обработчик для кнопки "Опубликовать задачу с переводами"
@router.callback_query(lambda call: call.data == "publish_task_with_translations")
async def publish_task_with_translations(call: CallbackQuery, db_session: AsyncSession):
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Опубликовать задачу с переводами'")

    # Находим самую старую неопубликованную задачу
    result = await db_session.execute(
        select(Task.translation_group_id)
        .where(Task.published.is_(False))
        .order_by(Task.id.asc())  # Самая старая задача
        .limit(1)
    )
    translation_group_id = result.scalar_one_or_none()

    if translation_group_id:
        # Публикуем одну задачу с её переводами
        await call.message.answer("Найдена неопубликованная задача. Начинаем публикацию.")
        success = await publish_task_by_translation_group(translation_group_id, call.message, db_session, call.bot)

        if success:
            await call.message.answer(f"Все переводы задачи с группой {translation_group_id} успешно опубликованы.")
        else:
            await call.message.answer("Произошла ошибка при публикации переводов.")
    else:
        # Если нет неопубликованных задач, находим самую старую задачу, опубликованную более месяца назад
        one_month_ago = datetime.now() - timedelta(days=30)
        result = await db_session.execute(
            select(Task.translation_group_id)
            .where(Task.published.is_(True))
            .where(Task.publish_date < one_month_ago)
            .order_by(Task.publish_date.asc())  # Самая старая по дате публикации
            .limit(1)
        )
        translation_group_id = result.scalar_one_or_none()

        if translation_group_id:
            await call.message.answer("Найдена задача, опубликованная более месяца назад. Публикуем её снова.")
            success = await publish_task_by_translation_group(translation_group_id, call.message, db_session, call.bot, reuse_image=True)

            if success:
                await call.message.answer(f"Задача с группой {translation_group_id} опубликована снова с обновлением даты.")
            else:
                await call.message.answer("Произошла ошибка при публикации перевода.")
        else:
            # Сообщаем, что нет задач для публикации
            await call.message.answer("Задач для публикации не найдено. Все задачи либо недавно опубликованы, либо неопубликованных задач нет.")