import asyncio
import logging
from datetime import datetime
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.middlewares import db_session
from database.models import Task, Group
from bot.services.image_service import generate_image_if_needed



logger = logging.getLogger(__name__)


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
            logger.error(f"Задача с ID {task_id} не найдена.")
            await message.answer(f"Задача с ID {task_id} не найдена.")
            return False

        if task.published:
            logger.info(f"Задача с ID {task_id} уже была опубликована.")
            await message.answer(f"Задача с ID {task_id} уже опубликована.")
            return False

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

        # Генерация изображения для задачи (один раз для всех языков)
        logger.info(f"Генерация изображения для группы задач {task.translation_group_id}.")
        image_url = await generate_image_if_needed(task)
        if not image_url:
            logger.error(f"Ошибка при генерации изображения для группы задач {task.translation_group_id}.")
            await message.answer(f"Ошибка при генерации изображения для группы задач {task.translation_group_id}.")
            return False

        # Сохраняем ссылку на изображение для всех задач в группе переводов
        for translation_task in translation_group_tasks:
            translation_task.image_url = image_url

        all_published = True
        published_languages = []

        for translation_task in translation_group_tasks:
            if not translation_task.translations:
                logger.error(f"У задачи с ID {translation_task.id} нет переводов.")
                continue

            language = translation_task.translations[0].language
            logger.info(f"Публикация версии задачи на языке: {language}")
            try:
                # Вызов функции для публикации конкретного перевода
                success = await publish_translation(translation_task, image_url, bot, db_session)

                if success:
                    published_languages.append(language)
                    translation_task.published = True
                    translation_task.publish_date = datetime.now()
                    logger.info(f"Успешно опубликована версия на языке: {language}")
                else:
                    all_published = False
                    logger.error(f"Не удалось опубликовать версию на языке: {language}")
            except Exception as e:
                all_published = False
                logger.error(f"Ошибка при публикации версии на языке {language}: {str(e)}")

        if all_published:
            await db_session.commit()
            success_message = f"Группа задач {task.translation_group_id} успешно опубликована на всех языках ({len(published_languages)}): {', '.join(published_languages)}"
            logger.info(success_message)
            await message.answer(success_message)
        else:
            if published_languages:
                await db_session.commit()
                partial_success_message = f"Группа задач {task.translation_group_id} опубликована частично на {len(published_languages)} из {len(translation_group_tasks)} языков: {', '.join(published_languages)}"
                logger.warning(partial_success_message)
                await message.answer(partial_success_message + " Некоторые языки не были опубликованы из-за ошибок.")
            else:
                await db_session.rollback()
                failure_message = f"Группа задач {task.translation_group_id} не была опубликована ни на одном из {len(translation_group_tasks)} языков из-за ошибок."
                logger.error(failure_message)
                await message.answer(failure_message + " Проверьте логи для деталей.")

        return all_published
    except Exception as e:
        logger.error(f"Ошибка при публикации группы задач для ID {task_id}: {str(e)}")
        await db_session.rollback()
        await message.answer(f"Ошибка при публикации группы задач для ID {task_id}: {str(e)}")
        return False





async def publish_translation(translation_task: Task, image_url: str, bot: Bot, db_session: AsyncSession):
    """
    Публикует перевод задачи в соответствующую группу на основе языка и топика.
    """
    try:
        if not translation_task.translations:
            logger.error(f"У задачи с ID {translation_task.id} нет переводов.")
            return False

        translation = translation_task.translations[0]
        language = translation.language
        task_text = translation.question
        answers = translation.answers
        correct_answer = translation.correct_answer

        # Найти группу для данного языка и топика
        result = await db_session.execute(
            select(Group)
            .where(Group.topic_id == translation_task.topic_id)
            .where(Group.language == language)
        )
        group = result.scalar_one_or_none()

        if not group:
            logger.error(f"Группа для языка '{language}' и топика '{translation_task.topic.name}' не найдена.")
            return False

        # Отправляем изображение и текст задачи в группу
        await bot.send_photo(
            chat_id=group.group_id,
            photo=image_url,
            caption=task_text
        )
        logger.info(f"Сообщение с изображением отправлено в группу {group.group_name} (язык: {language}).")

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
        logger.info(f"Опрос успешно опубликован в группе {group.group_name} (язык: {language}).")

        return True
    except Exception as e:
        logger.error(f"Ошибка при публикации перевода на языке {language}: {str(e)}")
        return False