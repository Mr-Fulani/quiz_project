import logging
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


from database.models import Task, Group, TaskTranslation
from bot.services.image_service import generate_image_if_needed




logger = logging.getLogger(__name__)


# Функция для поиска группы по topic_id и языку
async def get_group_by_topic_and_language(topic_id: int, language: str, db_session: AsyncSession):
    # Ищем группу по topic_id и языку
    result = await db_session.execute(
        select(Group)
        .where(Group.topic_id == topic_id)  # Фильтруем по topic_id
        .where(Group.language == language)  # Добавляем фильтрацию по языку
    )
    group = result.scalar_one_or_none()  # Возвращаем одну запись или None

    # Если группа не найдена
    if not group:
        logger.error(f"Группа для топика {topic_id} и языка {language} не найдена.")
        return None

    return group  # Возвращаем найденную группу








async def publish_task_by_id(task_id: int, message, db_session: AsyncSession, bot: Bot):
    try:
        logger.info(f"Начало публикации задачи с ID {task_id}")

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
            logger.error(f"🔍Задача с ID {task_id} не найдена.")
            await message.answer(f"🔍Задача с ID {task_id} не найдена.")
            return False

        # Проверяем, была ли задача уже опубликована
        if task.published:
            # Если задача уже опубликована, проверяем, прошел ли месяц с последней публикации
            if task.publish_date and task.publish_date > datetime.now() - timedelta(days=30):
                time_left = (task.publish_date + timedelta(days=30)) - datetime.now()
                logger.info(f"⚠️Задача с ID {task_id} была опубликована менее месяца назад.")
                await message.answer(f"⚠️Задача с ID {task_id} была уже опубликована {task.publish_date.strftime('%Y-%m-%d %H:%M:%S')}. Следующая публикация возможна через {time_left.days} дней и {time_left.seconds // 3600} часов.")
                return False
            else:
                logger.info(f"🟢Задача с ID {task_id} уже была опубликована {task.publish_date.strftime('%Y-%m-%d %H:%M:%S')}, но прошел более месяц. Публикую заново.")

        # Получаем все задачи с тем же translation_group_id
        translation_group_tasks = await db_session.execute(
            select(Task)
            .options(
                joinedload(Task.translations),
                joinedload(Task.topic),
                joinedload(Task.subtopic)
            )
            .where(Task.translation_group_id == task.translation_group_id)
        )
        translation_group_tasks = translation_group_tasks.unique().scalars().all()

        logger.info(f"Найдено {len(translation_group_tasks)} задач в группе переводов {task.translation_group_id}")

        if len(translation_group_tasks) == 0:
            logger.warning(f"У задачи с ID {task_id} нет связанных переводов. Публикация невозможна.")
            await message.answer(f"У задачи с ID {task_id} нет связанных переводов. Публикация невозможна.")
            return False

        all_published = True
        published_languages = []
        failed_languages = []

        # Публикация каждого перевода с индивидуальной генерацией изображения
        for translation_task in translation_group_tasks:
            if not translation_task.translations:
                logger.error(f"У задачи с ID {translation_task.id} нет переводов.")
                failed_languages.append("Неизвестный язык")
                continue

            for translation in translation_task.translations:
                language = translation.language
                logger.info(f"Публикация версии задачи на языке: {language}")

                try:
                    # Генерация изображения для каждого перевода
                    logger.info(f"Генерация изображения для перевода задачи с ID {translation_task.id} на языке {language}")
                    image_url = await generate_image_if_needed(translation_task)

                    if not image_url:
                        logger.error(f"Ошибка при генерации изображения для перевода задачи с ID {translation_task.id} на языке {language}.")
                        failed_languages.append(language)
                        continue

                    # Вызов функции для публикации конкретного перевода
                    success = await publish_translation(translation, image_url, bot, db_session)

                    if success:
                        published_languages.append(language)
                        translation_task.published = True
                        translation_task.publish_date = datetime.now()  # Обновляем дату публикации
                        logger.info(f"Успешно опубликована версия на языке: {language}")
                    else:
                        all_published = False
                        failed_languages.append(language)
                        logger.error(f"Не удалось опубликовать версию на языке: {language}")
                except Exception as e:
                    all_published = False
                    failed_languages.append(language)
                    logger.error(f"Ошибка при публикации версии на языке {language}: {str(e)}")

        if all_published:
            await db_session.commit()  # Сохраняем изменения после успешной публикации
            success_message = f"Группа задач {task.translation_group_id} успешно опубликована на всех языках ({len(published_languages)}): {', '.join(published_languages)}"
            logger.info(success_message)
            await message.answer(success_message)
        else:
            if published_languages:
                await db_session.commit()  # Сохраняем частично успешные публикации
                partial_success_message = (
                    f"Группа задач {task.translation_group_id} опубликована частично:\n"
                    f"✅ Успешно: {len(published_languages)} из {len(translation_group_tasks)} языков: {', '.join(published_languages)}\n"
                    f"❌ Не удалось: {len(failed_languages)} языков: {', '.join(failed_languages)}"
                )
                logger.warning(partial_success_message)
                await message.answer(partial_success_message)
            else:
                await db_session.rollback()  # Откатываем изменения, если ни одна задача не была опубликована
                failure_message = f"Группа задач {task.translation_group_id} не была опубликована ни на одном из {len(translation_group_tasks)} языков из-за ошибок."
                logger.error(failure_message)
                await message.answer(failure_message + f"\nЯзыки с ошибками: {', '.join(failed_languages)}")

        return all_published
    except Exception as e:
        logger.error(f"Ошибка при публикации задачи с ID {task_id}: {str(e)}")

        await db_session.rollback()  # Откатываем другие изменения, если они были

        # Помечаем задачу как ошибочную
        task = await db_session.get(Task, task_id)
        task.error = True
        await db_session.commit()  # Сохраняем только изменение статуса задачи на ошибочную

        await message.answer(f"Произошла ошибка при публикации задачи с ID {task_id}. Задача помечена как проблемная. Подробности: {str(e)}")
        return False






async def publish_translation(translation: TaskTranslation, image_url: str, bot: Bot, db_session: AsyncSession):
    """
    Публикует перевод задачи в соответствующую группу на основе языка и топика.

    Args:
        translation (TaskTranslation): Объект перевода задачи.
        image_url (str): URL изображения для задачи.
        bot (Bot): Экземпляр бота для отправки сообщений.
        db_session (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        bool: True, если публикация успешна, False в противном случае.
    """
    language = None
    try:
        # Получаем язык перевода
        language = translation.language
        if not language:
            logger.error(f"🚫 Не удалось извлечь язык для перевода с ID {translation.id}.")
            return False

        # Получаем текст вопроса и возможные ответы
        task_text = translation.question
        answers = translation.answers
        correct_answer = translation.correct_answer

        # Ищем группу для данного языка и топика задачи
        result = await db_session.execute(
            select(Group)
            .where(Group.topic_id == translation.task.topic_id)
            .where(Group.language == language)
        )
        group = result.scalar_one_or_none()

        if not group:
            logger.error(f"🚫 Группа для языка '{language}' и топика '{translation.task.topic.name}' не найдена.")
            return False

        # Генерация изображения для задачи, если оно не было предоставлено
        task_image_url = image_url if image_url else await generate_image_if_needed(translation.task)

        # Отправляем изображение и текст задачи в группу
        await bot.send_photo(
            chat_id=group.group_id,
            photo=task_image_url,
            caption=task_text
        )
        logger.info(f"📷 Сообщение с изображением отправлено в группу '{group.group_name}' (язык: {language}).")

        # Отправляем опрос
        correct_option_id = answers.index(correct_answer)
        await bot.send_poll(
            chat_id=group.group_id,
            question=task_text,
            options=answers,
            type="quiz",
            correct_option_id=correct_option_id,
            explanation=translation.explanation,
            is_anonymous=False
        )
        logger.info(f"📊 Опрос успешно опубликован в группе '{group.group_name}' (язык: {language}).")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при публикации перевода на языке {language or 'неизвестный'}: {str(e)}")
        return False





async def publish_task_by_translation_group(translation_group_id, message, db_session: AsyncSession, bot: Bot):
    """
    Публикует все переводы задач, принадлежащих к указанной группе переводов.

    Args:
        translation_group_id: ID группы переводов.
        message: Объект сообщения для отправки ответов пользователю.
        db_session (AsyncSession): Асинхронная сессия базы данных.
        bot (Bot): Экземпляр бота для отправки сообщений.

    Returns:
        tuple: (success, published_count, failed_count, total_translations)
    """
    published_count = 0
    failed_count = 0
    total_translations = 0

    try:
        # Поиск всех задач с данным translation_group_id
        result = await db_session.execute(
            select(Task)
            .options(
                joinedload(Task.translations),
                joinedload(Task.topic),
                joinedload(Task.subtopic)
            )
            .where(Task.translation_group_id == translation_group_id)
        )

        tasks = result.unique().scalars().all()
        total_translations = len(tasks)

        if total_translations == 0:
            logger.warning(f"⚠️ Нет задач для публикации в группе переводов {translation_group_id}.")
            await message.answer(f"⚠️ Нет задач для публикации в группе переводов {translation_group_id}.")
            return False, published_count, failed_count, total_translations

        logger.info(f"📚 Начало публикации группы переводов {translation_group_id}. Всего задач: {total_translations}")

        # Генерация уникального изображения для каждой задачи
        for task in tasks:
            image_url = await generate_image_if_needed(task)
            if not image_url:
                logger.error(f"🚫 Ошибка при генерации изображения для задачи {task.id}.")
                await message.answer(f"🚫 Ошибка при генерации изображения для задачи {task.id}.")
                return False, published_count, failed_count, total_translations

            # Публикуем переводы задачи
            for translation in task.translations:
                language = translation.language
                logger.info(f"🌐 Публикация перевода на языке: {language}")

                try:
                    # Проверяем корректность данных перевода
                    if not translation.question or not translation.answers or not translation.correct_answer:
                        logger.error(f"⚠️ Некорректные данные перевода на языке: {language}. Пропуск перевода.")
                        failed_count += 1
                        continue

                    # Функция публикации конкретного перевода
                    success = await publish_translation(translation, image_url, bot, db_session)

                    if success:
                        published_count += 1
                        task.published = True
                        task.publish_date = datetime.now()
                        logger.info(f"✅ Успешно опубликован перевод на языке: {language}")
                    else:
                        failed_count += 1
                        logger.error(f"❌ Не удалось опубликовать перевод на языке: {language}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Ошибка при публикации перевода на языке {language}: {str(e)}")

        await db_session.commit()
        logger.info(f"📊 Итоги публикации группы переводов {translation_group_id}:")
        logger.info(f"   ✅ Успешно: {published_count}")
        logger.info(f"   ❌ Не удалось: {failed_count}")
        logger.info(f"   📚 Всего: {total_translations}")
        return True, published_count, failed_count, total_translations

    except Exception as e:
        logger.error(f"❌ Ошибка при публикации группы задач {translation_group_id}: {str(e)}")
        await db_session.rollback()
        return False, published_count, failed_count, total_translations