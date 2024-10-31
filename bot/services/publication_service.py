import io
import logging
import random
from datetime import datetime, timedelta
from io import BytesIO

import requests
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile, BufferedInputFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.services.task_service import prepare_publication
from database.models import Task, Group, TaskTranslation
from bot.services.image_service import generate_image_if_needed




logger = logging.getLogger(__name__)







async def publish_task_by_id(task_id: int, message, db_session: AsyncSession, bot: Bot):
    """
    Публикует все переводы задачи по её ID и translation_group_id, если задача не была опубликована
    или прошел месяц с последней публикации.
    """
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

        logger.info(f"✅ Задача с ID {task_id} успешно найдена. Статус публикации: {'опубликована' if task.published else 'не опубликована'}")

        # Проверяем, была ли задача уже опубликована и прошло ли 30 дней с последней публикации
        if task.published:
            if task.publish_date and task.publish_date > datetime.now() - timedelta(days=30):
                time_left = (task.publish_date + timedelta(days=30)) - datetime.now()
                logger.info(f"⚠️ Задача с ID {task_id} была опубликована {task.publish_date.strftime('%Y-%m-%d %H:%M:%S')}. Публикация доступна через {time_left.days} дней и {time_left.seconds // 3600} часов.")
                await message.answer(
                    f"⚠️ Задача с ID {task_id} уже опубликована {task.publish_date.strftime('%Y-%m-%d %H:%M:%S')}.\n"
                    f"Следующая публикация доступна через {time_left.days} дней и {time_left.seconds // 3600} часов."
                )
                return False

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

        if not tasks_in_group:
            logger.warning(f"⚠️ Нет задач для публикации с translation_group_id {task.translation_group_id}.")
            await message.answer(f"⚠️ Нет задач для публикации с translation_group_id {task.translation_group_id}.")
            return False

        logger.info(f"📚 Начало публикации группы переводов с ID {task.translation_group_id}. Всего задач: {len(tasks_in_group)}")

        # Переменные для статистики
        total_translations = 0
        published_count = 0
        failed_count = 0
        published_languages = []
        published_task_ids = []  # Для хранения ID опубликованных задач
        group_names = set()

        # Публикуем переводы всех задач в группе
        for task_in_group in tasks_in_group:
            for translation in task_in_group.translations:
                total_translations += 1
                try:
                    logger.info(f"🌍 Публикация перевода на языке {translation.language}")

                    # Генерация изображения для каждого перевода
                    image_url = await generate_image_if_needed(task_in_group)
                    if not image_url:
                        logger.error(f"Ошибка при генерации изображения для задачи с ID {task_in_group.id}")
                        await message.answer(f"Ошибка при генерации изображения для задачи с ID {task_in_group.id}")
                        failed_count += 1
                        continue

                    # Подготовка данных для публикации
                    image_message, text_message, poll_message, button_message = await prepare_publication(
                        task=task_in_group,
                        translation=translation,
                        image_url=image_url
                    )

                    # Ищем группу для публикации
                    result = await db_session.execute(
                        select(Group)
                        .where(Group.topic_id == task_in_group.topic_id)
                        .where(Group.language == translation.language)
                    )
                    group = result.scalar_one_or_none()

                    if not group:
                        logger.error(f"🚫 Группа для языка '{translation.language}' и топика '{task_in_group.topic.name}' не найдена.")
                        failed_count += 1
                        continue

                    # Добавляем название группы в список
                    group_names.add(group.group_name)

                    # Публикация в Telegram
                    # 1. Отправляем изображение
                    await bot.send_photo(
                        chat_id=group.group_id,
                        photo=image_message["photo"],
                        caption=image_message["caption"],
                        parse_mode="MarkdownV2"
                    )
                    logger.info(f"📷 Сообщение с изображением отправлено в группу '{group.group_name}' (язык: {translation.language}).")

                    # 2. Отправляем информацию о задаче
                    await bot.send_message(
                        chat_id=group.group_id,
                        text=text_message["text"],
                        parse_mode=text_message.get("parse_mode", "MarkdownV2")
                    )
                    logger.info(f"📋 Тема, подтема и сложность задачи отправлены в группу '{group.group_name}'.")

                    # 3. Отправляем опрос
                    await bot.send_poll(
                        chat_id=group.group_id,
                        question=poll_message["question"],
                        options=poll_message["options"],
                        correct_option_id=poll_message["correct_option_id"],
                        explanation=poll_message["explanation"],
                        is_anonymous=True,
                        type="quiz"
                    )
                    logger.info(f"📊 Опрос успешно опубликован в группу '{group.group_name}' (язык: {translation.language}).")

                    # 4. Отправляем кнопку "Узнать больше"
                    await bot.send_message(
                        chat_id=group.group_id,
                        text=button_message["text"],
                        reply_markup=button_message["reply_markup"]
                    )
                    logger.info(f"🔗 Кнопка 'Узнать больше' отправлена в группу '{group.group_name}' (язык: {translation.language}).")

                    # Отмечаем перевод как опубликованный
                    translation.published = True
                    translation.publish_date = datetime.now()
                    published_languages.append(translation.language)
                    published_task_ids.append(task_in_group.id)  # Добавляем ID задачи в список опубликованных
                    published_count += 1

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Ошибка при публикации перевода на языке {translation.language}: {str(e)}")

        # Обновляем статус всех задач в группе
        if published_count > 0:
            for task_in_group in tasks_in_group:
                task_in_group.published = True
                task_in_group.publish_date = datetime.now()
            await db_session.commit()
            success_message = (
                f"✅ Задачи с ID: {', '.join(map(str, set(published_task_ids)))} успешно опубликованы!\n"
                f"🌍 Опубликовано переводов: {published_count} из {total_translations}\n"
                f"📜 Языки: {', '.join(published_languages)}\n"
                f"🏷️ Группы: {', '.join(group_names)}"
            )
            if failed_count > 0:
                success_message += f"\n⚠️ Не удалось опубликовать: {failed_count}"
            logger.info(success_message)
            await message.answer(success_message)
        else:
            await db_session.rollback()
            failure_message = (
                f"❌ Публикация группы задач {task.translation_group_id} завершилась неудачно.\n"
                f"📜 Всего переводов: {total_translations}\n"
                f"⚠️ Не удалось опубликовать: {failed_count}"
            )
            logger.error(failure_message)
            await message.answer(failure_message)

        return published_count > 0

    except Exception as e:
        logger.error(f"⚠️ Ошибка при публикации группы задач с ID {task_id}: {str(e)}")
        await db_session.rollback()
        await message.answer(f"⚠️ Ошибка при публикации группы задач с ID {task_id}: {str(e)}")
        return False






async def publish_translation(translation: TaskTranslation, bot: Bot, db_session: AsyncSession):
    """
    Публикует перевод задачи в соответствующую группу на основе языка и топика.

    Args:
        translation (TaskTranslation): Объект перевода задачи.
        bot (Bot): Экземпляр бота для отправки сообщений.
        db_session (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        bool: True, если публикация успешна, False в противном случае.
    """
    try:
        # Генерация уникального изображения для перевода
        image_url = await generate_image_if_needed(translation)

        # Вызов функции для подготовки публикации
        image_message, text_message, poll_message, button_message = await prepare_publication(
            task=translation.task,
            translation=translation,
            image_url=image_url
        )

        # Ищем группу для публикации
        result = await db_session.execute(
            select(Group)
            .where(Group.topic_id == translation.task.topic_id)
            .where(Group.language == translation.language)
        )
        group = result.scalar_one_or_none()

        if not group:
            logger.error(f"🚫 Группа для языка '{translation.language}' и топика '{translation.task.topic.name}' не найдена.")
            return False

        # 1. Отправляем изображение
        await bot.send_photo(
            chat_id=group.group_id,
            photo=image_message["photo"],
            caption=image_message["caption"],
            parse_mode="MarkdownV2"
        )
        logger.info(f"📷 Сообщение с изображением отправлено в группу '{group.group_name}' (язык: {translation.language}).")

        # 2. Отправляем информацию о задаче (topic, subtopic, difficulty)
        await bot.send_message(
            chat_id=group.group_id,
            text=text_message["text"],
            parse_mode=text_message.get("parse_mode", "MarkdownV2")
        )
        logger.info(f"📋 Тема, подтема и сложность задачи отправлены в группу '{group.group_name}'.")

        # 3. Отправляем опрос с типом "quiz"
        await bot.send_poll(
            chat_id=group.group_id,
            question=poll_message["question"],
            options=poll_message["options"],
            correct_option_id=poll_message["correct_option_id"],
            explanation=poll_message["explanation"],
            is_anonymous=True,
            type="quiz"  # Явно указываем, что это опрос-викторина
        )
        logger.info(f"📊 Опрос успешно опубликован в группе '{group.group_name}' (язык: {translation.language}).")

        # 4. Отправляем кнопку "Узнать больше"
        await bot.send_message(
            chat_id=group.group_id,
            text=button_message["text"],
            reply_markup=button_message["reply_markup"]
        )
        logger.info(f"🔗 Кнопка 'Узнать больше' отправлена в группу '{group.group_name}' (язык: {translation.language}).")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при публикации перевода на языке {translation.language}: {str(e)}")
        return False




























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




