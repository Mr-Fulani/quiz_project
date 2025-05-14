# bot/handlers/feedback.py

import datetime
import logging
from datetime import datetime

from aiogram import types, Router
from aiogram.filters import StateFilter, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from bot.database.models import FeedbackMessage
from bot.database.database import get_session, AsyncSessionMaker  # Импорт из database.py
from bot.keyboards.quiz_keyboards import get_feedback_keyboard
from bot.states.admin_states import FeedbackStates

# Инициализация маршрутизатора
router = Router(name="feedback_router")

# Настройка логирования
logger = logging.getLogger(__name__)

# Обработчик кнопки "Написать Администратору"
@router.message(lambda message: message.text and message.text.lower() == "написать администратору")
async def handle_write_to_admin(message: types.Message):
    await message.answer("Ваше сообщение для администратора. Напишите текст, и он будет передан.")

# Фильтр для сообщений пользователей
class UserMessageFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        current_state = await state.get_state()
        return (
            message.text
            and message.text.lower() != "написать администратору"
            and current_state != FeedbackStates.awaiting_reply
        )

# Обработчик для сохранения сообщения пользователя
@router.message(UserMessageFilter())
async def save_feedback_message(message: types.Message):
    async with get_session() as session:
        feedback = FeedbackMessage(
            user_id=message.from_user.id,
            username=message.from_user.username,
            message=message.text,
            created_at=datetime.utcnow(),
            is_processed=False
        )
        session.add(feedback)
        await session.commit()
    await message.answer("Ваше сообщение сохранено, Мы ответим Вам в ближайшее время. Спасибо!")

# Обработчик для просмотра необработанных сообщений
@router.callback_query(lambda c: c.data == "view_feedback")
async def show_unprocessed_feedback(callback_query: types.CallbackQuery):
    logger.info("Обработчик 'Просмотреть сообщения' вызван.")
    async with get_session() as session:
        result = await session.execute(
            select(FeedbackMessage).where(FeedbackMessage.is_processed == False)
        )
        feedbacks = result.scalars().all()

    if not feedbacks:
        await callback_query.message.answer("Нет необработанных сообщений.")
        await callback_query.answer()
        return

    for feedback in feedbacks:
        feedback_text = (
            f"ID: {feedback.id}\n"
            f"Пользователь: @{feedback.username or 'Неизвестно'} (ID: {feedback.user_id})\n"
            f"Сообщение: {feedback.message}"
        )
        await callback_query.message.answer(feedback_text, reply_markup=get_feedback_keyboard(feedback.id))

    await callback_query.answer()

# Обработчик для пометки сообщения как обработанного
@router.callback_query(lambda c: c.data.startswith("mark_processed:"))
async def mark_feedback_processed(callback_query: types.CallbackQuery):
    logger.info(f"Callback 'mark_processed' вызван, user_id={callback_query.from_user.id}, data={callback_query.data}")
    feedback_id = int(callback_query.data.split(":")[1])

    async with get_session() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await callback_query.answer("Сообщение не найдено или уже обработано.", show_alert=True)
            return

        feedback.is_processed = True
        await session.commit()

    await callback_query.answer("Сообщение помечено как обработанное.", show_alert=True)
    await callback_query.message.delete()

# Обработчик для ответа на feedback
@router.message(StateFilter(FeedbackStates.awaiting_reply))
async def handle_feedback_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    feedback_id = data.get("feedback_id")
    user_id = data.get("user_id")

    if not feedback_id or not user_id:
        await message.answer("Ошибка: невозможно найти данные для ответа.")
        await state.clear()
        return

    async with get_session() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await message.answer("Сообщение пользователя не найдено.")
            await state.clear()
            return

        try:
            # Отправляем сообщение пользователю
            await message.bot.send_message(
                chat_id=user_id,
                text=f"Ответ от администратора:\n\nВаше сообщение: {feedback.message}\n\nОтвет: {message.text}"
            )
            feedback.is_processed = True
            await session.commit()

            # Подтверждение администратору
            await message.answer(f"✅ Ответ успешно отправлен пользователю @{feedback.username}")

            # Удаляем сообщение с кнопками
            try:
                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=message.message_id - 1
                )
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение с кнопками: {e}")

        except Exception as e:
            await message.answer(f"❌ Ошибка при отправке ответа: {str(e)}")
            logger.error(f"Ошибка отправки ответа: {e}")
        finally:
            await state.clear()

# Обработчик для начала ответа на сообщение
@router.callback_query(lambda c: c.data.startswith("reply_to_feedback:"))
async def start_feedback_reply(callback_query: types.CallbackQuery, state: FSMContext):
    logger.info(f"Callback 'reply_to_feedback' вызван, user_id={callback_query.from_user.id}, data={callback_query.data}")
    feedback_id = int(callback_query.data.split(":")[1])

    async with get_session() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await callback_query.answer("Сообщение не найдено.", show_alert=True)
            return

    # Сначала устанавливаем данные
    await state.update_data(feedback_id=feedback_id, user_id=feedback.user_id)
    # Затем устанавливаем состояние
    await state.set_state(FeedbackStates.awaiting_reply)

    await callback_query.message.answer(
        f"Введите ваш ответ для пользователя @{feedback.username}:\n"
        f"Исходное сообщение: {feedback.message}"
    )
    await callback_query.answer()

# Обработчик для удаления сообщения
@router.callback_query(lambda c: c.data.startswith("delete_feedback:"))
async def delete_feedback(callback_query: types.CallbackQuery):
    logger.info(f"Callback 'delete_feedback' вызван, user_id={callback_query.from_user.id}, data={callback_query.data}")
    feedback_id = int(callback_query.data.split(":")[1])

    async with get_session() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await callback_query.answer("Сообщение не найдено или уже удалено.", show_alert=True)
            return

        await session.delete(feedback)
        await session.commit()

    await callback_query.answer("Сообщение удалено.", show_alert=True)
    await callback_query.message.delete()