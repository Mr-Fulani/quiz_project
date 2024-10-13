
import logging
from datetime import datetime

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

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
async def publish_by_id(call: CallbackQuery, db_session: AsyncSession):
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Опубликовать опрос по ID'")
    await call.message.answer("Введите ID задачи для публикации.")
    temp_data[call.from_user.id] = 'awaiting_task_id'




# Обработчик для получения ID от пользователя
@router.message(F.text.regexp(r'^\d+$'))  # Ожидаем только число (ID задачи)
async def receive_task_id(message: types.Message, db_session: AsyncSession, state: FSMContext):
    user_id = message.from_user.id

    # Проверяем, находится ли пользователь в состоянии ожидания ID
    if temp_data.get(user_id) == 'awaiting_task_id':
        try:
            task_id = int(message.text)
            logger.info(f"Получен ID задачи для публикации: {task_id} от пользователя {message.from_user.username}")

            # Выполняем запрос для получения задачи
            result = await db_session.execute(
                select(Task)
                .options(joinedload(Task.topic), joinedload(Task.subtopic))  # Подгружаем связанные данные topic
                .where(Task.id == task_id)
            )
            task = result.scalar_one_or_none()

            if task is None:
                # Задача не найдена
                await message.answer(f"Задача с ID {task_id} не найдена. Пожалуйста, попробуйте снова.")
                return

            if task.published:
                # Задача уже опубликована
                await message.answer(f"Задача с ID {task_id} уже была опубликована.")
                return

            # Публикуем задачу
            task.published = True
            task.publish_date = datetime.now()
            await db_session.commit()

            # Формируем сообщение о публикации
            response_message = f"Задача ID {task.id} опубликована!\n"
            response_message += f"Тема: {task.topic.name}\n"  # Заранее загруженная тема
            if task.subtopic:
                response_message += f"Подтема: {task.subtopic.name}\n"
            response_message += f"Сложность: {task.difficulty}\n"
            response_message += f"Ссылка на ресурс: {task.external_link}\n"

            await message.answer(response_message)
            logger.info(f"Задача с ID {task.id} успешно опубликована.")

        except Exception as e:
            logger.error(f"Ошибка при обработке ID задачи: {e}")
            await db_session.rollback()
            await message.answer("Произошла ошибка при обработке задачи. Попробуйте снова.")

        finally:
            # Очистка временных данных
            temp_data.pop(user_id, None)
            await state.clear()

    else:
        # Если пользователь прислал ID, когда бот не ждет ID, отправляем уведомление
        await message.answer("Я не ожидал ID задачи. Пожалуйста, воспользуйтесь соответствующей командой.")




# Обработчик для кнопки "Загрузить JSON"
@router.callback_query(lambda call: call.data == "upload_json")
async def upload_json(call: CallbackQuery, db_session: AsyncSession):
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Загрузить JSON'")
    await call.message.answer("Загрузите JSON файл с задачами.")



# Обработчик для кнопки "Опубликовать по две"
@router.callback_query(lambda call: call.data == "publish_two_tasks")
async def publish_two_tasks(call: CallbackQuery, db_session: AsyncSession):
    logger.info(f"Пользователь {call.from_user.username} ({call.from_user.id}) нажал на 'Опубликовать по две'")
    await call.message.answer("Функция публикации по две задачи в разработке.")