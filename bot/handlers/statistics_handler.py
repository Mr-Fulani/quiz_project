import csv
import io
import logging
import calendar
from datetime import datetime, timedelta
from operator import or_

from aiogram import F
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, case, and_, or_, update, literal, String, text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.quiz_keyboards import get_admin_channels_keyboard
from bot.services.admin_service import is_admin
from bot.states.admin_states import UserStatsState
from bot.utils.markdownV2 import escape_markdown
from bot.database.models import TelegramUser, TaskStatistics, UserChannelSubscription, TelegramGroup

logger = logging.getLogger(__name__)
router = Router(name="statistics_router")


# ------------------------------------------------------------------------------
# Функции обновления статуса подписки
# ------------------------------------------------------------------------------

async def update_single_user_subscription_status(user: TelegramUser, db_session: AsyncSession):
    """
    Проверяет наличие активных подписок для одного пользователя.
    Если активных подписок нет, обновляет subscription_status на 'inactive' в таблице telegram_users.

    Args:
        user (TelegramUser): Объект пользователя Telegram.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для работы с базой данных.
    """
    active_subs_query = select(func.count()).select_from(UserChannelSubscription).where(
        UserChannelSubscription.telegram_user_id == user.id,
        UserChannelSubscription.subscription_status == 'active'
    )
    active_subs = (await db_session.execute(active_subs_query)).scalar() or 0
    if active_subs == 0 and user.subscription_status != 'inactive':
        user.subscription_status = 'inactive'
        db_session.add(user)
        await db_session.commit()


async def update_all_users_subscription_statuses(db_session: AsyncSession):
    """
    Обновляет статус подписки для всех пользователей в таблице telegram_users.
    Устанавливает subscription_status='inactive' для пользователей, у которых нет активных подписок
    в таблице user_channel_subscriptions.

    Args:
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для работы с базой данных.
    """
    subquery = select(UserChannelSubscription.telegram_user_id).where(
        UserChannelSubscription.subscription_status == 'active'
    ).distinct()
    stmt = update(TelegramUser).where(
        TelegramUser.id.not_in(subquery),
        TelegramUser.subscription_status != 'inactive'
    ).values(subscription_status='inactive')
    await db_session.execute(stmt)
    await db_session.commit()


# ------------------------------------------------------------------------------
# Функции вычисления границ периода
# ------------------------------------------------------------------------------

def get_current_month_boundaries() -> tuple[datetime, datetime]:
    """
    Возвращает начало и конец текущего месяца в UTC.

    Returns:
        tuple[datetime, datetime]: Начало и конец текущего месяца.
    """
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = calendar.monthrange(now.year, now.month)[1]
    end_of_month = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
    return start_of_month, end_of_month


def get_current_week_boundaries() -> tuple[datetime, datetime]:
    """
    Возвращает начало (понедельник) и конец (воскресенье) текущей недели в UTC.

    Returns:
        tuple[datetime, datetime]: Начало и конец текущей недели.
    """
    now = datetime.utcnow()
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
    return start_of_week, end_of_week


def get_current_quarter_boundaries() -> tuple[datetime, datetime]:
    """
    Возвращает начало и конец текущего квартала в UTC.

    Returns:
        tuple[datetime, datetime]: Начало и конец текущего квартала.
    """
    now = datetime.utcnow()
    current_month = now.month
    quarter = (current_month - 1) // 3 + 1
    start_month = 3 * (quarter - 1) + 1
    start_of_quarter = now.replace(month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    end_month = start_month + 2
    last_day = calendar.monthrange(now.year, end_month)[1]
    end_of_quarter = now.replace(month=end_month, day=last_day, hour=23, minute=59, second=59, microsecond=999999)
    return start_of_quarter, end_of_quarter


async def get_mini_app_users_count(db_session: AsyncSession, start_date: datetime, end_date: datetime) -> int:
    """
    Подсчитывает количество новых пользователей Mini App за указанный период.
    Использует прямые SQL запросы к таблице Django mini_app_users.

    Args:
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        start_date (datetime): Начало периода.
        end_date (datetime): Конец периода.

    Returns:
        int: Количество новых пользователей Mini App за период.
    """
    try:
        # Используем параметризованный запрос для безопасности
        # Сырой SQL не покрывается автофильтром тенанта (bot/tenancy.py) — тенант указываем сами
        from bot.tenancy import current_tenant_id
        tenant_id = current_tenant_id.get()
        query = text("""
            SELECT COUNT(*)
            FROM mini_app_users
            WHERE created_at >= :start_date AND created_at <= :end_date
              AND (CAST(:tenant_id AS BIGINT) IS NULL OR tenant_id = :tenant_id OR tenant_id IS NULL)
        """)
        result = await db_session.execute(
            query,
            {"start_date": start_date, "end_date": end_date, "tenant_id": tenant_id}
        )
        count = result.scalar() or 0
        return count
    except Exception as e:
        logger.error(f"[get_mini_app_users_count] Ошибка при подсчете пользователей Mini App: {e}")
        return 0


# ------------------------------------------------------------------------------
# Команды для отображения статистики
# ------------------------------------------------------------------------------

@router.message(Command(commands=["mystatistics"]))
async def my_statistics(message: types.Message, db_session: AsyncSession):
    """
    Обрабатывает команду /mystatistics для отображения статистики текущего пользователя.
    Показывает количество попыток, успешных ответов и процент успеха по задачам.

    Args:
        message (types.Message): Сообщение от пользователя с командой.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для работы с базой данных.
    """
    telegram_id = message.from_user.id
    logger.info(f"[my_statistics] Запрос статистики от пользователя {telegram_id}")

    query = select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
    result = await db_session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"[my_statistics] Пользователь {telegram_id} не найден.")
        await message.reply("❌ Вы не зарегистрированы в системе.")
        return

    # Обновляем статус, если нет активных подписок
    await update_single_user_subscription_status(user, db_session)

    query_stats = select(TaskStatistics).where(TaskStatistics.user_id == user.id)
    stats_result = await db_session.execute(query_stats)
    stats = stats_result.scalars().all()

    if not stats:
        await message.answer("📄 У вас пока нет статистики по задачам.")
        logger.info(f"[my_statistics] У пользователя {telegram_id} нет статистики.")
        return

    total_attempts = sum(stat.attempts for stat in stats)
    total_successful = sum(1 for stat in stats if stat.successful)
    success_rate = (total_successful / total_attempts * 100) if total_attempts else 0

    response = (
        f"📊 *Ваша статистика по задачам:*\n\n"
        f"• *Всего попыток*: {escape_markdown(str(total_attempts))}\n"
        f"• *Успешных ответов*: {escape_markdown(str(total_successful))}\n"
        f"• *Процент успешных ответов*: {escape_markdown(f'{success_rate:.2f}%')}\n\n"
        f"*Детальная статистика по задачам:*\n"
    )

    for stat in stats:
        task = stat.task
        if not task:
            continue
        publish_date = task.publish_date.strftime('%Y-%m-%d %H:%M:%S') if task.publish_date else "Не опубликована"
        last_attempt = stat.last_attempt_date.strftime('%Y-%m-%d %H:%M:%S') if stat.last_attempt_date else "Нет попыток"
        topic_name = task.topic.name if task.topic else "Без темы"

        response += (
            f"• *Задача {escape_markdown(str(task.id))}*\n"
            f"  - *Тема*: {escape_markdown(topic_name)}\n"
            f"  - *Попыток*: {escape_markdown(str(stat.attempts))}\n"
            f"  - *Успешных*: {'Да' if stat.successful else 'Нет'}\n"
            f"  - *Последняя попытка*: {escape_markdown(last_attempt)}\n"
            f"  - *Дата публикации*: {escape_markdown(publish_date)}\n\n"
        )

    await message.answer(response, parse_mode="MarkdownV2")
    logger.info(f"[my_statistics] Статистика для пользователя {telegram_id} отправлена.")


@router.callback_query(F.data == "mystatistics")
async def callback_mystatistics(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Обрабатывает callback-кнопку 'mystatistics' для отображения статистики пользователя.
    Вызывает ту же логику, что и команда /mystatistics.

    Args:
        call (types.CallbackQuery): Callback-запрос от кнопки.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для работы с базой данных.
    """
    telegram_id = call.from_user.id
    logger.info(f"[callback_mystatistics] Нажата кнопка 'моя статистика' пользователем {telegram_id}")

    # Ищем пользователя
    query = select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
    result = await db_session.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        await call.message.answer("❌ Вы не зарегистрированы в системе.")
        await call.answer()
        return

    await update_single_user_subscription_status(user, db_session)

    # Получаем статистику
    query_stats = select(TaskStatistics).where(TaskStatistics.user_id == user.id)
    stats_result = await db_session.execute(query_stats)
    stats = stats_result.scalars().all()

    if not stats:
        await call.message.answer("📄 У вас пока нет статистики по задачам.")
        await call.answer()
        return

    total_attempts = sum(stat.attempts for stat in stats)
    total_successful = sum(1 for stat in stats if stat.successful)
    success_rate = (total_successful / total_attempts * 100) if total_attempts else 0

    response = (
        f"📊 *Ваша статистика по задачам (кнопка):*\n\n"
        f"• *Всего попыток*: {escape_markdown(str(total_attempts))}\n"
        f"• *Успешных ответов*: {escape_markdown(str(total_successful))}\n"
        f"• *Процент успешных ответов*: {escape_markdown(f'{success_rate:.2f}%')}\n\n"
        f"*Детальная статистика по задачам:*\n"
    )

    for stat in stats:
        task = stat.task
        if not task:
            continue
        publish_date = task.publish_date.strftime('%Y-%m-%d %H:%M:%S') if task.publish_date else "Не опубликована"
        last_attempt = stat.last_attempt_date.strftime('%Y-%m-%d %H:%M:%S') if stat.last_attempt_date else "Нет попыток"
        topic_name = task.topic.name if task.topic else "Без темы"

        response += (
            f"• *Задача {escape_markdown(str(task.id))}*\n"
            f"  - *Тема*: {escape_markdown(topic_name)}\n"
            f"  - *Попыток*: {escape_markdown(str(stat.attempts))}\n"
            f"  - *Успешных*: {'Да' if stat.successful else 'Нет'}\n"
            f"  - *Последняя попытка*: {escape_markdown(last_attempt)}\n"
            f"  - *Дата публикации*: {escape_markdown(publish_date)}\n\n"
        )

    await call.message.answer(response, parse_mode="MarkdownV2")
    await call.answer()


def escape_markdown_v2(text: str) -> str:
    """
    Экранирует специальные символы для формата MarkdownV2 в Telegram.

    Args:
        text (str): Входная строка для экранирования.

    Returns:
        str: Экранированная строка, безопасная для MarkdownV2.
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text




@router.message(Command(commands=["allstats"]))
async def all_statistics(message: types.Message, db_session: AsyncSession):
    """
    Показывает админам статистику пользователей и активности в каналах за месяц, неделю, квартал.

    Args:
        message (types.Message): Сообщение с командой /allstats.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    admin_id = message.from_user.id
    logger.info(f"[all_statistics] Админ {admin_id} запросил общую статистику с детализацией по периодам.")

    if not await is_admin(admin_id, db_session):
        await message.answer("⚠️ У вас нет прав для выполнения этой команды.")
        return

    try:
        await update_all_users_subscription_statuses(db_session)

        # Границы периодов
        start_month, end_month = get_current_month_boundaries()
        start_week, end_week = get_current_week_boundaries()
        start_quarter, end_quarter = get_current_quarter_boundaries()

        # Общие показатели
        total_users = (await db_session.execute(select(func.count(TelegramUser.id)))).scalar() or 0
        active_users = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(TelegramUser.subscription_status == 'active'))).scalar() or 0
        inactive_users = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(TelegramUser.subscription_status == 'inactive'))).scalar() or 0
        active_in_bot = (await db_session.execute(
            select(func.count(func.distinct(TaskStatistics.user_id))))).scalar() or 0
        bot_activity_pct = (active_in_bot / total_users * 100) if total_users > 0 else 0.0

        # Статистика за текущий месяц
        subscribed_month = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(
                    TelegramUser.subscription_status == 'active',
                    TelegramUser.created_at.between(start_month, end_month)
                )
            )
        )).scalar() or 0
        unsubscribed_month = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(
                    TelegramUser.subscription_status == 'inactive',
                    TelegramUser.deactivated_at.between(start_month, end_month)
                )
            )
        )).scalar() or 0
        mini_app_users_month = await get_mini_app_users_count(db_session, start_month, end_month)

        channel_activity_query_month = select(
            TelegramGroup.group_name,
            TelegramGroup.username,
            func.count(case((UserChannelSubscription.subscription_status == 'active', 1))).label('gained'),
            func.count(case((UserChannelSubscription.subscription_status == 'inactive', 1))).label('lost')
        ).join(
            UserChannelSubscription, UserChannelSubscription.channel_id == TelegramGroup.group_id
        ).where(
            or_(
                and_(
                    UserChannelSubscription.subscription_status == 'active',
                    UserChannelSubscription.subscribed_at.between(start_month, end_month)
                ),
                and_(
                    UserChannelSubscription.subscription_status == 'inactive',
                    UserChannelSubscription.unsubscribed_at.between(start_month, end_month)
                )
            )
        ).group_by(TelegramGroup.group_name, TelegramGroup.username)
        channel_activity_month = (await db_session.execute(channel_activity_query_month)).all()
        total_gained_month = sum(g for _, _, g, _ in channel_activity_month)
        total_lost_month = sum(l for _, _, _, l in channel_activity_month)
        overall_channel_activity_month = (f"+{total_gained_month} подписок / -{total_lost_month} отписок"
                                          if (total_gained_month + total_lost_month) > 0
                                          else "Нет изменений")

        # Статистика за текущую неделю
        subscribed_week = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(
                    TelegramUser.subscription_status == 'active',
                    TelegramUser.created_at.between(start_week, end_week)
                )
            )
        )).scalar() or 0
        unsubscribed_week = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(
                    TelegramUser.subscription_status == 'inactive',
                    TelegramUser.deactivated_at.between(start_week, end_week)
                )
            )
        )).scalar() or 0
        mini_app_users_week = await get_mini_app_users_count(db_session, start_week, end_week)

        channel_activity_query_week = select(
            TelegramGroup.group_name,
            TelegramGroup.username,
            func.count(case((UserChannelSubscription.subscription_status == 'active', 1))).label('gained'),
            func.count(case((UserChannelSubscription.subscription_status == 'inactive', 1))).label('lost')
        ).join(
            UserChannelSubscription, UserChannelSubscription.channel_id == TelegramGroup.group_id
        ).where(
            or_(
                and_(
                    UserChannelSubscription.subscription_status == 'active',
                    UserChannelSubscription.subscribed_at.between(start_week, end_week)
                ),
                and_(
                    UserChannelSubscription.subscription_status == 'inactive',
                    UserChannelSubscription.unsubscribed_at.between(start_week, end_week)
                )
            )
        ).group_by(TelegramGroup.group_name, TelegramGroup.username)
        channel_activity_week = (await db_session.execute(channel_activity_query_week)).all()
        total_gained_week = sum(g for _, _, g, _ in channel_activity_week)
        total_lost_week = sum(l for _, _, _, l in channel_activity_week)
        overall_channel_activity_week = (f"+{total_gained_week} подписок / -{total_lost_week} отписок"
                                         if (total_gained_week + total_lost_week) > 0
                                         else "Нет изменений")

        # Статистика за текущий квартал
        subscribed_quarter = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(
                    TelegramUser.subscription_status == 'active',
                    TelegramUser.created_at.between(start_quarter, end_quarter)
                )
            )
        )).scalar() or 0
        unsubscribed_quarter = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(
                    TelegramUser.subscription_status == 'inactive',
                    TelegramUser.deactivated_at.between(start_quarter, end_quarter)
                )
            )
        )).scalar() or 0
        mini_app_users_quarter = await get_mini_app_users_count(db_session, start_quarter, end_quarter)

        channel_activity_query_quarter = select(
            TelegramGroup.group_name,
            TelegramGroup.username,
            func.count(case((UserChannelSubscription.subscription_status == 'active', 1))).label('gained'),
            func.count(case((UserChannelSubscription.subscription_status == 'inactive', 1))).label('lost')
        ).join(
            UserChannelSubscription, UserChannelSubscription.channel_id == TelegramGroup.group_id
        ).where(
            or_(
                and_(
                    UserChannelSubscription.subscription_status == 'active',
                    UserChannelSubscription.subscribed_at.between(start_quarter, end_quarter)
                ),
                and_(
                    UserChannelSubscription.subscription_status == 'inactive',
                    UserChannelSubscription.unsubscribed_at.between(start_quarter, end_quarter)
                )
            )
        ).group_by(TelegramGroup.group_name, TelegramGroup.username)
        channel_activity_quarter = (await db_session.execute(channel_activity_query_quarter)).all()
        total_gained_quarter = sum(g for _, _, g, _ in channel_activity_quarter)
        total_lost_quarter = sum(l for _, _, _, l in channel_activity_quarter)
        overall_channel_activity_quarter = (f"+{total_gained_quarter} подписок / -{total_lost_quarter} отписок"
                                            if (total_gained_quarter + total_lost_quarter) > 0
                                            else "Нет изменений")

        # Формирование итогового сообщения с правильным экранированием
        response = "📊 *Общая статистика*\n\n"
        response += f"• *Всего пользователей*: {escape_markdown_v2(str(total_users))}\n"
        response += f"• *Активных*: {escape_markdown_v2(str(active_users))}\n"
        response += f"• *Неактивных*: {escape_markdown_v2(str(inactive_users))}\n"
        response += f"• *Активность в боте*: {escape_markdown_v2(f'{bot_activity_pct:.2f}%')}\n\n"

        # Форматирование дат с правильным экранированием
        month_dates = f"{escape_markdown_v2(start_month.strftime('%Y-%m-%d'))} — {escape_markdown_v2(end_month.strftime('%Y-%m-%d'))}"
        week_dates = f"{escape_markdown_v2(start_week.strftime('%Y-%m-%d'))} — {escape_markdown_v2(end_week.strftime('%Y-%m-%d'))}"
        quarter_dates = f"{escape_markdown_v2(start_quarter.strftime('%Y-%m-%d'))} — {escape_markdown_v2(end_quarter.strftime('%Y-%m-%d'))}"

        # Форматирование активности в каналах
        month_activity = escape_markdown_v2(f"+{total_gained_month} подписок / -{total_lost_month} отписок" if (total_gained_month + total_lost_month) > 0 else "Нет изменений")
        week_activity = escape_markdown_v2(f"+{total_gained_week} подписок / -{total_lost_week} отписок" if (total_gained_week + total_lost_week) > 0 else "Нет изменений")
        quarter_activity = escape_markdown_v2(f"+{total_gained_quarter} подписок / -{total_lost_quarter} отписок" if (total_gained_quarter + total_lost_quarter) > 0 else "Нет изменений")

        response += f"*За текущий месяц* \\({month_dates}\\):\n"
        response += f"  • Подписались: {escape_markdown_v2(str(subscribed_month))}\n"
        response += f"  • Отписались: {escape_markdown_v2(str(unsubscribed_month))}\n"
        response += f"  • Новые Mini App: {escape_markdown_v2(str(mini_app_users_month))}\n"
        response += f"  • Активность в каналах: {month_activity}\n\n"

        response += f"*За текущую неделю* \\({week_dates}\\):\n"
        response += f"  • Подписались: {escape_markdown_v2(str(subscribed_week))}\n"
        response += f"  • Отписались: {escape_markdown_v2(str(unsubscribed_week))}\n"
        response += f"  • Новые Mini App: {escape_markdown_v2(str(mini_app_users_week))}\n"
        response += f"  • Активность в каналах: {week_activity}\n\n"

        response += f"*За текущий квартал* \\({quarter_dates}\\):\n"
        response += f"  • Подписались: {escape_markdown_v2(str(subscribed_quarter))}\n"
        response += f"  • Отписались: {escape_markdown_v2(str(unsubscribed_quarter))}\n"
        response += f"  • Новые Mini App: {escape_markdown_v2(str(mini_app_users_quarter))}\n"
        response += f"  • Активность в каналах: {quarter_activity}\n"

        # Детальная активность по каналам
        response += "\n*Детальная активность по каналам:*\n"
        for group_name, username, gained, lost in channel_activity_month:
            if username:
                # Экранируем все специальные символы в названии группы
                safe_group_name = escape_markdown_v2(group_name)
                safe_username = escape_markdown_v2(username)
                channel_link = f"[{safe_group_name}](https://t\\.me/{safe_username})"
            else:
                channel_link = escape_markdown_v2(group_name)

            stats = f"\\+{gained} / \\-{lost}"
            response += f"  • {channel_link}: {stats}\n"

        await message.answer(response, parse_mode="MarkdownV2", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"[all_statistics] Ошибка: {e}")
        await message.answer("❌ Ошибка при получении общей статистики.")




@router.callback_query(F.data == "allstats")
async def callback_allstats(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Показывает админам статистику пользователей и каналов по нажатию кнопки 'allstats'.

    Args:
        call (types.CallbackQuery): Callback-запрос от кнопки.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    admin_id = call.from_user.id
    logger.info(f"Пользователь {admin_id} запросил общую статистику с детализацией.")

    if not await is_admin(admin_id, db_session):
        await call.message.reply("⚠️ У вас нет прав для выполнения этой команды.")
        await call.answer()
        return

    try:
        await update_all_users_subscription_statuses(db_session)
        start_month, end_month = get_current_month_boundaries()
        start_week, end_week = get_current_week_boundaries()
        start_quarter, end_quarter = get_current_quarter_boundaries()

        total_users = (await db_session.execute(select(func.count(TelegramUser.id)))).scalar() or 0
        active_users = (await db_session.execute(select(func.count(TelegramUser.id)).where(TelegramUser.subscription_status == 'active'))).scalar() or 0
        inactive_users = (await db_session.execute(select(func.count(TelegramUser.id)).where(TelegramUser.subscription_status == 'inactive'))).scalar() or 0
        active_in_bot = (await db_session.execute(select(func.count(func.distinct(TaskStatistics.user_id))))).scalar() or 0
        bot_activity_pct = (active_in_bot / total_users * 100) if total_users > 0 else 0.0

        # Статистика за месяц
        subscribed_month = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(TelegramUser.subscription_status == 'active', TelegramUser.created_at.between(start_month, end_month))
            )
        )).scalar() or 0
        unsubscribed_month = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(TelegramUser.subscription_status == 'inactive', TelegramUser.deactivated_at.between(start_month, end_month))
            )
        )).scalar() or 0
        mini_app_users_month = await get_mini_app_users_count(db_session, start_month, end_month)
        channel_activity_query_month = select(
            TelegramGroup.group_name,
            TelegramGroup.username,
            func.count(case((UserChannelSubscription.subscription_status == 'active', 1))).label('gained'),
            func.count(case((UserChannelSubscription.subscription_status == 'inactive', 1))).label('lost')
        ).join(
            UserChannelSubscription, UserChannelSubscription.channel_id == TelegramGroup.group_id
        ).where(
            or_(
                and_(UserChannelSubscription.subscription_status == 'active', UserChannelSubscription.subscribed_at.between(start_month, end_month)),
                and_(UserChannelSubscription.subscription_status == 'inactive', UserChannelSubscription.unsubscribed_at.between(start_month, end_month))
            )
        ).group_by(TelegramGroup.group_name, TelegramGroup.username)
        channel_activity_month = (await db_session.execute(channel_activity_query_month)).all()
        total_gained_month = sum(g for _, _, g, _ in channel_activity_month)
        total_lost_month = sum(l for _, _, _, l in channel_activity_month)
        overall_channel_activity_month = (
            f"+{total_gained_month} подписок / -{total_lost_month} отписок"
            if (total_gained_month + total_lost_month) > 0 else "Нет изменений"
        )

        # Статистика за неделю
        subscribed_week = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(TelegramUser.subscription_status == 'active', TelegramUser.created_at.between(start_week, end_week))
            )
        )).scalar() or 0
        unsubscribed_week = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(TelegramUser.subscription_status == 'inactive', TelegramUser.deactivated_at.between(start_week, end_week))
            )
        )).scalar() or 0
        mini_app_users_week = await get_mini_app_users_count(db_session, start_week, end_week)
        channel_activity_query_week = select(
            TelegramGroup.group_name,
            TelegramGroup.username,
            func.count(case((UserChannelSubscription.subscription_status == 'active', 1))).label('gained'),
            func.count(case((UserChannelSubscription.subscription_status == 'inactive', 1))).label('lost')
        ).join(
            UserChannelSubscription, UserChannelSubscription.channel_id == TelegramGroup.group_id
        ).where(
            or_(
                and_(UserChannelSubscription.subscription_status == 'active', UserChannelSubscription.subscribed_at.between(start_week, end_week)),
                and_(UserChannelSubscription.subscription_status == 'inactive', UserChannelSubscription.unsubscribed_at.between(start_week, end_week))
            )
        ).group_by(TelegramGroup.group_name, TelegramGroup.username)
        channel_activity_week = (await db_session.execute(channel_activity_query_week)).all()
        total_gained_week = sum(g for _, _, g, _ in channel_activity_week)
        total_lost_week = sum(l for _, _, _, l in channel_activity_week)
        overall_channel_activity_week = (f"+{total_gained_week} подписок / -{total_lost_week} отписок"
                                         if (total_gained_week + total_lost_week) > 0 else "Нет изменений")

        # Статистика за квартал
        subscribed_quarter = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(TelegramUser.subscription_status == 'active', TelegramUser.created_at.between(start_quarter, end_quarter))
            )
        )).scalar() or 0
        unsubscribed_quarter = (await db_session.execute(
            select(func.count(TelegramUser.id)).where(
                and_(TelegramUser.subscription_status == 'inactive', TelegramUser.deactivated_at.between(start_quarter, end_quarter))
            )
        )).scalar() or 0
        mini_app_users_quarter = await get_mini_app_users_count(db_session, start_quarter, end_quarter)
        channel_activity_query_quarter = select(
            TelegramGroup.group_name,
            TelegramGroup.username,
            func.count(case((UserChannelSubscription.subscription_status == 'active', 1))).label('gained'),
            func.count(case((UserChannelSubscription.subscription_status == 'inactive', 1))).label('lost')
        ).join(
            UserChannelSubscription, UserChannelSubscription.channel_id == TelegramGroup.group_id
        ).where(
            or_(
                and_(UserChannelSubscription.subscription_status == 'active', UserChannelSubscription.subscribed_at.between(start_quarter, end_quarter)),
                and_(UserChannelSubscription.subscription_status == 'inactive', UserChannelSubscription.unsubscribed_at.between(start_quarter, end_quarter))
            )
        ).group_by(TelegramGroup.group_name, TelegramGroup.username)
        channel_activity_quarter = (await db_session.execute(channel_activity_query_quarter)).all()
        total_gained_quarter = sum(g for _, _, g, _ in channel_activity_quarter)
        total_lost_quarter = sum(l for _, _, _, l in channel_activity_quarter)
        overall_channel_activity_quarter = (f"+{total_gained_quarter} подписок / -{total_lost_quarter} отписок"
                                            if (total_gained_quarter + total_lost_quarter) > 0 else "Нет изменений")

        # Детальная активность по каналам с правильным экранированием
        detailed_activity = "\n\n*Детальная активность по каналам и группам:*\n"
        for group_name, username, gained, lost in channel_activity_month:
            if username:
                safe_group_name = escape_markdown_v2(group_name)
                safe_username = escape_markdown_v2(username)
                channel_link = f"[{safe_group_name}](https://t\\.me/{safe_username})"
            else:
                channel_link = escape_markdown_v2(group_name)

            stats = f"\\+{gained} / \\-{lost}"
            detailed_activity += f"  • {channel_link}: {stats}\n"

        # Форматирование основного ответа
        response = "📊 *Общая статистика*\n\n"
        response += f"• *Всего пользователей*: {escape_markdown_v2(str(total_users))}\n"
        response += f"• *Активных*: {escape_markdown_v2(str(active_users))}\n"
        response += f"• *Неактивных*: {escape_markdown_v2(str(inactive_users))}\n"
        response += f"• *Активность в боте*: {escape_markdown_v2(f'{bot_activity_pct:.2f}%')}\n\n"

        # Форматирование дат
        month_dates = f"{start_month.strftime('%Y-%m-%d')} — {end_month.strftime('%Y-%m-%d')}"
        week_dates = f"{start_week.strftime('%Y-%m-%d')} — {end_week.strftime('%Y-%m-%d')}"
        quarter_dates = f"{start_quarter.strftime('%Y-%m-%d')} — {end_quarter.strftime('%Y-%m-%d')}"

        month_dates = escape_markdown_v2(month_dates)
        week_dates = escape_markdown_v2(week_dates)
        quarter_dates = escape_markdown_v2(quarter_dates)

        response += f"*За текущий месяц* \\({month_dates}\\):\n"
        response += f"  • Подписались: {escape_markdown_v2(str(subscribed_month))}\n"
        response += f"  • Отписались: {escape_markdown_v2(str(unsubscribed_month))}\n"
        response += f"  • Новые Mini App: {escape_markdown_v2(str(mini_app_users_month))}\n"
        response += f"  • Активность в каналах: {escape_markdown_v2(overall_channel_activity_month)}\n\n"

        response += f"*За текущую неделю* \\({week_dates}\\):\n"
        response += f"  • Подписались: {escape_markdown_v2(str(subscribed_week))}\n"
        response += f"  • Отписались: {escape_markdown_v2(str(unsubscribed_week))}\n"
        response += f"  • Новые Mini App: {escape_markdown_v2(str(mini_app_users_week))}\n"
        response += f"  • Активность в каналах: {escape_markdown_v2(overall_channel_activity_week)}\n\n"

        response += f"*За текущий квартал* \\({quarter_dates}\\):\n"
        response += f"  • Подписались: {escape_markdown_v2(str(subscribed_quarter))}\n"
        response += f"  • Отписались: {escape_markdown_v2(str(unsubscribed_quarter))}\n"
        response += f"  • Новые Mini App: {escape_markdown_v2(str(mini_app_users_quarter))}\n"
        response += f"  • Активность в каналах: {escape_markdown_v2(overall_channel_activity_quarter)}\n"

        response += detailed_activity

        await call.message.reply(response, parse_mode="MarkdownV2", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"[callback_allstats] Ошибка: {e}")
        await call.message.reply("❌ Ошибка при получении общей статистики.")
    finally:
        await call.answer()




@router.callback_query(F.data == "userstats")
async def start_userstats_callback(call: types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Начинает процесс ввода Telegram ID для просмотра статистики конкретного пользователя.
    Устанавливает состояние ожидания ввода ID.

    Args:
        call (types.CallbackQuery): Callback-запрос от кнопки.
        state (FSMContext): Контекст состояний для управления FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для работы с базой данных.
    """
    admin_id = call.from_user.id
    if not await is_admin(admin_id, db_session):
        await call.message.reply("⚠️ У вас нет прав для выполнения этой команды.")
        await call.answer()
        return

    await state.set_state(UserStatsState.waiting_for_telegram_id)
    await call.message.answer("Введите Telegram ID пользователя для просмотра статистики.")
    await call.answer()


@router.message(UserStatsState.waiting_for_telegram_id)
async def process_user_id_input(message: types.Message, state: FSMContext, db_session: AsyncSession):
    """
    Обрабатывает введённый Telegram ID и выводит статистику пользователя.
    Показывает количество попыток, успешных ответов и процент успеха по задачам.

    Args:
        message (types.Message): Сообщение с введённым Telegram ID.
        state (FSMContext): Контекст состояний для управления FSM.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy для работы с базой данных.
    """
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.reply("❌ Telegram ID должен быть числом. Попробуйте снова.")
        return

    query = select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
    user = (await db_session.execute(query)).scalar_one_or_none()

    if not user:
        await message.reply(f"❌ Пользователь с Telegram ID {telegram_id} не найден.")
        await state.clear()
        return

    await update_single_user_subscription_status(user, db_session)

    query_stats = select(TaskStatistics).where(TaskStatistics.user_id == user.id)
    stats_result = await db_session.execute(query_stats)
    stats = stats_result.scalars().all()

    if not stats:
        await message.reply(f"📄 У пользователя {telegram_id} нет статистики.")
        await state.clear()
        return

    total_attempts = sum(s.attempts for s in stats)
    total_successful = sum(1 for s in stats if s.successful)
    success_rate = (total_successful / total_attempts * 100) if total_attempts else 0

    response = (
        f"📊 *Статистика пользователя {escape_markdown(user.username or str(telegram_id))}:*\n\n"
        f"• *Всего попыток*: {escape_markdown(str(total_attempts))}\n"
        f"• *Успешных ответов*: {escape_markdown(str(total_successful))}\n"
        f"• *Процент успешных ответов*: {escape_markdown(f'{success_rate:.2f}%')}\n\n"
    )

    for stat in stats:
        task = stat.task
        if task:
            response += (
                f"• *Задача {escape_markdown(str(task.id))}*\n"
                f"  \\- *Попыток*: {escape_markdown(str(stat.attempts))}\n"
                f"  \\- *Успешных*: {'Да' if stat.successful else 'Нет'}\n\n"
            )

    await message.reply(response, parse_mode="MarkdownV2")
    await state.clear()


# ------------------------------------------------------------------------------
# CSV-обработчики
# ------------------------------------------------------------------------------

async def generate_and_send_csv_aggregated(
    chat_id: int,
    rows: list[tuple[int, str, datetime, str, str, str]],
    msg_or_call: types.Message | types.CallbackQuery,
    filename: str,
    caption: str
):
    """
    Генерирует и отправляет агрегированный CSV-файл с данными подписчиков.
    Поля: telegram_id, username, created_at, language, channel_names, subscribed_ats.

    Args:
        chat_id (int): ID чата для отправки файла.
        rows (list[tuple]): Список строк с данными (telegram_id, username, created_at, language, channel_names, subscribed_ats).
        msg_or_call (types.Message | types.CallbackQuery): Объект сообщения или callback для отправки ответа.
        filename (str): Имя CSV-файла.
        caption (str): Подпись к файлу.
    """
    if not rows:
        await msg_or_call.answer("Нет активных подписчиков.")
        return

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Заголовки
    writer.writerow([
        "telegram_id",
        "username",
        "created_at",
        "language",
        "channel_names",
        "subscribed_ats"
    ])

    for telegram_id, username, created_at, language, channel_names, subscribed_ats in rows:
        created_str = created_at.isoformat() if created_at else ""
        username_str = username or ""
        lang_str = language or ""
        channel_str = channel_names or ""
        subs_str = subscribed_ats or ""
        writer.writerow([
            telegram_id,
            username_str,
            created_str,
            lang_str,
            channel_str,
            subs_str
        ])

    csv_data = output.getvalue()
    output.close()
    csv_bytes = csv_data.encode("utf-8")

    await msg_or_call.answer_document(
        document=types.BufferedInputFile(file=csv_bytes, filename=filename),
        caption=caption
    )


@router.callback_query(F.data == "list_subscribers_all_csv")
async def list_subscribers_all_csv_callback(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Генерирует CSV-файл со списком всех активных подписчиков по всем каналам.

    Args:
        call (types.CallbackQuery): Callback-запрос от кнопки.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    admin_id = call.from_user.id
    if not await is_admin(admin_id, db_session):
        await call.message.reply("❌ Нет прав.")
        await call.answer()
        return

    try:
        from sqlalchemy.sql import text

        result = await db_session.execute(
            select(
                TelegramUser.telegram_id,
                TelegramUser.username,
                TelegramUser.created_at,
                TelegramUser.language,
                func.string_agg(TelegramGroup.group_name, ', ').label("channel_names"),
                func.string_agg(
                    func.to_char(
                        UserChannelSubscription.subscribed_at,
                        text("'YYYY-MM-DD\"T\"HH24:MI:SS'")
                    ),
                    ', '
                ).label("subscribed_ats")
            )
            .join(UserChannelSubscription, TelegramUser.id == UserChannelSubscription.telegram_user_id)
            .join(TelegramGroup, TelegramGroup.group_id == UserChannelSubscription.channel_id)
            .where(UserChannelSubscription.subscription_status == 'active')
            .group_by(TelegramUser.telegram_id, TelegramUser.username, TelegramUser.created_at, TelegramUser.language)
            .order_by(TelegramUser.username)
        )

        rows = result.all()
        await generate_and_send_csv_aggregated(
            chat_id=call.message.chat.id,
            rows=rows,
            msg_or_call=call.message,
            filename="all_subscribers.csv",
            caption="Список всех активных подписчиков по всем каналам (агрегирован)"
        )
    except Exception as e:
        logger.error(f"[list_subscribers_all_csv_callback] Ошибка: {e}")
        await call.message.reply("❌ Ошибка при генерации списка подписчиков.")
    finally:
        await call.answer()


@router.callback_query(F.data == "list_channels_groups_subscriptions")
async def callback_list_channels(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Показывает клавиатуру со списком каналов для выбора подписчиков.

    Args:
        call (types.CallbackQuery): Callback-запрос от кнопки.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    admin_id = call.from_user.id
    if not await is_admin(admin_id, db_session):
        await call.message.reply("❌ Нет прав.")
        await call.answer()
        return

    channels = (await db_session.execute(select(TelegramGroup))).scalars().all()
    if not channels:
        await call.message.reply("Каналов/групп нет в БД.")
        await call.answer()
        return

    kb = get_admin_channels_keyboard(channels)
    await call.message.answer("Выберите канал:", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("list_subscribers_csv:"))
async def list_subscribers_csv_for_channel(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Генерирует CSV-файл с активными подписчиками конкретного канала.

    Args:
        call (types.CallbackQuery): Callback-запрос с ID канала.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
    """
    admin_id = call.from_user.id
    if not await is_admin(admin_id, db_session):
        await call.message.reply("❌ Нет прав.")
        await call.answer()
        return

    try:
        _, channel_id_str = call.data.split(":", 1)
        channel_id = int(channel_id_str)
    except (ValueError, IndexError):
        await call.message.reply("❌ Некорректный формат данных.")
        await call.answer()
        return

    result = await db_session.execute(select(TelegramGroup).where(TelegramGroup.group_id == channel_id))
    group_obj = result.scalar_one_or_none()
    if not group_obj:
        await call.message.reply(f"❌ Канал (ID={channel_id}) не найден.")
        await call.answer()
        return

    result2 = await db_session.execute(
        select(UserChannelSubscription, TelegramUser, TelegramGroup)
        .join(TelegramUser, TelegramUser.id == UserChannelSubscription.telegram_user_id)
        .join(TelegramGroup, TelegramGroup.group_id == UserChannelSubscription.channel_id)
        .where(UserChannelSubscription.channel_id == channel_id)
        .where(UserChannelSubscription.subscription_status == 'active')
    )
    subscriptions = result2.all()
    await generate_and_send_csv(
        chat_id=call.message.chat.id,
        subscriptions=subscriptions,
        msg_or_call=call.message,
        filename=f"subscribers_{channel_id}.csv",
        caption=f"Активные подписчики канала {group_obj.group_name} (ID={channel_id})"
    )
    await call.answer()


async def generate_and_send_csv(
    chat_id: int,
    subscriptions: list[tuple[UserChannelSubscription, TelegramUser, TelegramGroup]],
    msg_or_call: types.Message | types.CallbackQuery,
    filename: str,
    caption: str
):
    """
    Генерирует и отправляет CSV-файл с данными подписчиков канала.

    Args:
        chat_id (int): ID чата для отправки.
        subscriptions (list[tuple]): Список подписок с объектами.
        msg_or_call (types.Message | types.CallbackQuery): Сообщение или callback.
        filename (str): Имя CSV-файла.
        caption (str): Подпись к файлу.
    """
    if not subscriptions:
        if isinstance(msg_or_call, types.Message):
            await msg_or_call.answer("Нет активных подписчиков.")
        else:
            await msg_or_call.answer("Нет активных подписчиков.")
        return

    output = io.StringIO()
    output.write("telegram_id,username,created_at,language,channel_id,channel_name,subscribed_at\n")
    for sub_obj, user_obj, group_obj in subscriptions:
        dt_sub = sub_obj.subscribed_at.isoformat() if sub_obj.subscribed_at else ""
        created_str = user_obj.created_at.isoformat() if user_obj.created_at else ""
        row = (
            f"{user_obj.telegram_id},"
            f"{user_obj.username or ''},"
            f"{created_str},"
            f"{user_obj.language or ''},"
            f"{group_obj.group_id},"
            f"{group_obj.group_name},"
            f"{dt_sub}\n"
        )
        output.write(row)

    output.seek(0)
    csv_bytes = output.getvalue().encode("utf-8")

    if isinstance(msg_or_call, types.Message):
        await msg_or_call.answer_document(
            document=types.BufferedInputFile(file=csv_bytes, filename=filename),
            caption=caption
        )
    else:
        await msg_or_call.answer_document(
            document=types.BufferedInputFile(file=csv_bytes, filename=filename),
            caption=caption
        )


