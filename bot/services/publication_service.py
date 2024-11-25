import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Tuple
from uuid import UUID


from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.handlers.webhook_handler import get_incorrect_answers
from bot.services.task_service import prepare_publication
from database.models import Task, Group, TaskTranslation
from bot.services.image_service import generate_image_if_needed
from webhook_sender import send_quiz_published_webhook, send_webhooks_sequentially



logger = logging.getLogger(__name__)



async def publish_task_by_id(task_id: int, message, db_session: AsyncSession, bot: Bot) -> bool:
    """
    Публикует все переводы задачи по её ID и translation_group_id.
    """
    webhook_data_list = []  # Список для хранения данных вебхуков

    try:
        logger.info(f"🚀 Начало публикации задачи с ID {task_id}")

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
            logger.error(f"🔍 Задача с ID {task_id} не найдена.")
            await message.answer(f"🔍 Задача с ID {task_id} не найдена.")
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

        # Публикация каждого перевода
        for task_in_group in tasks_in_group:
            image_url = await generate_image_if_needed(task_in_group)
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
                        image_url=image_url
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
                        continue

                    # Формирование данных для вебхука
                    poll_link = f"https://t.me/{channel_username}/{poll_msg.message_id}"
                    webhook_data = {
                        "type": "quiz_published",
                        "poll_link": poll_link,
                        "image_url": image_url,
                        "question": translation.question,
                        "correct_answer": translation.correct_answer,
                        "incorrect_answers": await get_incorrect_answers(translation.answers,
                                                                         translation.correct_answer),
                        "language": translation.language,
                        "group": {
                            "id": group.id,
                            "name": group.group_name
                        },
                        "caption": image_message["caption"] or "",
                        "published_at": datetime.utcnow().isoformat()
                    }

                    webhook_data_list.append(webhook_data)

                    translation.published = True
                    translation.publish_date = datetime.now()
                    published_languages.append(translation.language)
                    published_task_ids.append(task_in_group.id)
                    group_names.add(group.group_name)
                    published_count += 1

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Ошибка при публикации перевода: {str(e)}")
                    continue

        # Отправка вебхуков
        if webhook_data_list:
            logger.info(f"📤 Последовательная отправка {len(webhook_data_list)} вебхуков")
            try:
                results = await send_webhooks_sequentially(webhook_data_list)
                success_count = sum(1 for r in results if r)
                failed_count = len(results) - success_count
                logger.info(f"📊 Результаты отправки вебхуков: успешно - {success_count}, неудачно - {failed_count}")
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





async def publish_translation(translation: TaskTranslation, bot: Bot, db_session: AsyncSession) -> bool:
    """
    Публикует отдельный перевод задачи.
    """
    webhook_data_list = []  # Список для хранения данных вебхуков

    try:
        # Генерация изображения
        image_url = await generate_image_if_needed(translation.task)
        if not image_url:
            logger.error(f"🚫 Ошибка генерации изображения для перевода ID {translation.id}")
            return False

        # Подготовка данных для публикации
        image_message, text_message, poll_message, button_message = await prepare_publication(
            task=translation.task,
            translation=translation,
            image_url=image_url
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

        # Отправка вебхуков
        if webhook_data_list:
            logger.info(f"📤 Последовательная отправка вебхуков для перевода {translation.id}")
            try:
                results = await send_webhooks_sequentially(webhook_data_list)
                success_count = sum(1 for r in results if r)
                failed_count = len(results) - success_count
                logger.info(f"📊 Результаты отправки вебхуков: успешно - {success_count}, неудачно - {failed_count}")
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке вебхуков: {str(e)}")
                return False

        # Обновление статуса публикации
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
        bot: Bot
) -> Tuple[bool, int, int, int]:
    """
    Публикует все переводы задач в группе переводов.
    """
    webhook_data_list = []  # Список для хранения данных вебхуков
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

        for task in tasks:
            # Проверка предыдущей публикации
            if task.published and task.publish_date:
                if task.publish_date > datetime.now() - timedelta(days=30):
                    logger.info(f"⚠️ Задача с ID {task.id} была опубликована {task.publish_date}. Пропуск.")
                    continue

            image_url = await generate_image_if_needed(task)
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
                        image_url=image_url
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
                        "incorrect_answers": await get_incorrect_answers(translation.answers,
                                                                         translation.correct_answer),
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
                results = await send_webhooks_sequentially(webhook_data_list)
                success_count = sum(1 for r in results if r)
                failed_count_webhooks = len(results) - success_count
                logger.info(
                    f"📊 Результаты отправки вебхуков: успешно - {success_count}, неудачно - {failed_count_webhooks}")
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












# async def publish_task_by_translation_group(translation_group_id, message, db_session: AsyncSession, bot: Bot):
#     published_count = 0
#     failed_count = 0
#     total_translations = 0
#     published_task_ids = []
#     group_names = set()
#
#     try:
#         logger.info(f"🚀 Начало публикации группы переводов с ID {translation_group_id}")
#
#         result = await db_session.execute(
#             select(Task)
#             .options(
#                 joinedload(Task.translations),
#                 joinedload(Task.topic),
#                 joinedload(Task.subtopic)
#             )
#             .where(Task.translation_group_id == translation_group_id)
#         )
#
#         tasks = result.unique().scalars().all()
#         total_translations = len(tasks)
#
#         if total_translations == 0:
#             logger.warning(f"⚠️ Нет задач для публикации в группе переводов {translation_group_id}.")
#             await message.answer(f"⚠️ Нет задач для публикации в группе переводов {translation_group_id}.")
#             return False, published_count, failed_count, total_translations
#
#         logger.info(f"📚 Начало публикации группы переводов {translation_group_id}. Всего задач: {total_translations}")
#
#         # Флаг для отслеживания общего успеха публикации
#         all_publications_successful = True
#
#         for task in tasks:
#             # Проверка предыдущей публикации как раньше
#             if task.published and task.publish_date and task.publish_date > datetime.now() - timedelta(days=30):
#                 time_left = (task.publish_date + timedelta(days=30)) - datetime.now()
#                 logger.warning(
#                     f"⚠️ Задача с ID {task.id} была опубликована {task.publish_date}. Следующая публикация возможна через {time_left.days} дней и {time_left.seconds // 3600} часов.")
#                 await message.answer(
#                     f"⚠️ Задача с ID {task.id} была опубликована {task.publish_date}. Следующая публикация возможна через {time_left.days} дней и {time_left.seconds // 3600} часов.")
#                 continue
#
#             # Генерация изображения
#             image_url = await generate_image_if_needed(task)
#             if not image_url:
#                 logger.error(f"🚫 Ошибка при генерации изображения для задачи с ID {task.id}. Публикация прервана.")
#                 await message.answer(f"🚫 Ошибка при генерации изображения для задачи с ID {task.id}.")
#                 all_publications_successful = False
#                 failed_count += 1
#                 break
#
#             # Флаг для отслеживания успеха публикации перевода
#             task_translation_successful = True
#
#             # Публикуем каждый перевод задачи
#             for translation in task.translations:
#                 language = translation.language
#                 logger.info(f"🌐 Публикация перевода на языке: {language}")
#
#                 try:
#                     # Подготовка всех сообщений заранее
#                     image_message, text_message, poll_message, button_message = await prepare_publication(
#                         task=task,
#                         translation=translation,
#                         image_url=image_url
#                     )
#
#                     # Поиск группы для публикации
#                     result = await db_session.execute(
#                         select(Group)
#                         .where(Group.topic_id == task.topic_id)
#                         .where(Group.language == language)
#                     )
#                     group = result.scalar_one_or_none()
#
#                     if not group:
#                         logger.error(f"🚫 Группа для языка '{language}' и топика '{task.topic.name}' не найдена.")
#                         task_translation_successful = False
#                         failed_count += 1
#                         continue
#
#                     group_names.add(group.group_name)
#
#                     # Отправка 4 сообщений с полным контролем ошибок
#                     try:
#                         # 1. Отправка изображения
#                         response = requests.get(image_url)
#                         if response.status_code != 200:
#                             raise Exception(f"Не удалось загрузить изображение с URL {image_url}")
#
#                         photo = BufferedInputFile(response.content, filename="image.png")
#                         image_send = await bot.send_photo(
#                             chat_id=group.group_id,
#                             photo=photo,
#                             caption=image_message["caption"],
#                             parse_mode="MarkdownV2"
#                         )
#
#                         # 2. Отправка информации о задаче
#                         text_send = await bot.send_message(
#                             chat_id=group.group_id,
#                             text=text_message["text"],
#                             parse_mode=text_message.get("parse_mode", "MarkdownV2")
#                         )
#
#                         # 3. Отправка опроса
#                         poll_send = await bot.send_poll(
#                             chat_id=group.group_id,
#                             question=poll_message["question"],
#                             options=poll_message["options"],
#                             correct_option_id=poll_message["correct_option_id"],
#                             explanation=poll_message["explanation"],
#                             is_anonymous=True,
#                             type="quiz"
#                         )
#
#                         # 4. Отправка кнопки "Узнать больше"
#                         button_send = await bot.send_message(
#                             chat_id=group.group_id,
#                             text=button_message["text"],
#                             reply_markup=button_message["reply_markup"]
#                         )
#
#                         published_count += 1
#                         published_task_ids.append(task.id)
#
#                     except Exception as publish_error:
#                         logger.error(f"❌ Ошибка при публикации перевода на языке {language}: {str(publish_error)}")
#                         task_translation_successful = False
#
#                         # Удаление уже отправленных сообщений в случае ошибки
#                         try:
#                             if 'image_send' in locals() and image_send:
#                                 await bot.delete_message(chat_id=group.group_id, message_id=image_send.message_id)
#                             if 'text_send' in locals() and text_send:
#                                 await bot.delete_message(chat_id=group.group_id, message_id=text_send.message_id)
#                             if 'poll_send' in locals() and poll_send:
#                                 await bot.delete_message(chat_id=group.group_id, message_id=poll_send.message_id)
#                             if 'button_send' in locals() and button_send:
#                                 await bot.delete_message(chat_id=group.group_id, message_id=button_send.message_id)
#                         except Exception as delete_error:
#                             logger.error(f"Ошибка при удалении сообщений: {str(delete_error)}")
#
#                         failed_count += 1
#                         break
#
#                 except Exception as e:
#                     logger.error(f"❌ Критическая ошибка при публикации перевода на языке {language}: {str(e)}")
#                     task_translation_successful = False
#                     failed_count += 1
#                     break
#
#                 if not task_translation_successful:
#                     all_publications_successful = False
#                     break
#
#             # Прерываем публикацию всей группы, если что-то пошло не так
#             if not task_translation_successful:
#                 break
#
#         # Финальная обработка результатов
#         if all_publications_successful and published_count > 0:
#             await db_session.commit()
#             success_message = (
#                 f"✅ Задачи с ID: {', '.join(map(str, set(published_task_ids)))} успешно опубликованы!\n"
#                 f"🌍 Опубликовано переводов: {published_count} из {total_translations}\n"
#                 f"🏷️ Группы: {', '.join(group_names)}"
#             )
#             if failed_count > 0:
#                 success_message += f"\n⚠️ Не удалось опубликовать: {failed_count}"
#             logger.info(success_message)
#             await message.answer(success_message)
#         else:
#             await db_session.rollback()
#             failure_message = (
#                 f"❌ Публикация группы задач {translation_group_id} завершилась неудачно.\n"
#                 f"📜 Всего переводов: {total_translations}\n"
#                 f"⚠️ Не удалось опубликовать: {failed_count}"
#             )
#             logger.error(failure_message)
#             await message.answer(failure_message)
#
#         return all_publications_successful, published_count, failed_count, total_translations
#
#     except Exception as e:
#         logger.error(f"❌ Глобальная ошибка при публикации группы задач {translation_group_id}: {str(e)}")
#         await db_session.rollback()
#         await message.answer(f"❌ Глобальная ошибка при публикации группы задач: {str(e)}")
#         return False, published_count, failed_count, total_translations























# async def publish_task_by_translation_group(translation_group_id, message, db_session: AsyncSession, bot: Bot):
#     """
#     Публикует все переводы задач, принадлежащих к указанной группе переводов.
#
#     Args:
#         translation_group_id: ID группы переводов.
#         message: Объект сообщения для отправки ответов пользователю.
#         db_session (AsyncSession): Асинхронная сессия базы данных.
#         bot (Bot): Экземпляр бота для отправки сообщений.
#
#     Returns:
#         tuple: (success, published_count, failed_count, total_translations)
#     """
#     published_count = 0
#     failed_count = 0
#     total_translations = 0
#     published_task_ids = []  # Для хранения ID опубликованных задач
#     group_names = set()  # Для хранения имен групп
#
#     try:
#         logger.info(f"🚀 Начало публикации группы переводов с ID {translation_group_id}")
#
#         # Поиск всех задач с данным translation_group_id
#         result = await db_session.execute(
#             select(Task)
#             .options(
#                 joinedload(Task.translations),
#                 joinedload(Task.topic),
#                 joinedload(Task.subtopic)
#             )
#             .where(Task.translation_group_id == translation_group_id)
#         )
#
#         tasks = result.unique().scalars().all()
#         total_translations = len(tasks)
#
#         if total_translations == 0:
#             logger.warning(f"⚠️ Нет задач для публикации в группе переводов {translation_group_id}.")
#             await message.answer(f"⚠️ Нет задач для публикации в группе переводов {translation_group_id}.")
#             return False, published_count, failed_count, total_translations
#
#         logger.info(f"📚 Начало публикации группы переводов {translation_group_id}. Всего задач: {total_translations}")
#
#         # Проходим по всем задачам в группе
#         for task in tasks:
#             # Проверяем, была ли задача опубликована менее чем за последние 30 дней
#             if task.published and task.publish_date and task.publish_date > datetime.now() - timedelta(days=30):
#                 time_left = (task.publish_date + timedelta(days=30)) - datetime.now()
#                 logger.info(f"⚠️ Задача с ID {task.id} была опубликована {task.publish_date}. Следующая публикация возможна через {time_left.days} дней и {time_left.seconds // 3600} часов.")
#                 await message.answer(f"⚠️ Задача с ID {task.id} была опубликована {task.publish_date}. Следующая публикация возможна через {time_left.days} дней и {time_left.seconds // 3600} часов.")
#                 continue
#
#             # Генерация изображения
#             image_url = await generate_image_if_needed(task)
#             if not image_url:
#                 logger.error(f"🚫 Ошибка при генерации изображения для задачи с ID {task.id}. Публикация прервана.")
#                 await message.answer(f"🚫 Ошибка при генерации изображения для задачи с ID {task.id}.")
#                 failed_count += 1
#                 continue
#
#             # Публикуем каждый перевод задачи
#             for translation in task.translations:
#                 language = translation.language
#                 logger.info(f"🌐 Публикация перевода на языке: {language}")
#
#                 try:
#                     # Проверяем корректность данных перевода
#                     if not translation.question or not translation.answers or not translation.correct_answer:
#                         logger.error(f"⚠️ Некорректные данные перевода на языке: {language}. Пропуск перевода.")
#                         failed_count += 1
#                         continue
#
#                     # Вызов функции prepare_publication
#                     image_message, text_message, poll_message, button_message = await prepare_publication(
#                         task=task,
#                         translation=translation,
#                         image_url=image_url
#                     )
#
#                     # Ищем группу для публикации
#                     result = await db_session.execute(
#                         select(Group)
#                         .where(Group.topic_id == task.topic_id)
#                         .where(Group.language == language)
#                     )
#                     group = result.scalar_one_or_none()
#
#                     if not group:
#                         logger.error(f"🚫 Группа для языка '{language}' и топика '{task.topic.name}' не найдена.")
#                         failed_count += 1
#                         continue
#
#                     group_names.add(group.group_name)
#
#                     # Подготовка и отправка сообщения с изображением
#                     try:
#                         # Загрузка изображения
#                         response = requests.get(image_url)
#                         if response.status_code == 200:
#                             # Создаем BufferedInputFile вместо InputFile
#                             photo = BufferedInputFile(
#                                 response.content,
#                                 filename="image.png"
#                             )
#                             try:
#                                 await bot.send_photo(
#                                     chat_id=group.group_id,
#                                     photo=photo,
#                                     caption=image_message["caption"],
#                                     parse_mode="MarkdownV2"
#                                 )
#                                 logger.info(
#                                     f"📷 Сообщение с изображением отправлено в группу '{group.group_name}' (язык: {translation.language}).")
#                             except Exception as e:
#                                 logger.error(f"❌ Ошибка при отправке изображения: {str(e)}")
#                                 await message.answer(f"❌ Ошибка при отправке изображения: {str(e)}")
#                         else:
#                             logger.error(f"❌ Ошибка: не удалось загрузить изображение с URL {image_url}")
#                     except Exception as e:
#                         logger.error(f"❌ Ошибка при отправке изображения: {e}")
#                         await message.answer(f"❌ Ошибка при отправке изображения: {e}")
#                         failed_count += 1
#
#                     # Отправка информации о задаче
#                     await bot.send_message(
#                         chat_id=group.group_id,
#                         text=text_message["text"],
#                         parse_mode=text_message.get("parse_mode", "MarkdownV2")
#                     )
#                     logger.info(f"📋 Тема, подтема и сложность задачи отправлены в группу '{group.group_name}'.")
#
#                     # Отправка опроса с типом "quiz"
#                     await bot.send_poll(
#                         chat_id=group.group_id,
#                         question=poll_message["question"],
#                         options=poll_message["options"],
#                         correct_option_id=poll_message["correct_option_id"],
#                         explanation=poll_message["explanation"],
#                         is_anonymous=True,
#                         type="quiz"
#                     )
#                     logger.info(f"📊 Опрос успешно опубликован в группу '{group.group_name}' (язык: {translation.language}).")
#
#                     # Отправка кнопки "Узнать больше"
#                     await bot.send_message(
#                         chat_id=group.group_id,
#                         text=button_message["text"],
#                         reply_markup=button_message["reply_markup"]
#                     )
#                     logger.info(f"🔗 Кнопка 'Узнать больше' отправлена в группу '{group.group_name}' (язык: {translation.language}).")
#
#                     # Пометка о публикации перевода
#                     published_count += 1
#                     task.published = True
#                     task.publish_date = datetime.now()
#                     published_task_ids.append(task.id)
#                     logger.info(f"✅ Успешно опубликован перевод на языке: {language}")
#
#                 except Exception as e:
#                     failed_count += 1
#                     logger.error(f"❌ Ошибка при публикации перевода на языке {language}: {str(e)}")
#
#         # После успешной публикации всех задач обновляем статус
#         if published_count > 0:
#             await db_session.commit()
#             success_message = (
#                 f"✅ Задачи с ID: {', '.join(map(str, set(published_task_ids)))} успешно опубликованы!\n"
#                 f"🌍 Опубликовано переводов: {published_count} из {total_translations}\n"
#                 f"🏷️ Группы: {', '.join(group_names)}"
#             )
#             if failed_count > 0:
#                 success_message += f"\n⚠️ Не удалось опубликовать: {failed_count}"
#             logger.info(success_message)
#             await message.answer(success_message)
#         else:
#             await db_session.rollback()
#             failure_message = (
#                 f"❌ Публикация группы задач {translation_group_id} завершилась неудачно.\n"
#                 f"📜 Всего переводов: {total_translations}\n"
#                 f"⚠️ Не удалось опубликовать: {failed_count}"
#             )
#             logger.error(failure_message)
#             await message.answer(failure_message)
#
#         return True, published_count, failed_count, total_translations
#
#     except Exception as e:
#         logger.error(f"❌ Ошибка при публикации группы задач {translation_group_id}: {str(e)}")
#         await db_session.rollback()
#         await message.answer(f"❌ Ошибка при публикации группы задач: {str(e)}")
#         return False, published_count, failed_count, total_translations




