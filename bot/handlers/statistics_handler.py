"""
Обработчики команд и callback, связанные со статистикой (mystatistics, userstats, allstats).
Теперь все callback-хендлеры переключены на синтаксис F.data == ... для фильтрации callback_data.
"""
import csv
import io
import logging
import datetime
from datetime import datetime, timedelta
from operator import or_

from aiogram import F  # для F.data == ...
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.quiz_keyboards import get_admin_channels_keyboard
from bot.services.admin_service import is_admin
from bot.states.admin_states import UserStatsState
from bot.utils.markdownV2 import escape_markdown
from database.models import User, TaskStatistics, UserChannelSubscription, Group

logger = logging.getLogger(__name__)
router = Router(name="statistics_router")




# ------------------------------------------------------------------------------
# ------------------------------ Команды / ... ---------------------------------
# ------------------------------------------------------------------------------



@router.message(Command(commands=["mystatistics"]))
async def my_statistics(message: types.Message, db_session: AsyncSession):
    """
    Команда /mystatistics — выводит статистику текущего пользователя (если он не бот).

    :param message: Объект сообщения.
    :param db_session: Асинхронная сессия к базе данных.
    """
    telegram_id = message.from_user.id
    logger.info(f"[my_statistics] Запрос статистики от пользователя {telegram_id}")

    # Ищем пользователя в БД
    query = select(User).where(User.telegram_id == telegram_id)
    result = await db_session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"[my_statistics] Пользователь {telegram_id} не найден в базе данных.")
        await message.reply("❌ Вы не зарегистрированы в системе.")
        return

    # Получаем статистику
    query_stats = select(TaskStatistics).where(TaskStatistics.user_id == user.id)
    stats_result = await db_session.execute(query_stats)
    stats = stats_result.scalars().all()

    if not stats:
        await message.answer("📄 У вас пока нет статистики по задачам.")
        logger.info(f"[my_statistics] У пользователя {telegram_id} нет статистики.")
        return

    # Подсчитываем общие метрики
    total_attempts = sum(stat.attempts for stat in stats)
    total_successful = sum(1 for stat in stats if stat.successful)
    success_rate = (total_successful / total_attempts) * 100 if total_attempts else 0

    # Формируем ответ
    response = (
        f"📊 **Ваша статистика по задачам:**\n\n"
        f"• **Всего попыток**: {total_attempts}\n"
        f"• **Успешных ответов**: {total_successful}\n"
        f"• **Процент успешных ответов**: {success_rate:.2f}%\n\n"
        f"**Детальная статистика по задачам:**\n"
    )

    for stat in stats:
        task = stat.task
        if not task:
            continue
        publish_date = (
            task.publish_date.strftime('%Y-%m-%d %H:%M:%S')
            if task.publish_date
            else "Не опубликована"
        )
        last_attempt = (
            stat.last_attempt_date.strftime('%Y-%m-%d %H:%M:%S')
            if stat.last_attempt_date
            else "Нет попыток"
        )
        topic_name = task.topic.name if task.topic else "Без темы"

        response += (
            f"• **Задача {task.id}**\n"
            f"  - **Тема**: {escape_markdown(topic_name)}\n"
            f"  - **Попыток**: {stat.attempts}\n"
            f"  - **Успешных**: {'Да' if stat.successful else 'Нет'}\n"
            f"  - **Последняя попытка**: {last_attempt}\n"
            f"  - **Дата публикации**: {publish_date}\n\n"
        )

    await message.answer(response, parse_mode="MarkdownV2")
    logger.info(f"[my_statistics] Статистика для пользователя {telegram_id} успешно отправлена.")






@router.message(Command(commands=["allstats"]))
async def all_statistics(message: types.Message, db_session: AsyncSession):
    """
    Команда /allstats — общая статистика по всем пользователям, только для админа.
    """
    admin_id = message.from_user.id
    logger.info(f"[all_statistics] Админ {admin_id} запросил общую статистику.")

    if not await is_admin(admin_id, db_session):
        await message.answer("⚠️ У вас нет прав для выполнения этой команды.")
        logger.warning(f"[all_statistics] Пользователь {admin_id} не админ, отказано.")
        return

    try:
        # 1) Всего пользователей
        total_users_query = select(func.count(User.id))
        total_users = (await db_session.execute(total_users_query)).scalar() or 0

        # 2) Активных пользователей (subscription_status='active')
        active_users_query = select(func.count(User.id)).where(User.subscription_status == 'active')
        active_users = (await db_session.execute(active_users_query)).scalar() or 0

        # 3) Неактивных пользователей
        inactive_users_query = select(func.count(User.id)).where(User.subscription_status == 'inactive')
        inactive_users = (await db_session.execute(inactive_users_query)).scalar() or 0

        # 4) Сколько подписались за последние 30 дней
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        subscribed_30d_query = select(func.count(User.id)).where(
            and_(
                User.subscription_status == 'active',
                User.created_at >= thirty_days_ago
            )
        )
        subscribed_30d = (await db_session.execute(subscribed_30d_query)).scalar() or 0

        # 5) Сколько отписались за последние 30 дней
        unsubscribed_30d_query = select(func.count(User.id)).where(
            and_(
                User.subscription_status == 'inactive',
                User.deactivated_at >= thirty_days_ago
            )
        )
        unsubscribed_30d = (await db_session.execute(unsubscribed_30d_query)).scalar() or 0

        # 6) Активность в боте
        active_in_bot_query = select(func.count(func.distinct(TaskStatistics.user_id)))
        active_in_bot_count = (await db_session.execute(active_in_bot_query)).scalar() or 0
        bot_activity_pct = 0.0
        if total_users > 0:
            bot_activity_pct = active_in_bot_count / total_users * 100

        # 7) Активность в каналах и группах (супергруппах)
        channel_activity_query = select(
            Group.group_name,
            Group.username,  # Добавляем username
            func.count(
                case(
                    (UserChannelSubscription.subscription_status == 'active', 1)
                )
            ).label('gained'),
            func.count(
                case(
                    (UserChannelSubscription.subscription_status == 'inactive', 1)
                )
            ).label('lost')
        ).join(
            UserChannelSubscription, UserChannelSubscription.channel_id == Group.group_id
        ).where(
            or_(
                and_(
                    UserChannelSubscription.subscription_status == 'active',
                    UserChannelSubscription.subscribed_at >= thirty_days_ago
                ),
                and_(
                    UserChannelSubscription.subscription_status == 'inactive',
                    UserChannelSubscription.unsubscribed_at >= thirty_days_ago
                )
            )
        ).group_by(Group.group_name, Group.username)

        channel_activity_result = await db_session.execute(channel_activity_query)
        channel_activity = channel_activity_result.all()  # Список кортежей: (group_name, username, gained, lost)

        # Вычисляем общий прирост и убыль
        total_gained = sum(gained for _, _, gained, _ in channel_activity)
        total_lost = sum(lost for _, _, _, lost in channel_activity)

        if total_gained + total_lost > 0:
            overall_channel_activity = f"• *Активность в каналах и группах*: \\+{total_gained} подписок / \\-{total_lost} отписок"
        else:
            overall_channel_activity = "• *Активность в каналах и группах*: Нет изменений за последние 30 дней"

        # Детальная активность по каналам и группам
        if channel_activity:
            channel_details = "\n• *Детальная активность по каналам и группам*:\n"
            for group_name, group_username, gained, lost in channel_activity:
                if group_username:
                    # Формируем ссылку на канал или группу
                    channel_link = f"[{escape_markdown(group_name)}](https://t.me/{group_username})"
                else:
                    # Если username нет, выводим просто название
                    channel_link = f"{escape_markdown(group_name)}"
                # Экранируем '+' и '-' в статических частях
                channel_details += f"  \\- {channel_link}: \\+{gained} / \\-{lost}\n"
        else:
            channel_details = "\n• *Детальная активность по каналам и группам*: Нет данных за последние 30 дней"

        # Формируем ответ
        response = (
            f"📊 *Общая статистика*:\n\n"
            f"• *Всего пользователей*: {escape_markdown(str(total_users))}\n"
            f"• *Активных*: {escape_markdown(str(active_users))}\n"
            f"• *Неактивных*: {escape_markdown(str(inactive_users))}\n\n"
            f"• *Подписались за 30 дней*: {escape_markdown(str(subscribed_30d))}\n"
            f"• *Отписались за 30 дней*: {escape_markdown(str(unsubscribed_30d))}\n\n"
            f"• *Активность в боте*: {escape_markdown(f'{bot_activity_pct:.2f}%')}\n"
            f"{overall_channel_activity}\n"
            f"{channel_details}"
        )

        await message.answer(response, parse_mode="MarkdownV2", disable_web_page_preview=True)
        logger.info(f"[all_statistics] Общая статистика отправлена админу {admin_id}.")
    except Exception as e:
        logger.error(f"[all_statistics] Ошибка: {e}")
        await message.answer("❌ Ошибка при получении общей статистики.")





# ------------------------------------------------------------------------------
# ------------------------------ Callback Queries -------------------------------
# ------------------------------------------------------------------------------



@router.callback_query(F.data == "mystatistics")
async def callback_mystatistics(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Инлайн-кнопка "Моя статистика" (callback_data="mystatistics").
    Вызывает ту же логику, что и команда /mystatistics, но по нажатию кнопки.

    :param call: Объект CallbackQuery.
    :param db_session: Асинхронная сессия к базе данных.
    """
    # Имитируем вызов my_statistics, но у нас в коллбэке нет message.text
    # Поэтому возьмём from_user.id, и выполним ту же логику.
    user_id = call.from_user.id
    logger.info(f"[callback_mystatistics] Нажата кнопка 'Моя статистика' пользователем {user_id}")

    # Ищем пользователя
    query = select(User).where(User.telegram_id == user_id)
    result = await db_session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"[callback_mystatistics] Пользователь {user_id} не найден в БД.")
        await call.message.answer("❌ Вы не зарегистрированы в системе.")
        await call.answer()
        return

    # Получаем статистику
    query_stats = select(TaskStatistics).where(TaskStatistics.user_id == user.id)
    stats_result = await db_session.execute(query_stats)
    stats = stats_result.scalars().all()

    if not stats:
        await call.message.answer("📄 У вас пока нет статистики по задачам.")
        logger.info(f"[callback_mystatistics] У пользователя {user_id} нет статистики.")
        await call.answer()
        return

    total_attempts = sum(stat.attempts for stat in stats)
    total_successful = sum(1 for stat in stats if stat.successful)
    success_rate = (total_successful / total_attempts) * 100 if total_attempts else 0

    response = (
        f"📊 **Ваша статистика по задачам (кнопка):**\n\n"
        f"• **Всего попыток**: {total_attempts}\n"
        f"• **Успешных ответов**: {total_successful}\n"
        f"• **Процент успешных ответов**: {success_rate:.2f}%\n\n"
        f"**Детальная статистика по задачам:**\n"
    )

    for stat in stats:
        task = stat.task
        if not task:
            continue
        publish_date = task.publish_date.strftime('%Y-%m-%d %H:%M:%S') if task.publish_date else "Не опубликована"
        last_attempt = stat.last_attempt_date.strftime('%Y-%m-%d %H:%M:%S') if stat.last_attempt_date else "Нет попыток"
        topic_name = task.topic.name if task.topic else "Без темы"

        response += (
            f"• **Задача {task.id}**\n"
            f"  - **Тема**: {escape_markdown(topic_name)}\n"
            f"  - **Попыток**: {stat.attempts}\n"
            f"  - **Успешных**: {'Да' if stat.successful else 'Нет'}\n"
            f"  - **Последняя попытка**: {last_attempt}\n"
            f"  - **Дата публикации**: {publish_date}\n\n"
        )

    await call.message.answer(response, parse_mode="MarkdownV2")
    logger.info(f"[callback_mystatistics] Статистика для пользователя {user_id} отправлена.")
    await call.answer()





@router.callback_query(F.data == "allstats")
async def callback_allstats(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Обработчик коллбэка «Общая статистика».
    """
    admin_id = call.from_user.id
    logger.info(f"Пользователь {admin_id} запросил общую статистику (allstats).")

    # Проверяем права
    if not await is_admin(admin_id, db_session):
        await call.message.reply("⚠️ У вас нет прав для выполнения этой команды.")
        await call.answer()
        return

    try:
        # 1) Всего пользователей
        total_users_query = select(func.count(User.id))
        total_users = (await db_session.execute(total_users_query)).scalar() or 0

        # 2) Активных пользователей (subscription_status='active')
        active_users_query = select(func.count(User.id)).where(User.subscription_status == 'active')
        active_users = (await db_session.execute(active_users_query)).scalar() or 0

        # 3) Неактивных пользователей
        inactive_users_query = select(func.count(User.id)).where(User.subscription_status == 'inactive')
        inactive_users = (await db_session.execute(inactive_users_query)).scalar() or 0

        # 4) Сколько подписались за последние 30 дней
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        subscribed_30d_query = select(func.count(User.id)).where(
            and_(
                User.subscription_status == 'active',
                User.created_at >= thirty_days_ago
            )
        )
        subscribed_30d = (await db_session.execute(subscribed_30d_query)).scalar() or 0

        # 5) Сколько отписались за последние 30 дней
        unsubscribed_30d_query = select(func.count(User.id)).where(
            and_(
                User.subscription_status == 'inactive',
                User.deactivated_at >= thirty_days_ago
            )
        )
        unsubscribed_30d = (await db_session.execute(unsubscribed_30d_query)).scalar() or 0

        # 6) Активность в боте
        active_in_bot_query = select(func.count(func.distinct(TaskStatistics.user_id)))
        active_in_bot_count = (await db_session.execute(active_in_bot_query)).scalar() or 0
        bot_activity_pct = 0.0
        if total_users > 0:
            bot_activity_pct = active_in_bot_count / total_users * 100

        # 7) Активность в каналах и группах (супергруппах)
        channel_activity_query = select(
            Group.group_name,
            Group.username,  # Добавляем username
            func.count(
                case(
                    (UserChannelSubscription.subscription_status == 'active', 1)
                )
            ).label('gained'),
            func.count(
                case(
                    (UserChannelSubscription.subscription_status == 'inactive', 1)
                )
            ).label('lost')
        ).join(
            UserChannelSubscription, UserChannelSubscription.channel_id == Group.group_id
        ).where(
            or_(
                and_(
                    UserChannelSubscription.subscription_status == 'active',
                    UserChannelSubscription.subscribed_at >= thirty_days_ago
                ),
                and_(
                    UserChannelSubscription.subscription_status == 'inactive',
                    UserChannelSubscription.unsubscribed_at >= thirty_days_ago
                )
            )
        ).group_by(Group.group_name, Group.username)

        channel_activity_result = await db_session.execute(channel_activity_query)
        channel_activity = channel_activity_result.all()  # Список кортежей: (group_name, username, gained, lost)

        # Вычисляем общий прирост и убыль
        total_gained = sum(gained for _, _, gained, _ in channel_activity)
        total_lost = sum(lost for _, _, _, lost in channel_activity)

        if total_gained + total_lost > 0:
            overall_channel_activity = f"• *Активность в каналах и группах*: \\+{total_gained} подписок / \\-{total_lost} отписок"
        else:
            overall_channel_activity = "• *Активность в каналах и группах*: Нет изменений за последние 30 дней"

        # Детальная активность по каналам и группам
        if channel_activity:
            channel_details = "\n• *Детальная активность по каналам и группам*:\n"
            for group_name, group_username, gained, lost in channel_activity:
                if group_username:
                    # Формируем ссылку на канал или группу
                    channel_link = f"[{escape_markdown(group_name)}](https://t.me/{group_username})"
                else:
                    # Если username нет, выводим просто название
                    channel_link = f"{escape_markdown(group_name)}"
                # Экранируем '+' и '-' в статических частях
                channel_details += f"  \\- {channel_link}: \\+{gained} / \\-{lost}\n"
        else:
            channel_details = "\n• *Детальная активность по каналам и группам*: Нет данных за последние 30 дней"

        # Формируем ответ
        response = (
            f"📊 *Общая статистика*:\n\n"
            f"• *Всего пользователей*: {escape_markdown(str(total_users))}\n"
            f"• *Активных*: {escape_markdown(str(active_users))}\n"
            f"• *Неактивных*: {escape_markdown(str(inactive_users))}\n\n"
            f"• *Подписались за 30 дней*: {escape_markdown(str(subscribed_30d))}\n"
            f"• *Отписались за 30 дней*: {escape_markdown(str(unsubscribed_30d))}\n\n"
            f"• *Активность в боте*: {escape_markdown(f'{bot_activity_pct:.2f}%')}\n"
            f"{overall_channel_activity}\n"
            f"{channel_details}"
        )

        await call.message.reply(response, parse_mode="MarkdownV2", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"[callback_allstats] Ошибка: {e}")
        await call.message.reply("❌ Ошибка при получении общей статистики.")
    finally:
        await call.answer()







@router.callback_query(F.data == "userstats")
async def start_userstats_callback(call: types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    """
    Начало процесса ввода Telegram ID для просмотра статистики пользователя.
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
    Обработка введенного Telegram ID и вывод статистики пользователя.
    """
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.reply("❌ Telegram ID должен быть числом. Попробуйте снова.")
        return

    # Проверяем, существует ли пользователь
    query = select(User).where(User.telegram_id == telegram_id)
    user = (await db_session.execute(query)).scalar_one_or_none()

    if not user:
        await message.reply(f"❌ Пользователь с Telegram ID {telegram_id} не найден.")
        await state.clear()
        return

    # Получаем статистику пользователя
    query_stats = select(TaskStatistics).where(TaskStatistics.user_id == user.id)
    stats_result = await db_session.execute(query_stats)
    stats = stats_result.scalars().all()

    if not stats:
        await message.reply(f"📄 У пользователя {telegram_id} нет статистики.")
        await state.clear()
        return

    # Считаем общие метрики
    total_attempts = sum(s.attempts for s in stats)
    total_successful = sum(1 for s in stats if s.successful)
    success_rate = (total_successful / total_attempts) * 100 if total_attempts else 0

    # Формируем сообщение с правильным экранированием для MarkdownV2
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












async def generate_and_send_csv_aggregated(
    chat_id: int,
    rows: list[tuple[int, str, datetime, str, str, str]],
    msg_or_call: types.Message | types.CallbackQuery,
    filename: str,
    caption: str
):
    """
    Генерация и отправка АГРЕГИРОВАННОГО CSV с полями:
      telegram_id, username, created_at, language, channel_names, subscribed_ats
    rows = [
      (telegram_id, username, created_at, language, channel_names, subscribed_ats)
    ]
    где channel_names и subscribed_ats - это string_agg(...)
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
        subs_str = subscribed_ats or ""  # может быть "2024-12-01T12:00:00, 2024-12-02T08:30:00"

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

    # Отправляем
    await msg_or_call.answer_document(
        document=types.BufferedInputFile(file=csv_bytes, filename=filename),
        caption=caption
    )


@router.callback_query(F.data == "list_subscribers_all_csv")
async def list_subscribers_all_csv_callback(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Кнопка «Список ВСЕХ подписчиков (CSV)» (агрегированный).
    """
    admin_id = call.from_user.id
    if not await is_admin(admin_id, db_session):
        await call.message.reply("❌ Нет прав.")
        await call.answer()
        return

    try:
        # Агрегированный запрос
        #  - string_agg(...) по group_name
        #  - string_agg(...) по subscribed_at (кастуем к тексту, форматируем)
        # Поля: telegram_id, username, created_at, language
        # group_by: telegram_id, username, created_at, language
        # Пример форматирования subscribed_at:
        #   to_char(user_channel_subscriptions.subscribed_at, 'YYYY-MM-DD"T"HH24:MI:SS')
        # или любой другой формат
        from sqlalchemy.sql import text

        result = await db_session.execute(
            select(
                User.telegram_id,
                User.username,
                User.created_at,
                User.language,
                func.string_agg(Group.group_name, ', ').label("channel_names"),
                func.string_agg(
                    func.to_char(
                        UserChannelSubscription.subscribed_at,
                        text("'YYYY-MM-DD\"T\"HH24:MI:SS'")
                    ),
                    ', '
                ).label("subscribed_ats")
            )
            .join(UserChannelSubscription, User.id == UserChannelSubscription.user_id)
            .join(Group, Group.group_id == UserChannelSubscription.channel_id)
            .where(UserChannelSubscription.subscription_status == 'active')
            .group_by(User.telegram_id, User.username, User.created_at, User.language)
            .order_by(User.username)
        )

        rows = result.all()  # [(tg_id, username, created_at, language, channel_names, subscribed_ats), ...]

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
    Показываем инлайн-клавиатуру с каждым каналом, чтобы потом можно было нажать
    и получить детальный список подписчиков канала (CSV).
    """
    admin_id = call.from_user.id
    if not await is_admin(admin_id, db_session):
        await call.message.reply("❌ Нет прав.")
        await call.answer()
        return

    # Получаем список каналов (Group.location_type="channel", если нужно)
    channels = (
        await db_session.execute(
            select(Group)
            # .where(Group.location_type == 'channel')  # Если нужно только каналы
        )
    ).scalars().all()

    if not channels:
        await call.message.reply("Каналов/групп нет в БД.")
        await call.answer()
        return

    kb = get_admin_channels_keyboard(channels)
    await call.message.answer("Выберите канал:", reply_markup=kb)
    await call.answer()




# Дополнительно: Модификация обработчика для кнопок с channel_id
@router.callback_query(F.data.startswith("list_subscribers_csv:"))
async def list_subscribers_csv_for_channel(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Кнопка «Список подписчиков канала {channel_name}»
    callback_data="list_subscribers_csv:{channel_id}"
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

    # Ищем канал
    result = await db_session.execute(select(Group).where(Group.group_id == channel_id))
    group_obj = result.scalar_one_or_none()
    if not group_obj:
        await call.message.reply(f"❌ Канал (ID={channel_id}) не найден.")
        await call.answer()
        return

    # Ищем подписчиков
    result2 = await db_session.execute(
        select(UserChannelSubscription, User, Group)
        .join(User, User.id == UserChannelSubscription.user_id)
        .join(Group, Group.group_id == UserChannelSubscription.channel_id)
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





# Общая функция для генерации и отправки CSV
async def generate_and_send_csv(
    chat_id: int,
    subscriptions: list[tuple[UserChannelSubscription, User, Group]],
    msg_or_call: types.Message | types.CallbackQuery,
    filename: str,
    caption: str
):
    """
    Генерация и отправка CSV с полями:
    telegram_id,username,created_at,language,channel_id,channel_name,subscribed_at
    """
    if not subscriptions:
        # Нет ни одной записи
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

    # Отправляем
    if isinstance(msg_or_call, types.Message):
        await msg_or_call.answer_document(
            document=types.BufferedInputFile(file=csv_bytes, filename=filename),
            caption=caption
        )
    else:
        # call.message.answer_document(...)
        await msg_or_call.answer_document(
            document=types.BufferedInputFile(file=csv_bytes, filename=filename),
            caption=caption
        )

