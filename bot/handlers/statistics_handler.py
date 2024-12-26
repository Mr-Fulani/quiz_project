"""
Обработчики команд и callback, связанные со статистикой (mystatistics, userstats, allstats).
Теперь все callback-хендлеры переключены на синтаксис F.data == ... для фильтрации callback_data.
"""
import io
import logging
from datetime import datetime, timezone, timedelta

from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram import F  # для F.data == ...
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.quiz_keyboards import get_admin_channels_keyboard
from bot.services.admin_service import is_admin
from bot.states.admin_states import UserStatsState
from bot.utils.db_utils import fetch_one
from bot.utils.markdownV2 import escape_markdown
from database.models import User, Task, TaskStatistics, TaskPoll, Admin, UserChannelSubscription, Group



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


@router.message(Command(commands=["userstats"]))
async def user_statistics(message: types.Message, db_session: AsyncSession):
    """
    Команда /userstats <telegram_id> — вывод статистики конкретного пользователя (по ID),
    доступно только администратору.

    Пример:
      /userstats 123456789

    :param message: Объект сообщения с командой.
    :param db_session: Асинхронная сессия к базе данных.
    """
    admin_id = message.from_user.id
    logger.info(f"[user_statistics] Админ {admin_id} запросил статистику конкретного пользователя.")

    if not await is_admin(admin_id, db_session):
        await message.answer("⚠️ У вас нет прав для выполнения этой команды.")
        logger.warning(f"[user_statistics] Пользователь {admin_id} не админ, отказано.")
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("ℹ️ Использование: /userstats <telegram_id>")
        return

    # Парсим целочисленный ID
    try:
        target_telegram_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом.")
        return

    # Ищем пользователя
    query = select(User).where(User.telegram_id == target_telegram_id)
    user = await fetch_one(db_session, query)

    if not user:
        await message.answer(f"❌ Пользователь с ID `{target_telegram_id}` не найден.")
        return

    # Получаем статистику
    query_stats = select(TaskStatistics).where(TaskStatistics.user_id == user.id)
    stats_result = await db_session.execute(query_stats)
    stats = stats_result.scalars().all()

    if not stats:
        await message.answer(f"📄 У пользователя `{target_telegram_id}` пока нет статистики.")
        return

    total_attempts = sum(s.attempts for s in stats)
    total_successful = sum(1 for s in stats if s.successful)
    success_rate = (total_successful / total_attempts) * 100 if total_attempts else 0

    response = (
        f"📊 **Статистика пользователя {user.username or target_telegram_id}:**\n\n"
        f"• **Всего попыток**: {total_attempts}\n"
        f"• **Успешных ответов**: {total_successful}\n"
        f"• **Процент успеха**: {success_rate:.2f}%\n\n"
        f"**Детали:**\n"
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
    logger.info(f"[user_statistics] Статистика пользователя {target_telegram_id} отправлена админу {admin_id}.")


@router.message(Command(commands=["allstats"]))
async def all_statistics(message: types.Message, db_session: AsyncSession):
    """
    Команда /allstats — общая статистика по всем пользователям, только для админа.

    :param message: Объект сообщения с командой.
    :param db_session: Асинхронная сессия к базе данных.
    """
    admin_id = message.from_user.id
    logger.info(f"[all_statistics] Админ {admin_id} запросил общую статистику.")

    if not await is_admin(admin_id, db_session):
        await message.answer("⚠️ У вас нет прав для выполнения этой команды.")
        logger.warning(f"[all_statistics] Пользователь {admin_id} не админ, отказано.")
        return

    try:
        # Общая статистика
        total_users_query = select(func.count(User.id))
        total_users = (await db_session.execute(total_users_query)).scalar() or 0

        total_tasks_query = select(func.count(Task.id))
        total_tasks = (await db_session.execute(total_tasks_query)).scalar() or 0

        total_attempts_query = select(func.sum(TaskStatistics.attempts))
        total_attempts = (await db_session.execute(total_attempts_query)).scalar() or 0

        total_successful_query = select(func.sum(case(
            (TaskStatistics.successful == True, 1),
            else_=0)))
        total_successful = (await db_session.execute(total_successful_query)).scalar() or 0

        response = (
            f"📊 **Общая статистика**:\n\n"
            f"• **Всего пользователей**: {total_users}\n"
            f"• **Всего задач**: {total_tasks}\n"
            f"• **Всего попыток**: {total_attempts}\n"
            f"• **Успешных ответов**: {total_successful}\n"
        )
        await message.answer(response, parse_mode="MarkdownV2")

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
        #    Нужно поле created_at для этого
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        subscribed_30d_query = select(func.count(User.id)).where(
            and_(
                User.subscription_status == 'active',
                User.created_at >= thirty_days_ago
            )
        )
        subscribed_30d = (await db_session.execute(subscribed_30d_query)).scalar() or 0

        # 5) Сколько отписались за последние 30 дней (если есть поле deactivated_at)
        #    Если поле deactivated_at не используется, уберите этот блок
        unsubscribed_30d_query = select(func.count(User.id)).where(
            and_(
                User.subscription_status == 'inactive',
                # Предполагаем, что deactivated_at заполняется, когда становится inactive
                User.deactivated_at >= thirty_days_ago
            )
        )
        unsubscribed_30d = (await db_session.execute(unsubscribed_30d_query)).scalar() or 0

        # 6) Активность в боте (примерно — доля пользователей, у которых есть хотя бы 1 запись в статистике task_statistics)
        #    Это условная метрика, зависящая от вашей логики.
        #    Здесь просто пример, пусть под "активностью в боте" считаем процент пользователей,
        #    которые совершали действия (есть записи в TaskStatistics).
        #    TaskStatistics связывает user_id с задачами.
        #    Для упрощения примем, что "активность" = (число пользователей, у которых есть хотя бы 1 запись) / (total_users)
        from database.models import TaskStatistics
        active_in_bot_query = select(func.count(func.distinct(TaskStatistics.user_id)))
        active_in_bot_count = (await db_session.execute(active_in_bot_query)).scalar() or 0
        bot_activity_pct = 0.0
        if total_users > 0:
            bot_activity_pct = active_in_bot_count / total_users * 100

        # 7) «Активность в каналах»
        #    Зависит от логики, где вы храните info о том, кто как взаимодействует с каналами.
        #    Если Group / location_type="channel" и есть tasks,
        #    вы можете считать, сколько пользователей участвует в опросах канала, или что-то подобное.
        #    В качестве примера:
        from database.models import Group, Task
        # Предположим, «активность в канале» = доля пользователей, участвовавших в опросах, опубликованных в каких-то каналах
        # Реализовать точный расчёт — в зависимости от вашей схемы.
        # Пока сделаем фейковый расчёт:
        # (число пользователей, у которых есть записи в TaskStatistics для задач, у которых group.location_type=="channel") / total_users
        # Это только пример. Нужно смотреть ваши таблицы.

        # Сначала найдём все task_id, относящиеся к каналам
        subq_channel_tasks = select(Task.id).join(Group, Task.group).where(Group.location_type == "channel")
        # Считаем, сколько уникальных user_id есть в TaskStatistics по этим task_id
        channel_activity_query = (
            select(func.count(func.distinct(TaskStatistics.user_id)))
            .where(TaskStatistics.task_id.in_(subq_channel_tasks))
        )
        channel_activity_count = (await db_session.execute(channel_activity_query)).scalar() or 0

        channel_activity_pct = 0.0
        if total_users > 0:
            channel_activity_pct = channel_activity_count / total_users * 100

        # Формируем ответ (внимательно экранируем для MarkdownV2, чтобы не вылетал Bad Request)
        # В MarkdownV2 нужно экранировать символы . ( ) ! - и т. п. через backslash
        # Или использовать функцию escape_markdown
        response = (
            f"📊 *Общая статистика*:\n\n"
            f"• *Всего пользователей*: {escape_markdown(str(total_users))}\n"
            f"• *Активных*: {escape_markdown(str(active_users))}\n"
            f"• *Неактивных*: {escape_markdown(str(inactive_users))}\n\n"
            f"• *Подписались за 30 дней*: {escape_markdown(str(subscribed_30d))}\n"
            f"• *Отписались за 30 дней*: {escape_markdown(str(unsubscribed_30d))}\n\n"
            f"• *Активность в боте*: {escape_markdown(f'{bot_activity_pct:.2f}%')}\n"
            f"• *Активность в каналах*: {escape_markdown(f'{channel_activity_pct:.2f}%')}\n"
        )

        await call.message.reply(response, parse_mode="MarkdownV2")
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
    if not await is_admin(admin_id, db_session):  # Используем db_session напрямую
        await call.message.reply("⚠️ У вас нет прав для выполнения этой команды.")
        await call.answer()
        return

    await call.message.answer("Введите Telegram ID пользователя для просмотра статистики.")
    await state.set_state(UserStatsState.waiting_for_telegram_id)
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
        await message.reply(f"❌ Пользователь с Telegram ID `{telegram_id}` не найден.")
        await state.clear()
        return

    # Получаем статистику пользователя
    query_stats = select(TaskStatistics).where(TaskStatistics.user_id == user.id)
    stats_result = await db_session.execute(query_stats)
    stats = stats_result.scalars().all()

    if not stats:
        await message.reply(f"📄 У пользователя `{telegram_id}` нет статистики.")
        await state.clear()
        return

    # Считаем общие метрики
    total_attempts = sum(s.attempts for s in stats)
    total_successful = sum(1 for s in stats if s.successful)
    success_rate = (total_successful / total_attempts) * 100 if total_attempts else 0

    # Формируем сообщение
    response = (
        f"📊 **Статистика пользователя {escape_markdown(user.username or str(telegram_id))}:**\n\n"
        f"• **Всего попыток**: {escape_markdown(str(total_attempts))}\n"
        f"• **Успешных ответов**: {escape_markdown(str(total_successful))}\n"
        f"• **Процент успешных ответов**: {escape_markdown(f'{success_rate:.2f}%')}\n\n"
    )

    for stat in stats:
        task = stat.task
        if task:
            response += (
                f"• **Задача {escape_markdown(str(task.id))}**\n"
                f"  - **Попыток**: {escape_markdown(str(stat.attempts))}\n"
                f"  - **Успешных**: {'Да' if stat.successful else 'Нет'}\n\n"
            )

    await message.reply(response, parse_mode="MarkdownV2")
    await state.clear()









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






# Обработчик кнопки "Список подписчиков (CSV)"
@router.callback_query(F.data == "list_subscribers_all_csv")
async def list_subscribers_all_csv_callback(call: types.CallbackQuery, db_session: AsyncSession):
    """
    Кнопка «Список всех подписчиков (CSV)»
    """
    admin_id = call.from_user.id
    if not await is_admin(admin_id, db_session):
        await call.message.reply("❌ Нет прав.")
        await call.answer()
        return

    # Собираем все active-подписки
    result = await db_session.execute(
        select(UserChannelSubscription, User, Group)
        .join(User, User.id == UserChannelSubscription.user_id)
        .join(Group, Group.group_id == UserChannelSubscription.channel_id)
        .where(UserChannelSubscription.subscription_status == 'active')
    )
    subscriptions = result.all()  # Список кортежей

    await generate_and_send_csv(
        chat_id=call.message.chat.id,
        subscriptions=subscriptions,
        msg_or_call=call.message,
        filename="all_subscribers.csv",
        caption="Список всех активных подписчиков по всем каналам"
    )
    await call.answer()




@router.callback_query(F.data == "list_channels_groups_subscriptions")
async def callback_list_channels(call: types.CallbackQuery, db_session: AsyncSession):
    # допустим, получаем все каналы:
    channels = (await db_session.execute(select(Group))).scalars().all()
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








# # Обработчик команды /list_subscribers_channel <channel_id>
# @router.message(Command("list_subscribers_channel"))
# async def list_subscribers_channel_cmd(message: types.Message, db_session: AsyncSession):
#     """
#     Команда вида:
#     /list_subscribers_channel <channel_id>
#     Выдаёт CSV-файл со списком активных подписчиков для данного channel_id.
#     """
#     args = message.text.strip().split()
#     if len(args) < 2:
#         await message.reply("⚠️ Использование: /list_subscribers_channel <channel_id>")
#         return
#
#     try:
#         channel_id = int(args[1])
#     except ValueError:
#         await message.reply("⚠️ channel_id должен быть числом.")
#         return
#
#     # Проверяем, существует ли канал в базе
#     result = await db_session.execute(
#         select(Group).where(Group.group_id == channel_id)
#     )
#     group_obj = result.scalar_one_or_none()
#     if not group_obj:
#         await message.reply(f"❌ Канал (ID: {channel_id}) не найден в базе.")
#         return
#
#     # Находим все активные подписки к этому каналу
#     result = await db_session.execute(
#         select(UserChannelSubscription, User, Group)
#         .join(User, User.id == UserChannelSubscription.user_id)
#         .join(Group, Group.group_id == UserChannelSubscription.channel_id)
#         .where(UserChannelSubscription.channel_id == channel_id)
#         .where(UserChannelSubscription.subscription_status == "active")
#     )
#     subscriptions = result.all()
#
#     if not subscriptions:
#         await message.reply(f"📭 На канал '{group_obj.group_name}' нет активных подписчиков.")
#         return
#
#     # Используем общую функцию для генерации и отправки CSV
#     await generate_and_send_csv(
#         chat_id=message.chat.id,
#         subscriptions=subscriptions,
#         message_or_bot=message,
#         filename=f"subscribers_{channel_id}.csv",
#         caption=f"Список подписчиков канала {group_obj.group_name} (ID: {channel_id})."
#     )






