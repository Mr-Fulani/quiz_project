# bot/services/publication_service.py

import logging
from datetime import datetime, timedelta
from typing import Tuple
from uuid import UUID
import asyncio
import random

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.handlers.webhook_handler import get_incorrect_answers
from bot.services.default_link_service import DefaultLinkService
from bot.services.image_service import generate_image_if_needed
from bot.services.task_service import prepare_publication
from bot.services.webhook_service import WebhookService
from database.models import Task, Group, TaskTranslation
from webhook_sender import send_webhooks_sequentially

logger = logging.getLogger(__name__)


async def publish_task_by_id(task_id: int, message, db_session: AsyncSession, bot: Bot, user_chat_id: int) -> bool:
    """
    Публикует все переводы задачи по её ID и translation_group_id.
    Отправляет вебхуки на все активные URL вебхуков после публикации.
    """
    webhook_data_list = []  # Список для хранения данных вебхуков

    try:
        logger.info(f"🚀 Начало публикации задачи с ID {task_id}")

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
            if task.publish_date > datetime.now() - timedelta(days=30):
                time_left = (task.publish_date + timedelta(days=30)) - datetime.now()
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

        # Публикация каждого перевода
        for task_in_group in tasks_in_group:
            image_url = await generate_image_if_needed(task_in_group, user_chat_id)
            if not image_url:
                logger.error(f"Ошибка при генерации изображения для задачи с ID {task_in_group.id}")
                continue

            for translation in task_in_group.translations:
                total_translations += 1
                try:
                    # Подготовка публикации
                    image_message, text_message, poll_message, button_message = await prepare_publication(
                        task=task_in_group,
                        translation=translation,
                        image_url=image_url,
                        db_session=db_session,
                        default_link_service=default_link_service,  # Добавлено
                        user_chat_id=user_chat_id
                    )

                    # Поиск группы для публикации
                    result = await db_session.execute(
                        select(Group)
                        .where(Group.topic_id == task_in_group.topic_id)
                        .where(Group.language == translation.language)
                    )
                    group = result.scalar_one_or_none()

                    if not group:
                        failed_count += 1
                        logger.warning(f"Группа для языка '{translation.language}' не найдена.")
                        continue

                    # Публикация контента
                    image_msg = await bot.send_photo(
                        chat_id=group.group_id,
                        photo=image_message["photo"],
                        caption=image_message["caption"],
                        parse_mode="MarkdownV2"
                    )

                    text_msg = await bot.send_message(
                        chat_id=group.group_id,
                        text=text_message["text"],
                        parse_mode=text_message.get("parse_mode", "MarkdownV2")
                    )

                    poll_msg = await bot.send_poll(
                        chat_id=group.group_id,
                        question=poll_message["question"],
                        options=poll_message["options"],
                        correct_option_id=poll_message["correct_option_id"],
                        explanation=poll_message["explanation"],
                        is_anonymous=True,
                        type="quiz"
                    )

                    button_msg = await bot.send_message(
                        chat_id=group.group_id,
                        text=button_message["text"],
                        reply_markup=button_message["reply_markup"]
                    )

                    # Получение username канала
                    chat = await bot.get_chat(group.group_id)
                    channel_username = chat.username
                    if not channel_username:
                        failed_count += 1
                        logger.warning(f"Username канала для chat_id {group.group_id} не найден.")
                        continue

                    # Формирование данных для вебхука
                    poll_link = f"https://t.me/{channel_username}/{poll_msg.message_id}"
                    webhook_data = {
                        "type": "quiz_published",
                        "poll_link": poll_link,
                        "image_url": image_url,
                        "question": translation.question,
                        "correct_answer": translation.correct_answer,
                        "incorrect_answers": await get_incorrect_answers(translation.answers, translation.correct_answer),
                        "language": translation.language,
                        "group": {
                            "id": group.id,
                            "name": group.group_name
                        },
                        "caption": image_message["caption"] or "",
                        "published_at": datetime.utcnow().isoformat()
                    }

                    webhook_data_list.append(webhook_data)

                    # Обновление статуса перевода
                    translation.published = True
                    translation.publish_date = datetime.now()
                    published_languages.append(translation.language)
                    published_task_ids.append(task_in_group.id)
                    group_names.add(group.group_name)
                    published_count += 1

                    # Лог о публикации
                    logger.info(
                        f"✅ Публикована задача с ID {task_in_group.id} на канал '{group.group_name}' "
                        f"({translation.language})."
                    )

                    # Добавляем паузу между публикациями переводов
                    sleep_time = random.randint(3, 6)
                    pause_log_msg = (
                        f"⏸️ Пауза {sleep_time} секунд перед следующей публикацией "
                        f"(Задача ID {task_in_group.id}, Язык: {translation.language}, Канал: {group.group_name})"
                    )
                    logger.info(pause_log_msg)
                    await message.answer(pause_log_msg)
                    await asyncio.sleep(sleep_time)

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Ошибка при публикации перевода: {str(e)}")
                    continue

        # Отправка вебхуков
        if webhook_data_list and active_webhooks:
            logger.info(f"📤 Отправка вебхуков на {len(active_webhooks)} сервисов")
            try:
                results = await send_webhooks_sequentially(webhook_data_list, active_webhooks, db_session, bot)
                success_count = sum(1 for r in results if r)
                failed_count += len(results) - success_count
                logger.info(
                    f"📊 Результаты отправки вебхуков: успешно - {success_count}, неудачно - {len(results) - success_count}"
                )
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке вебхуков: {str(e)}")

        # Обновление статуса задач
        if published_count > 0:
            for task_in_group in tasks_in_group:
                if task_in_group.id in published_task_ids:
                    task_in_group.published = True
                    task_in_group.publish_date = datetime.now()
            await db_session.commit()

            success_message = (
                f"✅ Задачи с ID: {', '.join(map(str, set(published_task_ids)))} успешно опубликованы!\n"
                f"🌍 Опубликовано переводов: {published_count} из {total_translations}\n"
                f"📜 Языки: {', '.join(published_languages)}\n"
                f"🏷️ Группы: {', '.join(group_names)}"
            )
            await message.answer(success_message)
            return True
        else:
            await db_session.rollback()
            await message.answer(f"❌ Публикация не удалась. Проверьте логи для подробностей.")
            return False

    except Exception as e:
        logger.error(f"⚠️ Ошибка при публикации задачи с ID {task_id}: {str(e)}")
        await db_session.rollback()
        await message.answer(f"⚠️ Ошибка при публикации задачи с ID {task_id}: {str(e)}")
        return False


async def publish_translation(translation: TaskTranslation, bot: Bot, db_session: AsyncSession, user_chat_id: int) -> bool:
    """
    Публикует отдельный перевод задачи.
    Отправляет вебхуки на все активные URL вебхуков после публикации.
    """
    webhook_data_list = []

    try:
        # Инициализация DefaultLinkService
        default_link_service = DefaultLinkService(db_session)

        # Получение списка активных вебхуков
        webhook_service = WebhookService(db_session)
        active_webhooks = await webhook_service.get_active_webhooks()

        # Генерация изображения
        image_url = await generate_image_if_needed(translation.task, user_chat_id)
        if not image_url:
            logger.error(f"🚫 Ошибка генерации изображения для перевода ID {translation.id}")
            return False

        # Подготовка данных для публикации
        image_message, text_message, poll_message, button_message = await prepare_publication(
            task=translation.task,
            translation=translation,
            image_url=image_url,
            db_session=db_session,
            default_link_service=default_link_service,  # Добавлено
            user_chat_id=user_chat_id
        )

        # Поиск группы для публикации
        result = await db_session.execute(
            select(Group)
            .where(Group.topic_id == translation.task.topic_id)
            .where(Group.language == translation.language)
        )
        group = result.scalar_one_or_none()

        if not group:
            logger.error(f"🚫 Группа не найдена для языка {translation.language}")
            return False

        # Публикация контента
        image_msg = await bot.send_photo(
            chat_id=group.group_id,
            photo=image_message["photo"],
            caption=image_message["caption"],
            parse_mode="MarkdownV2"
        )

        text_msg = await bot.send_message(
            chat_id=group.group_id,
            text=text_message["text"],
            parse_mode=text_message.get("parse_mode", "MarkdownV2")
        )

        poll_msg = await bot.send_poll(
            chat_id=group.group_id,
            question=poll_message["question"],
            options=poll_message["options"],
            correct_option_id=poll_message["correct_option_id"],
            explanation=poll_message["explanation"],
            is_anonymous=True,
            type="quiz"
        )

        button_msg = await bot.send_message(
            chat_id=group.group_id,
            text=button_message["text"],
            reply_markup=button_message["reply_markup"]
        )

        # Получение username канала
        chat = await bot.get_chat(group.group_id)
        channel_username = chat.username
        if not channel_username:
            logger.error(f"❌ Username канала не найден для группы {group.group_name}")
            return False

        # Формирование данных для вебхука
        poll_link = f"https://t.me/{channel_username}/{poll_msg.message_id}"
        webhook_data = {
            "type": "quiz_published",
            "poll_link": poll_link,
            "image_url": image_url,
            "question": translation.question,
            "correct_answer": translation.correct_answer,
            "incorrect_answers": await get_incorrect_answers(translation.answers, translation.correct_answer),
            "language": translation.language,
            "group": {
                "id": group.id,
                "name": group.group_name
            },
            "caption": image_message["caption"] or "",
            "published_at": datetime.utcnow().isoformat()
        }

        webhook_data_list.append(webhook_data)

        # Лог о публикации перевода
        logger.info(
            f"✅ Публикован перевод задачи (ID задачи: {translation.task_id}, Перевод ID: {translation.id}) на канал '{group.group_name}' "
            f"({translation.language})."
        )

        # Отправка вебхуков
        if webhook_data_list and active_webhooks:
            logger.info(f"📤 Отправка вебхуков для перевода {translation.id}")
            try:
                results = await send_webhooks_sequentially(webhook_data_list, active_webhooks, db_session, bot)
                success_count = sum(1 for r in results if r)
                failed_count = len(results) - success_count
                logger.info(f"📊 Результаты отправки вебхуков: успешно - {success_count}, неудачно - {failed_count}")
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке вебхуков: {str(e)}")
                return False

        # Обновление статуса перевода
        translation.published = True
        translation.publish_date = datetime.now()
        await db_session.commit()

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при публикации перевода {translation.id}: {str(e)}")
        await db_session.rollback()
        return False


async def publish_task_by_translation_group(
        translation_group_id: UUID,
        message,
        db_session: AsyncSession,
        bot: Bot,
        user_chat_id: int
) -> Tuple[bool, int, int, int]:
    """
    Публикует все переводы задач в группе переводов.
    Отправляет вебхуки на все активные URL вебхуков после публикации.
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
        logger.info(f"🚀 Начало публикации группы переводов с ID {translation_group_id}")

        # Получаем все задачи группы
        stmt = select(Task).options(
            joinedload(Task.translations),
            joinedload(Task.topic),
            joinedload(Task.subtopic)
        ).where(Task.translation_group_id == translation_group_id)

        result = await db_session.execute(stmt)
        tasks = result.unique().scalars().all()

        if not tasks:
            logger.warning(f"⚠️ Нет задач для публикации в группе переводов {translation_group_id}")
            await message.answer(f"⚠️ Нет задач для публикации в группе переводов {translation_group_id}.")
            return False, 0, 0, 0

        total_translations = sum(len(task.translations) for task in tasks)
        logger.info(f"📚 Найдено задач для публикации: {total_translations} в группе переводов {translation_group_id}")

        # Получение списка активных вебхуков
        webhook_service = WebhookService(db_session)
        active_webhooks = await webhook_service.get_active_webhooks()

        # Инициализация DefaultLinkService
        default_link_service = DefaultLinkService(db_session)

        for task in tasks:
            # Проверка предыдущей публикации
            if task.published and task.publish_date:
                if task.publish_date > datetime.now() - timedelta(days=30):
                    logger.info(f"⚠️ Задача с ID {task.id} была опубликована {task.publish_date}. Пропуск.")
                    continue

            image_url = await generate_image_if_needed(task, user_chat_id)
            if not image_url:
                error_message = f"🚫 Ошибка генерации изображения для задачи {task.id}"
                logger.error(error_message)
                failed_count += len(task.translations)
                continue

            for translation in task.translations:
                try:
                    logger.info(f"🌍 Публикация перевода (ID: {translation.id}) на языке {translation.language}")

                    # Подготовка публикации
                    image_message, text_message, poll_message, button_message = await prepare_publication(
                        task=task,
                        translation=translation,
                        image_url=image_url,
                        db_session=db_session,
                        default_link_service=default_link_service,  # Добавлено
                        user_chat_id=user_chat_id
                    )

                    # Поиск группы
                    group_result = await db_session.execute(
                        select(Group)
                        .where(Group.topic_id == task.topic_id)
                        .where(Group.language == translation.language)
                    )
                    group = group_result.scalar_one_or_none()

                    if not group:
                        error_msg = f"🚫 Группа не найдена для языка {translation.language}"
                        logger.error(error_msg)
                        failed_count += 1
                        failed_publications.append({
                            "task_id": task.id,
                            "translation_id": translation.id,
                            "language": translation.language,
                            "error": "Группа не найдена"
                        })
                        continue

                    # Публикация контента
                    image_msg = await bot.send_photo(
                        chat_id=group.group_id,
                        photo=image_message["photo"],
                        caption=image_message["caption"],
                        parse_mode="MarkdownV2"
                    )

                    text_msg = await bot.send_message(
                        chat_id=group.group_id,
                        text=text_message["text"],
                        parse_mode=text_message.get("parse_mode", "MarkdownV2")
                    )

                    poll_msg = await bot.send_poll(
                        chat_id=group.group_id,
                        question=poll_message["question"],
                        options=poll_message["options"],
                        correct_option_id=poll_message["correct_option_id"],
                        explanation=poll_message["explanation"],
                        is_anonymous=True,
                        type="quiz"
                    )

                    button_msg = await bot.send_message(
                        chat_id=group.group_id,
                        text=button_message["text"],
                        reply_markup=button_message["reply_markup"]
                    )

                    # Получение username канала
                    chat = await bot.get_chat(group.group_id)
                    channel_username = chat.username
                    if not channel_username:
                        error_msg = f"❌ Username канала не найден для группы {group.group_name}"
                        logger.error(error_msg)
                        failed_count += 1
                        failed_publications.append({
                            "task_id": task.id,
                            "translation_id": translation.id,
                            "language": translation.language,
                            "error": "Username канала не найден"
                        })
                        continue

                    # Формирование данных для вебхука
                    poll_link = f"https://t.me/{channel_username}/{poll_msg.message_id}"
                    webhook_data = {
                        "type": "quiz_published",
                        "poll_link": poll_link,
                        "image_url": image_url,
                        "question": translation.question,
                        "correct_answer": translation.correct_answer,
                        "incorrect_answers": await get_incorrect_answers(translation.answers, translation.correct_answer),
                        "language": translation.language,
                        "group": {
                            "id": group.id,
                            "name": group.group_name
                        },
                        "caption": image_message["caption"] or "",
                        "published_at": datetime.utcnow().isoformat()
                    }

                    webhook_data_list.append(webhook_data)

                    # Отмечаем публикацию как успешную
                    translation.published = True
                    translation.publish_date = datetime.now()
                    published_count += 1
                    published_task_ids.append(task.id)
                    published_languages.add(translation.language)
                    published_group_names.add(group.group_name)

                    # Лог о публикации
                    logger.info(
                        f"✅ Публикована задача с ID {task.id} на канал '{group.group_name}' "
                        f"({translation.language})."
                    )

                    # Добавляем паузу между публикациями переводов
                    sleep_time = random.randint(3, 6)
                    pause_log_msg = (
                        f"⏸️ Пауза {sleep_time} секунд перед следующей публикацией "
                        f"(Задача ID {task.id}, Язык: {translation.language}, Канал: {group.group_name})"
                    )
                    logger.info(pause_log_msg)
                    await message.answer(pause_log_msg)
                    await asyncio.sleep(sleep_time)

                except Exception as e:
                    error_msg = f"❌ Ошибка при публикации перевода (ID: {translation.id}): {str(e)}"
                    logger.error(error_msg)
                    failed_count += 1
                    failed_publications.append({
                        "task_id": task.id,
                        "translation_id": translation.id,
                        "language": translation.language,
                        "error": str(e)
                    })
                    continue

        # Отправка вебхуков
        if webhook_data_list:
            logger.info(f"📤 Последовательная отправка {len(webhook_data_list)} вебхуков")
            try:
                results = await send_webhooks_sequentially(webhook_data_list, active_webhooks, db_session, bot)
                success_count = sum(1 for r in results if r)
                failed_count_webhooks = len(results) - success_count
                logger.info(
                    f"📊 Результаты отправки вебхуков: успешно - {success_count}, неудачно - {failed_count_webhooks}"
                )
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке вебхуков: {str(e)}")

        # Обновление статуса задач
        if published_count > 0:
            for task in tasks:
                if task.id in published_task_ids:
                    task.published = True
                    task.publish_date = datetime.now()
            await db_session.commit()

            success_message = (
                f"✅ Задачи с ID: {', '.join(map(str, set(published_task_ids)))} успешно опубликованы!\n"
                f"🌍 Опубликовано переводов: {published_count} из {total_translations}\n"
                f"📜 Языки: {', '.join(sorted(published_languages))}\n"
                f"🏷️ Группы: {', '.join(sorted(published_group_names))}"
            )
            logger.info(success_message)
            await message.answer(success_message)
            return True, published_count, failed_count, total_translations
        else:
            await db_session.rollback()
            failure_message = (
                f"❌ Публикация группы задач {translation_group_id} завершилась неудачно.\n"
                f"📜 Всего переводов: {total_translations}\n"
                f"⚠️ Не удалось опубликовать: {failed_count}\n\n"
                "📋 Детали ошибок:\n" +
                "\n".join(
                    f"• Задача ID {fail['task_id']}, Перевод ID {fail['translation_id']}, "
                    f"Язык: {fail['language']}\n  - Ошибка: {fail['error']}"
                    for fail in failed_publications
                )
            )
            logger.error(failure_message)
            await message.answer(failure_message)
            return False, published_count, failed_count, total_translations

    except Exception as e:
        error_msg = f"❌ Ошибка при публикации группы переводов {translation_group_id}: {str(e)}"
        logger.exception(error_msg)
        await db_session.rollback()
        await message.answer(error_msg)
        return False, published_count, failed_count, total_translations




