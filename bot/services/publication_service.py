# bot/services/publication_service.py

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Tuple, List
from uuid import UUID

import pytz
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.database.models import Task, TelegramGroup, TaskTranslation, TaskPoll, Topic
from bot.services.default_link_service import DefaultLinkService
from bot.services.task_service import prepare_publication
from bot.services.webhook_service import WebhookService
from bot.utils.logging_utils import log_final_summary, log_pause, \
    log_username_received, log_publication_start, log_publication_failure, log_webhook_data, log_publication_success
from bot.utils.webhook_utils import create_bulk_webhook_data, create_full_webhook_data_for_task




logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def get_group_by_topic_and_language(db_session, topic_id: int, language: str):
    """
    Получает группу по топику и языку.
    """
    result = await db_session.execute(
        select(TelegramGroup).where(
            TelegramGroup.topic_id == topic_id,
            TelegramGroup.language == language
        )
    )
    return result.scalar_one_or_none()


async def send_task_post(bot: Bot, group, task, text_message: dict, poll_message: dict):
    """
    Отправляет пост задачи: вопрос (код или текст, с кнопкой «Узнать подробнее») и опрос.
    Сохраняет в задаче ID всех сообщений поста — по ним пост удаляется. Возвращает сообщение опроса.
    """
    text_msg = await bot.send_message(
        chat_id=group.group_id,
        text=text_message["text"],
        parse_mode=text_message.get("parse_mode", "HTML"),
        reply_markup=text_message.get("reply_markup"),
    )
    poll_msg = await bot.send_poll(
        chat_id=group.group_id,
        question=poll_message["question"],
        options=poll_message["options"],
        correct_option_id=poll_message["correct_option_id"],
        explanation=poll_message["explanation"] or None,
        is_anonymous=True,
        type="quiz",
    )
    task.telegram_message_ids = [text_msg.message_id, poll_msg.message_id]
    task.message_id = poll_msg.message_id
    task.group_id = group.id
    return poll_msg


async def publish_task_by_id(task_id: int, message, db_session: AsyncSession, bot: Bot, user_chat_id: int) -> bool:
    """
    Публикует все переводы задачи по её ID и translation_group_id.
    Отправляет вебхуки на все активные URL вебхуков после публикации.
    Обновляет поле error при возникновении ошибок.
    """
    webhook_data_list = []  # Список для хранения данных вебхуков
    failed_publications = []  # Список для хранения неудачных публикаций

    try:
        logger.info(f"🟢 Процесс публикации задачи с ID {task_id} запущен для пользователя {user_chat_id}.")

        # Инициализация DefaultLinkService
        default_link_service = DefaultLinkService(db_session)

        # Получаем задачу вместе с её переводами, топиком и подтопиком
        result = await db_session.execute(
            select(Task)
            .options(
                joinedload(Task.translations),
                joinedload(Task.topic),
                joinedload(Task.subtopic)
            )
            .where(Task.id == task_id)
        )
        task = result.unique().scalar_one_or_none()

        if task is None:
            logger.error(f"🔍 Задача с ID {task_id} не найдена")
            await message.answer(f"🔍 Задача с ID {task_id} не найдена")
            return False

        # Проверка времени с последней публикации
        if task.published and task.publish_date:
            utc_now = datetime.now(tz=pytz.utc)
            if task.publish_date > utc_now - timedelta(days=30):
                time_left = (task.publish_date + timedelta(days=30)) - utc_now
                await message.answer(
                    f"⚠️ Задача с ID {task_id} уже опубликована {task.publish_date.strftime('%Y-%m-%d %H:%M:%S')}.\n"
                    f"Следующая публикация доступна через {time_left.days} дней и {time_left.seconds // 3600} часов."
                )
                return False

        # Статистика публикации
        total_translations = 0
        published_count = 0
        failed_count = 0
        published_languages = []
        published_task_ids = []
        group_names = set()

        # Получаем все задачи с тем же translation_group_id
        result = await db_session.execute(
            select(Task)
            .options(
                joinedload(Task.translations),
                joinedload(Task.topic),
                joinedload(Task.subtopic)
            )
            .where(Task.translation_group_id == task.translation_group_id)
        )
        tasks_in_group = result.unique().scalars().all()

        # Получение списка активных вебхуков
        webhook_service = WebhookService(db_session)
        active_webhooks = await webhook_service.get_active_webhooks()
        logger.info(f"📥 Список активных вебхуков: {[wh.url for wh in active_webhooks]}")
        if not active_webhooks:
            logger.warning("⚠️ Нет активных вебхуков для отправки.")
            await message.answer("⚠️ Нет активных вебхуков для отправки.")

        # Публикация каждого перевода
        for task_in_group in tasks_in_group:
            # Проверка, что задача не помечена как ошибка
            if task_in_group.error:
                logger.warning(f"⚠️ Задача с ID {task_in_group.id} помечена как с ошибкой. Пропуск.")
                await message.answer(f"⚠️ Задача с ID `{task_in_group.id}` помечена как с ошибкой. Пропуск.")
                continue

            for translation in task_in_group.translations:
                total_translations += 1
                try:
                    # Получаем группу по топику и языку
                    group = await get_group_by_topic_and_language(db_session, task_in_group.topic_id, translation.language)
                    
                    # Логирование начала публикации
                    publication_start_msg = log_publication_start(
                        task_id=task_in_group.id,
                        translation_id=translation.id,
                        language=translation.language,
                        target=f"канал '{group.group_name if group else 'Неизвестно'}'"
                    )
                    await message.answer(publication_start_msg)

                    # Подготовка публикации
                    await message.answer(f"🔧 Начало подготовки публикации для задачи ID {task_in_group.id} с переводом ID {translation.id} на языке {translation.language}")
                    
                    image_message, text_message, poll_message, button_message, external_link, dont_know_option = await prepare_publication(
                        task=task_in_group,
                        translation=translation,
                        db_session=db_session,
                        default_link_service=default_link_service,
                        user_chat_id=user_chat_id
                    )
                    
                    await message.answer(f"✅ Подготовка публикации завершена для задачи ID {task_in_group.id}")

                    if not group:
                        failed_count += 1
                        logger.warning(f"Группа для языка '{translation.language}' не найдена.")
                        failed_publications.append({
                            "task_id": task_in_group.id,
                            "translation_id": translation.id,
                            "language": translation.language,
                            "error": "Группа не найдена"
                        })
                        # Помечаем задачу как с ошибкой
                        task_in_group.error = True
                        await db_session.commit()
                        continue

                    # Публикация: вопрос текстом (с кнопкой) и опрос
                    await message.answer(f"📝 Отправка вопроса и опроса в канал {group.group_name}...")
                    poll_msg = await send_task_post(bot, group, task_in_group, text_message, poll_message)
                    await db_session.commit()
                    await message.answer(f"✅ Пост отправлен (message_id опроса: {poll_msg.message_id})")

                    # Получение username канала (если есть)
                    chat = await bot.get_chat(group.group_id)
                    channel_username = chat.username
                    if not channel_username:
                        logger.info(f"Username канала для chat_id {group.group_id} не найден. Используем group_id для формирования ссылки.")
                        channel_username = None  # Передаем None, webhook_utils обработает это

                    # Формируем webhook_data
                    full_data = await create_full_webhook_data_for_task(task, db_session)
                    webhook_data = {
                        "task": full_data.get("task"),
                        "translations": full_data.get("translations")
                    }
                    
                    # Формируем poll_link
                    if channel_username:
                        poll_link = f"https://t.me/{channel_username}/{poll_msg.message_id}"
                    else:
                        # Используем group_id для формирования ссылки (убираем -100 в начале)
                        group_id_str = str(group.group_id).replace('-100', '')
                        poll_link = f"https://t.me/c/{group_id_str}/{poll_msg.message_id}"
                    log_webhook_data(webhook_data)
                    webhook_data_list.append(webhook_data)

                    # Сохранение информации об опросе
                    task_poll = TaskPoll(
                        task_id=task_in_group.id,
                        translation_id=translation.id,
                        poll_id=poll_msg.poll.id if hasattr(poll_msg, 'poll') and hasattr(poll_msg.poll, 'id') else None,
                        poll_question=translation.question,
                        poll_options=translation.answers,
                        is_anonymous=poll_msg.poll.is_anonymous if hasattr(poll_msg, 'poll') and hasattr(poll_msg.poll, 'is_anonymous') else True,
                        allows_multiple_answers=poll_msg.poll.allows_multiple_answers if hasattr(poll_msg, 'poll') and hasattr(poll_msg.poll, 'allows_multiple_answers') else False,
                        poll_type=poll_msg.poll.type if hasattr(poll_msg, 'poll') and hasattr(poll_msg.poll, 'type') else "quiz",
                        # Указываем значение по умолчанию
                        total_voter_count=poll_msg.poll.total_voter_count if hasattr(poll_msg, 'poll') and hasattr(poll_msg.poll, 'total_voter_count') else 0,
                        poll_link=poll_link
                    )
                    db_session.add(task_poll)
                    await db_session.commit()

                    # Логирование получения username канала
                    username_msg = log_username_received(group_name=group.group_name, channel_username=channel_username)
                    await message.answer(username_msg)

                    # Обновление статуса перевода
                    translation.published = True
                    translation.publish_date = datetime.now(tz=pytz.utc)
                    task_in_group.published = True  # Исправлено: устанавливаем Boolean
                    task_in_group.publish_date = datetime.now(tz=pytz.utc)  # Устанавливаем дату отдельно
                    published_languages.append(translation.language)
                    published_task_ids.append(task_in_group.id)
                    group_names.add(group.group_name)
                    published_count += 1

                    # Лог о публикации
                    logger.info(
                        f"✅ Публикована задача с ID {task_in_group.id} на канал '{group.group_name}' "
                        f"({translation.language})."
                    )
                    
                    # Уведомление об успешной публикации
                    success_detail_msg = (
                        f"🎉 Задача {task_in_group.id} ПОЛНОСТЬЮ опубликована!\n"
                        f"📷 Изображение: ✅\n"
                        f"📝 Детали: ✅\n"
                        f"📊 Опрос: ✅ (poll_id: {poll_msg.poll.id if hasattr(poll_msg, 'poll') and hasattr(poll_msg.poll, 'id') else 'N/A'})\n"
                        f"🔗 Кнопка: ✅"
                    )
                    await message.answer(success_detail_msg)

                    # Логирование и пауза
                    sleep_time = random.randint(3, 6)
                    pause_msg = log_pause(
                        sleep_time=sleep_time,
                        task_id=task_in_group.id,
                        language=translation.language,
                        group_name=group.group_name
                    )
                    await message.answer(pause_msg)
                    await asyncio.sleep(sleep_time)

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Ошибка при публикации перевода: {str(e)}")
                    failed_publications.append({
                        "task_id": task_in_group.id,
                        "translation_id": translation.id,
                        "language": translation.language,
                        "error": str(e)
                    })
                    # Помечаем задачу как с ошибкой
                    task_in_group.error = True
                    await db_session.commit()
                    continue

        # Отправка вебхуков
        if webhook_data_list and active_webhooks:
            logger.info(f"📤 Отправка вебхуков на {len(active_webhooks)} сервисов.")
            await message.answer(f"📤 Отправка вебхуков на {len(active_webhooks)} сервисов.")

            try:
                # <-- Вызываем новую логику send_webhooks
                results = await webhook_service.send_webhooks(
                    webhooks_data=webhook_data_list,
                    webhooks=active_webhooks,
                    bot=bot,
                    admin_chat_id=user_chat_id
                )
                success_count = sum(1 for r in results if r)
                failed_count += len(results) - success_count
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке вебхуков: {e}")
                await message.answer(f"❌ Ошибка при отправке вебхуков: {e}")

        # Собираем все опубликованные задачи для сводного вебхука
        published_tasks = []
        for task_id in set(published_task_ids):
            result = await db_session.execute(
                select(Task).options(
                    joinedload(Task.translations),
                    joinedload(Task.polls),
                    joinedload(Task.topic),
                    joinedload(Task.subtopic),
                    joinedload(Task.group)
                ).where(Task.id == task_id)
            )
            task = result.unique().scalar_one_or_none()
            if task:
                published_tasks.append(task)

        # Отправка сводного вебхука
        if published_tasks and active_webhooks:
            logger.info(f"📤 Отправка сводного вебхука на {len(active_webhooks)} сервисов для {len(published_tasks)} задач.")
            await message.answer(f"📤 Отправка сводного вебхука на {len(active_webhooks)} сервисов.")

            try:
                await webhook_service.send_bulk_webhook_for_tasks(
                    tasks=published_tasks,
                    webhooks=active_webhooks,
                    bot=bot,
                    admin_chat_id=user_chat_id
                )
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке сводного вебхука: {e}")
                await message.answer(f"❌ Ошибка при отправке сводного вебхука: {e}")


        # Обновление статуса задач
        if published_count > 0:
            try:
                for task_in_group in tasks_in_group:
                    if task_in_group.id in published_task_ids:
                        task_in_group.published = True
                        task_in_group.publish_date = datetime.now(tz=pytz.utc)
                await db_session.commit()

                success_message = log_final_summary(
                    published_task_ids=set(published_task_ids),
                    published_count=published_count,
                    total_translations=total_translations,
                    languages=published_languages,
                    groups=group_names
                )
                await message.answer(success_message)
                return True
            except Exception as e:
                logger.error(f"❌ Ошибка при обновлении статуса задач: {e}")
                await db_session.rollback()
                await message.answer(f"❌ Ошибка при обновлении статуса задач: {e}")
                return False
        else:
            try:
                await db_session.rollback()
                failure_message = (
                    f"❌ Публикация группы задач `{task.translation_group_id}` завершилась неудачно.\n"
                    f"📜 Всего переводов: {total_translations}\n"
                    f"⚠️ Не удалось опубликовать: {failed_count}\n\n"
                    "📋 Детали ошибок:\n" +
                    "\n".join(
                        f"• Задача ID `{fail['task_id']}`, Перевод ID `{fail.get('translation_id', 'N/A')}`, "
                        f"Язык: `{fail['language']}`\n  - Ошибка: {fail['error']}"
                        for fail in failed_publications
                    )
                )
                logger.error(f"❌ Импорт завершился с ошибками:\n{failure_message}")
                await message.answer(failure_message)
                return False
            except Exception as e:
                logger.error(f"❌ Ошибка при откате транзакции: {e}")
                # Не пытаемся делать rollback повторно, если уже была ошибка
                await message.answer(f"❌ Ошибка при откате транзакции: {e}")
                return False

    except Exception as e:
        logger.error(f"⚠️ Ошибка при публикации задачи с ID {task_id}: {str(e)}")
        try:
            await db_session.rollback()
        except Exception as rollback_error:
            logger.error(f"❌ Ошибка при откате транзакции: {rollback_error}")
        await message.answer(f"⚠️ Ошибка при публикации задачи с ID {task_id}: {str(e)}")
        return False






async def publish_task_by_translation_group(
    translation_group_id: UUID,
    message,
    db_session: AsyncSession,
    bot: Bot,
    admin_chat_id: int
) -> Tuple[bool, int, int, int]:
    """
    Публикует по одной самой старой задаче из каждого топика со всеми их переводами.
    Отправляет вебхуки и обновляет статус задач.

    Args:
        translation_group_id (UUID): Игнорируется, оставлен для совместимости.
        message: Сообщение от пользователя.
        db_session (AsyncSession): Сессия SQLAlchemy.
        bot (Bot): Экземпляр Aiogram Bot.
        admin_chat_id (int): ID чата администратора.

    Returns:
        Tuple[bool, int, int, int]: Успех (True/False), количество опубликованных, неудачных и всего переводов.
    """
    webhook_data_list = []
    published_count = 0
    failed_count = 0
    total_translations = 0
    published_task_ids = []
    published_languages = set()
    published_group_names = set()
    failed_publications = []

    try:
        logger.info(f"🚀 Начало публикации задач по топикам для пользователя {admin_chat_id}")
        await message.answer("🚀 Начинаю поиск и публикацию задач по топикам...")

        utc_now = datetime.now(tz=pytz.utc)
        one_month_ago = utc_now - timedelta(days=30)

        # Получение всех топиков
        stmt = select(Topic).distinct()
        with db_session.no_autoflush:
            result = await db_session.execute(stmt)
            topics = result.scalars().all()

        if not topics:
            logger.info("⚠️ Нет топиков с задачами.")
            await message.answer("⚠️ Нет топиков с задачами.")
            return False, 0, 0, 0

        logger.info(f"📚 Найдено топиков: {len(topics)}")
        await message.answer(f"📚 Найдено топиков: {len(topics)}.")

        webhook_service = WebhookService(db_session)
        active_webhooks = await webhook_service.get_active_webhooks()
        logger.info(f"📥 Список активных вебхуков: {[wh.url for wh in active_webhooks]}")
        if not active_webhooks:
            logger.warning("⚠️ Нет активных вебхуков для отправки.")
            await message.answer("⚠️ Нет активных вебхуков для отправки.")

        default_link_service = DefaultLinkService(db_session)

        tasks_to_publish = []
        for topic in topics:
            # Выбираем одну самую старую задачу из топика
            stmt = (
                select(Task)
                .options(
                    joinedload(Task.translations),
                    joinedload(Task.topic),
                    joinedload(Task.subtopic)
                )
                .where(
                    Task.topic_id == topic.id,
                    Task.error == False,
                    (Task.publish_date.is_(None)) | (Task.publish_date < one_month_ago)
                )
                .order_by(Task.create_date.asc())
                .limit(1)
            )
            with db_session.no_autoflush:
                result = await db_session.execute(stmt)
                task = result.unique().scalar_one_or_none()

            if task and task.translations:
                tasks_to_publish.append(task)
            else:
                logger.info(f"ℹ️ Нет подходящих задач для топика '{topic.name}'")

        if not tasks_to_publish:
            logger.info("⚠️ Нет задач для публикации.")
            await message.answer("⚠️ Нет задач для публикации.")
            return False, 0, 0, 0

        logger.info(f"📚 Найдено задач для публикации: {len(tasks_to_publish)}")
        await message.answer(f"📚 Найдено задач для публикации: {len(tasks_to_publish)}")

        # Публикуем каждую задачу со всеми её переводами
        for task in tasks_to_publish:
            if task.error:
                logger.warning(f"⚠️ Задача {task.id} в топике '{task.topic.name}' имеет ошибку. Пропуск.")
                await message.answer(f"⚠️ Задача {task.id} в топике '{task.topic.name}' имеет ошибку. Пропуск.")
                continue

            # Находим все задачи с тем же translation_group_id
            stmt = (
                select(Task)
                .options(
                    joinedload(Task.translations),
                    joinedload(Task.topic),
                    joinedload(Task.subtopic)
                )
                .where(Task.translation_group_id == task.translation_group_id)
            )
            with db_session.no_autoflush:
                result = await db_session.execute(stmt)
                tasks_in_group = result.unique().scalars().all()

            logger.info(f"🔄 Публикация задачи ID {task.id} (группа {task.translation_group_id}) с {len(tasks_in_group)} задачами")

            for task_in_group in tasks_in_group:
                if task_in_group.error:
                    logger.warning(f"⚠️ Задача {task_in_group.id} имеет ошибку. Пропуск.")
                    await message.answer(f"⚠️ Задача {task_in_group.id} имеет ошибку. Пропуск.")
                    continue

                for translation in task_in_group.translations:
                    try:
                        # Получаем группу по топику и языку
                        group = await get_group_by_topic_and_language(db_session, task_in_group.topic_id, translation.language)
                        
                        target = f"канал '{group.group_name if group else 'Неизвестно'}'"
                        start_msg = (
                            f"🔄 Публикация задачи ID `{task_in_group.id}` (перевод ID `{translation.id}`) "
                            f"на языке `{translation.language}` в топике '{task_in_group.topic.name}' в {target}"
                        )
                        logger.info(start_msg)
                        await message.answer(start_msg)

                        await message.answer(f"🔧 Начало подготовки публикации для задачи ID {task_in_group.id} с переводом ID {translation.id} на языке {translation.language}")
                        
                        image_message, text_message, poll_message, button_message, external_link, dont_know_option = await prepare_publication(
                            task=task_in_group,
                            translation=translation,
                            db_session=db_session,
                            default_link_service=default_link_service,
                            user_chat_id=admin_chat_id
                        )
                        
                        await message.answer(f"✅ Подготовка публикации завершена для задачи ID {task_in_group.id}")
                        
                        if not group:
                            error_msg = f"🚫 Группа не найдена для задачи {task_in_group.id} (перевод {translation.id}, язык {translation.language})"
                            logger.error(f"❌ {error_msg}")
                            await message.answer(f"❌ {error_msg}")
                            failed_count += 1
                            failed_publications.append({
                                "task_id": task_in_group.id,
                                "translation_id": translation.id,
                                "language": translation.language,
                                "error": "Группа не найдена"
                            })
                            task_in_group.error = True
                            await db_session.commit()
                            continue

                        # Вопрос текстом (с кнопкой) и опрос
                        poll_msg = await send_task_post(bot, group, task_in_group, text_message, poll_message)
                        await db_session.commit()
                        await asyncio.sleep(1)

                        chat = await bot.get_chat(group.group_id)
                        channel_username = chat.username
                        if not channel_username:
                            logger.info(f"Username канала для группы {group.group_name} не найден. Используем group_id для формирования ссылки.")
                            channel_username = None  # Передаем None, webhook_utils обработает это

                        await message.answer(log_username_received(group.group_name, channel_username))

                        # Формируем webhook_data
                        full_data = await create_full_webhook_data_for_task(task_in_group, db_session)
                        webhook_data = {
                            "task": full_data.get("task"),
                            "translations": full_data.get("translations")
                        }
                        
                        # Формируем poll_link (не используется в этом месте, но оставляем для совместимости)
                        if channel_username:
                            poll_link = f"https://t.me/{channel_username}/{poll_msg.message_id}"
                        else:
                            # Используем group_id для формирования ссылки (убираем -100 в начале)
                            group_id_str = str(group.group_id).replace('-100', '')
                            poll_link = f"https://t.me/c/{group_id_str}/{poll_msg.message_id}"
                        webhook_data_list.append(webhook_data)

                        # Обновление статуса перевода и задачи
                        translation.published = True
                        translation.publish_date = utc_now
                        task_in_group.published = True
                        task_in_group.publish_date = utc_now
                        published_languages.add(translation.language)
                        published_task_ids.append(task_in_group.id)
                        published_group_names.add(group.group_name)
                        published_count += 1
                        total_translations += 1

                        success_msg = (
                            f"✅ Опубликована задача ID `{task_in_group.id}` (перевод ID `{translation.id}`, "
                            f"язык `{translation.language}`) в топике '{task_in_group.topic.name}' в '{group.group_name}'"
                        )
                        logger.info(success_msg)
                        await message.answer(success_msg)
                        
                        # Уведомление об успешной публикации
                        success_detail_msg = (
                            f"🎉 Задача {task_in_group.id} ПОЛНОСТЬЮ опубликована!\n"
                            f"📷 Изображение: ✅\n"
                            f"📝 Детали: ✅\n"
                            f"📊 Опрос: ✅ (poll_id: {poll_msg.poll.id if hasattr(poll_msg, 'poll') and hasattr(poll_msg.poll, 'id') else 'N/A'})\n"
                            f"🔗 Кнопка: ✅"
                        )
                        await message.answer(success_detail_msg)

                        sleep_time = random.randint(3, 6)
                        pause_msg = (
                            f"⏸️ Пауза {sleep_time} сек перед следующей публикацией: "
                            f"задача ID `{task_in_group.id}`, перевод ID `{translation.id}`, язык `{translation.language}`"
                        )
                        logger.info(pause_msg)
                        await message.answer(pause_msg)
                        await asyncio.sleep(sleep_time)

                    except Exception as e:
                        failed_count += 1
                        error_msg = (
                            f"❌ Ошибка публикации задачи ID `{task_in_group.id}` (перевод ID `{translation.id}`, "
                            f"язык `{translation.language}`) в топике '{task_in_group.topic.name}': {e}"
                        )
                        logger.error(error_msg)
                        failed_publications.append({
                            "task_id": task_in_group.id,
                            "translation_id": translation.id,
                            "language": translation.language,
                            "error": str(e)
                        })
                        task_in_group.error = True
                        await db_session.commit()
                        await message.answer(error_msg)
                        continue

        # Собираем все опубликованные задачи
        published_tasks_map = {}
        for task_id in set(published_task_ids):
            if task_id not in published_tasks_map:
                result = await db_session.execute(
                    select(Task).options(
                        joinedload(Task.translations),
                    joinedload(Task.polls),
                        joinedload(Task.topic),
                        joinedload(Task.subtopic),
                        joinedload(Task.group)
                    ).where(Task.id == task_id)
                )
                task = result.unique().scalar_one_or_none()
                if task:
                    published_tasks_map[task_id] = task
        
        published_tasks = list(published_tasks_map.values())

        if published_tasks and active_webhooks:
            logger.info(f"📤 Отправка сводного вебхука на {len(active_webhooks)} сервисов для {len(published_tasks)} задач.")
            await message.answer(f"📤 Отправка сводного вебхука на {len(active_webhooks)} сервисов.")
            
            try:
                await webhook_service.send_bulk_webhook_for_tasks(
                    tasks=published_tasks,
                    webhooks=active_webhooks,
                    bot=bot,
                    admin_chat_id=admin_chat_id
                )
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке сводного вебхука: {e}", exc_info=True)
                await message.answer(f"❌ Ошибка при отправке сводного вебхука: {e}")


        if published_count > 0:
            try:
                await db_session.commit()
                success_message = (
                    f"✅ Успешно опубликованы задачи: {', '.join(map(str, set(published_task_ids)))}\n"
                    f"🌍 Опубликовано переводов: {published_count} из {total_translations}\n"
                    f"📜 Языки: {', '.join(sorted(published_languages))}\n"
                    f"🏷️ Группы: {', '.join(sorted(published_group_names))}"
                )
                logger.info(success_message)
                await message.answer(success_message)
                return True, published_count, failed_count, total_translations
            except Exception as e:
                logger.error(f"❌ Ошибка при обновлении статуса задач: {e}")
                try:
                    await db_session.rollback()
                except Exception as rollback_error:
                    logger.error(f"❌ Ошибка при откате транзакции: {rollback_error}")
                await message.answer(f"❌ Ошибка при обновлении статуса задач: {e}")
                return False, published_count, failed_count, total_translations
        else:
            try:
                await db_session.rollback()
            except Exception as rollback_error:
                logger.error(f"❌ Ошибка при откате транзакции: {rollback_error}")
            failure_message = (
                f"❌ Публикация завершилась неудачно.\n"
                f"📜 Всего переводов: {total_translations}\n"
                f"⚠️ Не удалось опубликовать: {failed_count}\n\n"
                "📋 Детали ошибок:\n" +
                "\n".join(
                    f"• Задача ID `{fail['task_id']}`, Перевод ID `{fail.get('translation_id', 'N/A')}`, "
                    f"Язык: `{fail['language']}`\n  - Ошибка: {fail['error']}"
                    for fail in failed_publications
                )
            )
            logger.error(failure_message)
            await message.answer(failure_message)
            return False, published_count, failed_count, total_translations

    except Exception as e:
        error_msg = f"❌ Общая ошибка при публикации задач по топикам: {str(e)}"
        logger.exception(error_msg)
        try:
            await db_session.rollback()
        except Exception as rollback_error:
            logger.error(f"❌ Ошибка при откате транзакции: {rollback_error}")
        await message.answer(error_msg)
        return False, published_count, failed_count, total_translations


