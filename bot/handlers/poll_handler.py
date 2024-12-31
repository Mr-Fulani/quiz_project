# bot/handlers/poll_handler.py

from aiogram import Router, types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.database.models import User, TaskPoll, TaskStatistics
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = Router(name="poll_router")

@router.poll_answer()
async def handle_poll_answer(poll_answer: types.PollAnswer, db_session: AsyncSession):
    """
    Обработчик ответа на опрос (PollAnswer).
    Обновляет статистику пользователя (TaskStatistics) в зависимости от правильности ответа.
    """
    logger.info(f"Получен PollAnswer: {poll_answer}")
    user_id = poll_answer.user.id

    # Если это бот, игнорируем
    if poll_answer.user.is_bot:
        logger.debug(f"PollAnswer от бота ID={user_id}, пропускаем.")
        return

    poll_id = poll_answer.poll_id
    selected_option_ids = poll_answer.option_ids
    logger.info(f"PollAnswer от user={user_id}, poll_id={poll_id}, варианты={selected_option_ids}")

    # Ищем TaskPoll
    query_poll = select(TaskPoll).where(TaskPoll.poll_id == poll_id)
    result_poll = await db_session.execute(query_poll)
    task_poll = result_poll.scalar_one_or_none()
    if not task_poll:
        logger.warning(f"Не найден TaskPoll с poll_id={poll_id}")
        return

    task = task_poll.task
    translation = task_poll.translation

    if not translation:
        logger.warning(f"Нет translation в task_poll id={task_poll.id}")
        return

    correct_answer = translation.correct_answer
    try:
        correct_option_id = translation.answers.index(correct_answer)
    except ValueError:
        correct_option_id = None
        logger.error(f"Правильный ответ '{correct_answer}' не найден в опциях перевода {translation.id}")

    is_correct = (correct_option_id in selected_option_ids) if correct_option_id is not None else False

    # Ищем пользователя в БД
    user_query = select(User).where(User.telegram_id == user_id)
    user_result = await db_session.execute(user_query)
    user = user_result.scalar_one_or_none()
    if not user:
        logger.warning(f"Пользователь {user_id} не найден в БД, не можем записать статистику.")
        return

    # Ищем или создаём статистику
    stats_query = select(TaskStatistics).where(
        TaskStatistics.user_id == user.id,
        TaskStatistics.task_id == task.id
    )
    stats_result = await db_session.execute(stats_query)
    stats = stats_result.scalar_one_or_none()

    if not stats:
        stats = TaskStatistics(
            user_id=user.id,
            task_id=task.id,
            attempts=1,
            successful=is_correct,
            last_attempt_date=datetime.now(timezone.utc)
        )
        db_session.add(stats)
    else:
        stats.attempts += 1
        if is_correct:
            stats.successful = True
        stats.last_attempt_date = datetime.now(timezone.utc)

    try:
        await db_session.commit()
        logger.info(f"Статистика обновлена. user={user_id}, task={task.id}, is_correct={is_correct}")
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Ошибка при сохранении статистики: {e}")