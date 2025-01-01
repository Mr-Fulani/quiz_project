# bot/services/publication_service.py

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Tuple
from uuid import UUID

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.config import S3_BUCKET_NAME, S3_REGION
from bot.database.models import Task, Group, TaskTranslation, TaskPoll
from bot.handlers.webhook_handler import get_incorrect_answers
from bot.services.default_link_service import DefaultLinkService
from bot.services.deletion_service import delete_from_s3
from bot.services.image_service import generate_image_if_needed
from bot.services.task_service import prepare_publication
from bot.services.webhook_service import WebhookService
from bot.utils.logging_utils import log_final_summary, log_webhook_summary, log_pause, \
    log_username_received, log_publication_start, log_publication_failure, log_webhook_data, log_publication_success
from bot.utils.webhook_utils import create_webhook_data

logger = logging.getLogger(__name__)






async def publish_task_by_id(task_id: int, message, db_session: AsyncSession, bot: Bot, user_chat_id: int) -> bool:
    """
    Публикует все переводы задачи по её ID и translation_group_id.
    Отправляет вебхуки на все активные URL вебхуков после публикации.
    Обновляет поле error при возникновении ошибок.
    """
    webhook_data_list = []  # Список для хранения данных вебхуков
    failed_publications = []  # Список для хранения неудачных публикаций
    uploaded_images = []  # Список для хранения URL загруженных изображений (для отката)

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
                joinedload(Task.subtopic),
                joinedload(Task.group)  # Добавлено для получения group_name
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
                joinedload(Task.subtopic),
                joinedload(Task.group)
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

            # Генерируем (или пытаемся получить) картинку
            image_url = await generate_image_if_needed(task_in_group, user_chat_id)
            if not image_url:
                logger.error(f"Ошибка при генерации изображения для задачи с ID {task_in_group.id}")
                failed_count += len(task_in_group.translations)
                # Добавляем ошибки для каждого перевода этой задачи
                for tr in task_in_group.translations:
                    failed_publications.append({
                        "task_id": task_in_group.id,
                        "translation_id": tr.id,
                        "language": tr.language,
                        "error": "Ошибка при генерации изображения"
                    })
                # Помечаем задачу как с ошибкой
                task_in_group.error = True
                await db_session.commit()
                continue
            else:
                uploaded_images.append(image_url)  # Добавляем в список для отката

            for translation in task_in_group.translations:
                total_translations += 1
                try:
                    # Логирование начала публикации
                    publication_start_msg = log_publication_start(
                        task_id=task_in_group.id,
                        translation_id=translation.id,
                        language=translation.language,
                        target=f"канал '{task_in_group.group.group_name}'"
                    )
                    await message.answer(publication_start_msg)

                    # Подготовка публикации
                    image_message, text_message, poll_message, button_message, external_link, dont_know_option = await prepare_publication(
                        task=task_in_group,
                        translation=translation,
                        image_url=image_url,
                        db_session=db_session,
                        default_link_service=default_link_service,
                        user_chat_id=user_chat_id
                    )

                    # Поиск группы для публикации (уже загружена через joinedload)
                    group = task_in_group.group

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

                    # Публикация контента
                    await bot.send_photo(
                        chat_id=group.group_id,
                        photo=image_message["photo"],
                        parse_mode="MarkdownV2"
                    )

                    await bot.send_message(
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

                    await bot.send_message(
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
                        failed_publications.append({
                            "task_id": task_in_group.id,
                            "translation_id": translation.id,
                            "language": translation.language,
                            "error": "Username канала не найден"
                        })
                        # Помечаем задачу как с ошибкой
                        task_in_group.error = True
                        await db_session.commit()
                        continue

                    # Формирование данных для вебхука
                    webhook_data, poll_link = await create_webhook_data(
                        task_id=task.id,  # ID задачи
                        channel_username=channel_username,
                        poll_msg=poll_msg,
                        image_url=image_url,
                        poll_message=poll_message,
                        translation=translation,
                        group=group,
                        image_message=image_message,
                        dont_know_option=dont_know_option,
                        external_link=external_link
                    )

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
                results = await webhook_service.send_webhooks(
                    webhooks_data=webhook_data_list,
                    webhooks=active_webhooks,
                    bot=bot,
                    admin_chat_id=user_chat_id  # Передача ID чата администратора
                )

                # Подсчёт результатов
                success_count = sum(1 for r in results if r)
                failed_count += len(results) - success_count
                summary_msg = log_webhook_summary(success=success_count, failed=failed_count)
                await message.answer(summary_msg)
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке вебхуков: {str(e)}")
                await message.answer(f"❌ Ошибка при отправке вебхуков: {str(e)}")

        # Обновление статуса задач
        if published_count > 0:
            try:
                for task_in_group in tasks_in_group:
                    if task_in_group.id in published_task_ids:
                        task_in_group.published = True
                        task_in_group.publish_date = datetime.now()
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

                # Откат: удаление загруженных изображений из S3
                for s3_url in uploaded_images:
                    try:
                        s3_key = s3_url.split(f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/")[-1]
                        await delete_from_s3(s3_key)
                        logger.info(f"🗑️ Изображение удалено из S3: {s3_key}")
                    except Exception as del_e:
                        logger.error(f"❌ Не удалось удалить изображение из S3 по URL {s3_url}: {del_e}")

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
                await message.answer(f"❌ Ошибка при откате транзакции: {e}")
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
    Обновляет поле error при возникновении ошибок.
    """
    webhook_data_list = []
    uploaded_images = []  # Список для хранения URL загруженных изображений (для отката)
    failed_publications = []

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
            # Помечаем задачу как с ошибкой
            translation.task.error = True
            await db_session.commit()
            return False
        else:
            uploaded_images.append(image_url)  # Добавляем в список для отката

        # Подготовка данных для публикации
        image_message, text_message, poll_message, button_message, external_link, dont_know_option = await prepare_publication(
            task=translation.task,
            translation=translation,
            image_url=image_url,
            db_session=db_session,
            default_link_service=default_link_service,
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
            failed_publications.append({
                "task_id": translation.task.id,
                "translation_id": translation.id,
                "language": translation.language,
                "error": "Группа не найдена"
            })
            # Помечаем задачу как с ошибкой
            translation.task.error = True
            await db_session.commit()
            return False

        # Публикация контента
        try:
            await bot.send_photo(
                chat_id=group.group_id,
                photo=image_message["photo"],
                parse_mode="MarkdownV2"
            )
            logger.info(f"✅ Фото отправлено на канал '{group.group_name}'.")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке фото: {e}")
            failed_publications.append({
                "task_id": translation.task.id,
                "translation_id": translation.id,
                "language": translation.language,
                "error": f"Ошибка при отправке фото: {e}"
            })
            # Помечаем задачу как с ошибкой
            translation.task.error = True
            await db_session.commit()
            return False

        try:
            await bot.send_message(
                chat_id=group.group_id,
                text=text_message["text"],
                parse_mode=text_message.get("parse_mode", "MarkdownV2")
            )
            logger.info(f"✅ Текст отправлен на канал '{group.group_name}'.")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке текста: {e}")
            failed_publications.append({
                "task_id": translation.task.id,
                "translation_id": translation.id,
                "language": translation.language,
                "error": f"Ошибка при отправке текста: {e}"
            })
            # Помечаем задачу как с ошибкой
            translation.task.error = True
            await db_session.commit()
            return False

        try:
            poll_msg = await bot.send_poll(
                chat_id=group.group_id,
                question=poll_message["question"],
                options=poll_message["options"],
                correct_option_id=poll_message["correct_option_id"],
                explanation=poll_message["explanation"],
                is_anonymous=True,
                type="quiz"
            )
            logger.info(f"✅ Опрос отправлен на канал '{group.group_name}'.")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке опроса: {e}")
            failed_publications.append({
                "task_id": translation.task.id,
                "translation_id": translation.id,
                "language": translation.language,
                "error": f"Ошибка при отправке опроса: {e}"
            })
            # Помечаем задачу как с ошибкой
            translation.task.error = True
            await db_session.commit()
            return False

        try:
            await bot.send_message(
                chat_id=group.group_id,
                text=button_message["text"],
                reply_markup=button_message["reply_markup"]
            )
            logger.info(f"✅ Кнопка отправлена на канал '{group.group_name}'.")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке кнопки: {e}")
            failed_publications.append({
                "task_id": translation.task.id,
                "translation_id": translation.id,
                "language": translation.language,
                "error": f"Ошибка при отправке кнопки: {e}"
            })
            # Помечаем задачу как с ошибкой
            translation.task.error = True
            await db_session.commit()
            return False

        # Получение username канала
        try:
            chat = await bot.get_chat(group.group_id)
            channel_username = chat.username
            if not channel_username:
                raise ValueError(f"Username канала не найден для группы {group.group_name}")
            logger.info(f"✅ Username канала '{group.group_name}' получен: @{channel_username}")
        except Exception as e:
            logger.error(f"❌ Ошибка при получении информации о канале: {e}")
            failed_publications.append({
                "task_id": translation.task.id,
                "translation_id": translation.id,
                "language": translation.language,
                "error": f"Ошибка при получении username канала: {e}"
            })
            # Помечаем задачу как с ошибкой
            translation.task.error = True
            await db_session.commit()
            return False

        # Формирование данных для вебхука
        if webhook_data_list and active_webhooks:
            logger.info(f"📤 Отправка вебхуков для перевода {translation.id}")
            try:
                results = await webhook_service.send_webhooks(
                    webhook_data_list,
                    active_webhooks,
                    bot,
                    user_chat_id  # передаем как admin_chat_id
                )
                success_count = sum(1 for r in results if r)
                failed_count = len(results) - success_count
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке вебхуков: {str(e)}")
                # Помечаем задачу как с ошибкой
                translation.task.error = True
                await db_session.commit()
                return False

        # Лог о публикации перевода
        logger.info(
            f"✅ Публикован перевод задачи (ID задачи: {translation.task_id}, Перевод ID: {translation.id}) на канал '{group.group_name}' "
            f"({translation.language})."
        )

        # Отправка вебхуков
        if webhook_data_list and active_webhooks:
            logger.info(f"📤 Отправка вебхуков для перевода {translation.id}")
            try:
                results = await webhook_service.send_webhooks(
                    webhook_data_list,
                    active_webhooks,
                    bot,
                    user_chat_id  # Передача ID чата администратора
                )
                success_count = sum(1 for r in results if r)
                failed_count = len(results) - success_count
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке вебхуков: {str(e)}")
                # Помечаем задачу как с ошибкой
                translation.task.error = True
                await db_session.commit()
                return False

        # Обновление статуса перевода
        try:
            translation.published = True
            translation.publish_date = datetime.now()
            await db_session.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении статуса перевода {translation.id}: {e}")
            await db_session.rollback()

            # Откат: удаление загруженных изображений из S3
            for s3_url in uploaded_images:
                try:
                    s3_key = s3_url.split(f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/")[-1]
                    await delete_from_s3(s3_key)
                    logger.info(f"🗑️ Изображение удалено из S3: {s3_key}")
                except Exception as del_e:
                    logger.error(f"❌ Не удалось удалить изображение из S3 по URL {s3_url}: {del_e}")

            # Помечаем задачу как с ошибкой
            translation.task.error = True
            await db_session.commit()
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка при публикации перевода {translation.id}: {str(e)}")
        await db_session.rollback()
        return False












async def publish_task_by_translation_group(
    translation_group_id: UUID,
    message,
    db_session: AsyncSession,
    bot: Bot,
    admin_chat_id: int  # ID чата администратора
) -> Tuple[bool, int, int, int]:
    """
    Публикует все переводы задач в группе переводов.
    Отправляет вебхуки на все активные URL вебхуков после публикации.
    Обновляет поле error при возникновении ошибок.
    Пропускает группы, содержащие задачи с error=True.

    :param translation_group_id: UUID группы переводов.
    :param message: Объект сообщения для отправки ответов пользователю.
    :param db_session: Асинхронная сессия базы данных.
    :param bot: Экземпляр бота Aiogram.
    :param admin_chat_id: ID чата администратора для отправки уведомлений.
    :return: Кортеж с результатами публикации (успех, опубликовано, неудачно, всего).
    """
    webhook_data_list = []
    published_count = 0
    failed_count = 0
    total_translations = 0
    published_task_ids = []
    published_languages = set()
    published_group_names = set()
    failed_publications = []
    uploaded_images = []  # Список для хранения URL загруженных изображений (для отката)

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
            await message.answer(f"⚠️ Нет задач для публикации в группе переводов `{translation_group_id}`.")
            return False, 0, 0, 0

        # Проверка, содержит ли группа задачи с ошибками
        error_tasks = [task for task in tasks if task.error]
        if error_tasks:
            error_details = "\n".join([
                f"• Задача ID: `{task.id}`\n"
                f"  Группа: `{task.topic.name if task.topic else 'Не указана'}`"
                for task in error_tasks
            ])

            error_message = (
                f"⚠️ Группа переводов `{translation_group_id}` содержит задачи с ошибками:\n\n"
                f"{error_details}\n\n"
                f"Всего задач с ошибками: {len(error_tasks)}\n"
                f"❌ Публикация пропущена."
            )

            logger.warning(error_message)
            await message.answer(error_message)
            return False, 0, 0, 0

        total_translations = sum(len(task.translations) for task in tasks)
        logger.info(f"📚 Найдено задач для публикации: {total_translations} в группе переводов {translation_group_id}")
        await message.answer(f"📚 Найдено задач для публикации: {total_translations}.")

        # Получение списка активных вебхуков
        webhook_service = WebhookService(db_session)
        active_webhooks = await webhook_service.get_active_webhooks()
        logger.info(f"📥 Список активных вебхуков: {[wh.url for wh in active_webhooks]}")
        if not active_webhooks:
            logger.warning("⚠️ Нет активных вебхуков для отправки.")
            await message.answer("⚠️ Нет активных вебхуков для отправки.")

        # Инициализация DefaultLinkService
        default_link_service = DefaultLinkService(db_session)

        for task in tasks:
            # Проверка предыдущей публикации
            if task.published and task.publish_date:
                one_month_ago = datetime.now() - timedelta(days=30)
                if task.publish_date > one_month_ago:
                    logger.info(f"⚠️ Задача с ID {task.id} была опубликована {task.publish_date}. Пропуск.")
                    await message.answer(
                        f"⚠️ Задача с ID `{task.id}` была опубликована {task.publish_date.strftime('%Y-%m-%d %H:%M:%S')}. Пропуск."
                    )
                    continue

            # Генерация изображения один раз для задачи
            image_url = await generate_image_if_needed(task, admin_chat_id)
            if not image_url:
                error_message = f"🚫 Ошибка генерации изображения для задачи {task.id}"
                logger.error(f"❌ {error_message}")
                await message.answer(error_message)
                failed_count += len(task.translations)
                # Запишем ошибку для каждого перевода этой задачи
                for tr in task.translations:
                    failed_publications.append({
                        "task_id": task.id,
                        "translation_id": tr.id,
                        "language": tr.language,
                        "error": "Ошибка генерации изображения"
                    })
                # Помечаем задачу как с ошибкой
                task.error = True
                await db_session.commit()
                continue
            else:
                uploaded_images.append(image_url)  # Добавляем в список для отката

            for translation in task.translations:
                try:
                    # Вместо ручных сообщений используем log_publication_start
                    publication_start_msg = log_publication_start(
                        task_id=task.id,
                        translation_id=translation.id,
                        language=translation.language,
                        target=f"группу (канал) этой задачи"
                    )
                    await message.answer(publication_start_msg)

                    # Подготовка публикации
                    image_message, text_message, poll_message, button_message, external_link, dont_know_option = await prepare_publication(
                        task=task,
                        translation=translation,
                        image_url=image_url,
                        db_session=db_session,
                        default_link_service=default_link_service,
                        user_chat_id=admin_chat_id
                    )

                    # Поиск группы для публикации
                    group_result = await db_session.execute(
                        select(Group)
                        .where(Group.topic_id == task.topic_id)
                        .where(Group.language == translation.language)
                    )
                    group = group_result.scalar_one_or_none()

                    if not group:
                        error_msg = f"🚫 Группа не найдена для языка {translation.language}"
                        logger.error(f"❌ {error_msg}")
                        await message.answer(f"🚫 Группа не найдена для языка `{translation.language}`.")
                        failed_count += 1
                        failed_publications.append({
                            "task_id": task.id,
                            "translation_id": translation.id,
                            "language": translation.language,
                            "error": "Группа не найдена"
                        })
                        # Помечаем задачу как с ошибкой
                        task.error = True
                        await db_session.commit()
                        continue

                    target = f"канал '{group.group_name}'"

                    # Логирование начала публикации
                    log_publication_start(task.id, translation.id, translation.language, target)

                    # Публикация контента
                    try:
                        await bot.send_photo(
                            chat_id=group.group_id,
                            photo=image_message["photo"],
                            parse_mode="MarkdownV2"
                        )
                        logger.info(f"✅ Фото отправлено на канал '{group.group_name}'.")
                    except Exception as e:
                        log_publication_failure(task.id, translation.id, translation.language, target, e)
                        await message.answer(f"❌ Ошибка при отправке фото: {e}")
                        failed_count += 1
                        failed_publications.append({
                            "task_id": task.id,
                            "translation_id": translation.id,
                            "language": translation.language,
                            "error": f"Ошибка при отправке фото: {e}"
                        })
                        # Помечаем задачу как с ошибкой
                        task.error = True
                        await db_session.commit()
                        continue

                    try:
                        await bot.send_message(
                            chat_id=group.group_id,
                            text=text_message["text"],
                            parse_mode=text_message.get("parse_mode", "MarkdownV2")
                        )
                        logger.info(f"✅ Текст отправлен на канал '{group.group_name}'.")
                    except Exception as e:
                        log_publication_failure(task.id, translation.id, translation.language, target, e)
                        await message.answer(f"❌ Ошибка при отправке текста: {e}")
                        failed_count += 1
                        failed_publications.append({
                            "task_id": task.id,
                            "translation_id": translation.id,
                            "language": translation.language,
                            "error": f"Ошибка при отправке текста: {e}"
                        })
                        # Помечаем задачу как с ошибкой
                        task.error = True
                        await db_session.commit()
                        continue

                    try:
                        poll_msg = await bot.send_poll(
                            chat_id=group.group_id,
                            question=poll_message["question"],
                            options=poll_message["options"],
                            correct_option_id=poll_message["correct_option_id"],
                            explanation=poll_message["explanation"],
                            is_anonymous=True,
                            type="quiz"
                        )
                        logger.info(f"✅ Опрос отправлен на канал '{group.group_name}'.")
                    except Exception as e:
                        log_publication_failure(task.id, translation.id, translation.language, target, e)
                        await message.answer(f"❌ Ошибка при отправке опроса: {e}")
                        failed_count += 1
                        failed_publications.append({
                            "task_id": task.id,
                            "translation_id": translation.id,
                            "language": translation.language,
                            "error": f"Ошибка при отправке опроса: {e}"
                        })
                        # Помечаем задачу как с ошибкой
                        task.error = True
                        await db_session.commit()
                        continue

                    try:
                        await bot.send_message(
                            chat_id=group.group_id,
                            text=button_message["text"],
                            reply_markup=button_message["reply_markup"]
                        )
                        logger.info(f"✅ Кнопка отправлена на канал '{group.group_name}'.")
                    except Exception as e:
                        log_publication_failure(task.id, translation.id, translation.language, target, e)
                        await message.answer(f"❌ Ошибка при отправке кнопки: {e}")
                        failed_count += 1
                        failed_publications.append({
                            "task_id": task.id,
                            "translation_id": translation.id,
                            "language": translation.language,
                            "error": f"Ошибка при отправке кнопки: {e}"
                        })
                        # Помечаем задачу как с ошибкой
                        task.error = True
                        await db_session.commit()
                        continue

                    # Получение username канала
                    try:
                        chat = await bot.get_chat(group.group_id)
                        channel_username = chat.username
                        if not channel_username:
                            raise ValueError(f"Username канала не найден для группы {group.group_name}")
                        logger.info(f"✅ Username канала '{group.group_name}' получен: @{channel_username}")
                        await message.answer(f"✅ Username канала `{group.group_name}` получен: @{channel_username}")
                    except Exception as e:
                        log_publication_failure(task.id, translation.id, translation.language, target, e)
                        await message.answer(f"❌ Ошибка при получении информации о канале: {e}")
                        failed_count += 1
                        failed_publications.append({
                            "task_id": task.id,
                            "translation_id": translation.id,
                            "language": translation.language,
                            "error": f"Ошибка при получении username канала: {e}"
                        })
                        # Помечаем задачу как с ошибкой
                        task.error = True
                        await db_session.commit()
                        continue

                    # Формирование данных для вебхука
                    webhook_data, poll_link = await create_webhook_data(
                        task_id=task.id,  # ID задачи
                        channel_username=channel_username,
                        poll_msg=poll_msg,
                        image_url=image_url,
                        poll_message=poll_message,
                        translation=translation,
                        group=group,
                        image_message=image_message,
                        dont_know_option=dont_know_option,
                        external_link=external_link
                    )

                    log_webhook_data(webhook_data)
                    webhook_data_list.append(webhook_data)

                    # Обновление статуса перевода
                    translation.published = True
                    translation.publish_date = datetime.now()
                    published_languages.add(translation.language)
                    published_task_ids.append(task.id)
                    published_group_names.add(group.group_name)
                    published_count += 1

                    # Лог о публикации
                    log_publication_success(task.id, translation.id, translation.language, target)

                    # Добавляем паузу между публикациями переводов
                    sleep_time = random.randint(3, 6)
                    log_pause(sleep_time, task.id, translation.language, group.group_name)
                    await message.answer(
                        f"⏸️ Пауза {sleep_time} секунд перед следующей публикацией "
                        f"(Задача ID `{task.id}`, Язык: `{translation.language}`, Канал: `{group.group_name}`)."
                    )
                    await asyncio.sleep(sleep_time)
                except Exception as e:
                    failed_count += 1
                    log_publication_failure(task.id, translation.id, translation.language, target, e)
                    # Помечаем задачу как с ошибкой
                    task.error = True
                    await db_session.commit()
                    continue

    except Exception as e:
        error_msg = f"❌ Ошибка при публикации группы переводов `{translation_group_id}`: {str(e)}"
        logger.exception(error_msg)
        await db_session.rollback()

        # Откат: удаление загруженных изображений из S3
        for s3_url in uploaded_images:
            try:
                s3_key = s3_url.split(f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/")[-1]
                await delete_from_s3(s3_key)
                logger.info(f"🗑️ Изображение удалено из S3: {s3_key}")
            except Exception as del_e:
                logger.error(f"❌ Не удалось удалить изображение из S3 по URL {s3_url}: {del_e}")

        await message.answer(error_msg)
        return False, published_count, failed_count, total_translations

    # Отправка вебхуков после публикации всех переводов
    try:
        if webhook_data_list and active_webhooks:
            logger.info(f"📤 Отправка вебхуков на {len(active_webhooks)} сервисов.")
            await message.answer(f"📤 Отправка вебхуков на {len(active_webhooks)} сервисов.")

            log_webhook_data(webhook_data_list)
            logger.debug(f"📥 Активные вебхуки: {[wh.url for wh in active_webhooks]}")

            # Вызов функции отправки вебхуков с передачей admin_chat_id
            results = await webhook_service.send_webhooks(
                webhook_data_list,
                active_webhooks,
                bot,
                admin_chat_id  # Передача ID чата администратора
            )
            success_count = sum(1 for r in results if r)
            failed_webhooks = len(results) - success_count
            logger.info(
                f"📊 Результаты отправки вебхуков: успешно - {success_count}, неудачно - {failed_webhooks}"
            )
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке вебхуков: {str(e)}")
        await message.answer(f"❌ Ошибка при отправке вебхуков: {str(e)}")

    # Обновление статуса задач
    if published_count > 0:
        try:
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
        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении статуса задач: {e}")
            await db_session.rollback()

            # Откат: удаление загруженных изображений из S3
            for s3_url in uploaded_images:
                try:
                    s3_key = s3_url.split(f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/")[-1]
                    await delete_from_s3(s3_key)
                    logger.info(f"🗑️ Изображение удалено из S3: {s3_key}")
                except Exception as del_e:
                    logger.error(f"❌ Не удалось удалить изображение из S3 по URL {s3_url}: {del_e}")

            await message.answer(f"❌ Ошибка при обновлении статуса задач: {e}")
            return False, published_count, failed_count, total_translations
    else:
        try:
            await db_session.rollback()
            failure_message = (
                f"❌ Публикация группы задач `{translation_group_id}` завершилась неудачно.\n"
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
            return False, published_count, failed_count, total_translations
        except Exception as e:
            logger.error(f"❌ Ошибка при откате транзакции: {e}")
            await message.answer(f"❌ Ошибка при откате транзакции: {e}")
            return False, published_count, failed_count, total_translations




