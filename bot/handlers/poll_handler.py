from aiogram import Router, types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.database.models import TelegramUser, TaskPoll, TaskStatistics
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = Router(name="poll_router")

# Text for the "I don't know but want to learn" option
DONT_KNOW_OPTION = "Не знаю, но хочу узнать"


@router.poll_answer()
async def handle_poll_answer(poll_answer: types.PollAnswer, db_session: AsyncSession):
    """
    Обрабатывает ответ пользователя на опрос (PollAnswer) и обновляет статистику в таблице task_statistics.
    Проверяет правильность ответа, обновляет или создаёт запись в TaskStatistics.
    Специально обрабатывает вариант "Не знаю, но хочу узнать" как неправильный ответ с показом объяснения.

    Args:
        poll_answer (types.PollAnswer): Объект ответа на опрос от пользователя.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для работы с базой данных.
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

    # Проверка на выбранный вариант "Не знаю, но хочу узнать"
    is_dont_know_selected = False
    dont_know_option_index = None

    if task_poll.poll_options and DONT_KNOW_OPTION in task_poll.poll_options:
        dont_know_option_index = task_poll.poll_options.index(DONT_KNOW_OPTION)
        is_dont_know_selected = dont_know_option_index in selected_option_ids

    # Определение правильного ответа
    correct_answer = translation.correct_answer
    try:
        correct_option_id = translation.answers.index(correct_answer)
    except ValueError:
        correct_option_id = None
        logger.error(f"Правильный ответ '{correct_answer}' не найден в опциях перевода {translation.id}")

    # Для обычных ответов - проверяем корректность
    # Для "Не знаю, но хочу узнать" - всегда считаем неправильным, но не показываем как ошибку в UI
    is_correct = False
    if is_dont_know_selected:
        # Это особый случай - будет отображено объяснение, но статистика учитывается как неправильный ответ
        is_correct = False
    else:
        # Обычная проверка правильности
        is_correct = (correct_option_id in selected_option_ids) if correct_option_id is not None else False

    # Ищем пользователя в БД
    user_query = select(TelegramUser).where(TelegramUser.telegram_id == user_id)
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

        # Если выбран вариант "Не знаю, но хочу узнать", отправляем объяснение
        if is_dont_know_selected and translation.explanation:
            # Логика показа объяснения из поля explanation
            # В зависимости от контекста использования, здесь может быть разная реализация
            # (отправка сообщения, открытие модального окна и т.д.)
            logger.info(f"Показываем объяснение для user={user_id}, task={task.id}")
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Ошибка при сохранении статистики: {e}")