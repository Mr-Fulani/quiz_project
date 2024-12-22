import io
import json
import logging
import os
import random
import traceback
import uuid
from typing import Optional

from PIL import Image
from aiogram.client.session import aiohttp
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

import bot
from bot.services.default_link_service import DefaultLinkService
from bot.services.s3_services import delete_image_from_s3, save_image_to_storage
from config import S3_BUCKET_NAME, S3_REGION
from database.models import Task, TaskTranslation, Topic, Subtopic, Group





# Настройка локального логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Устанавливаем уровень логирования на DEBUG для подробного вывода
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)




# Глобальная переменная для хранения детального сообщения об ошибке при импорте
last_import_error_msg = ""






async def prepare_publication(
    task: Task,
    translation: TaskTranslation,
    image_url: str,
    db_session: AsyncSession,
    default_link_service: DefaultLinkService,  # Обязательный аргумент
    external_link: Optional[str] = None,
    user_chat_id: int = None
):
    """
    Подготавливает данные для публикации задачи в четыре сообщения:
    изображение, текст с деталями задачи, опрос и инлайн-кнопка.

    Args:
        task (Task): Объект задачи.
        translation (TaskTranslation): Перевод задачи.
        image_url (str): URL изображения для задачи.
        db_session (AsyncSession): Сессия базы данных.
        external_link (Optional[str]): Ссылка, передаваемая извне (например, из импорта JSON или интерфейса бота).
                                        Если None, будет использована ссылка из задачи или DefaultLinkService.
        user_chat_id (int): ID чата пользователя для уведомлений.

    Returns:
        tuple: Возвращает четыре сообщения (изображение, текст с деталями задачи, опрос и инлайн-кнопка).
    """
    logger.info(
        f"🔧 Начало подготовки публикации для задачи ID {task.id} "
        f"с переводом ID {translation.id} на языке {translation.language}"
    )

    def escape_md(text: str) -> str:
        """
        Экранирует специальные символы для использования в MarkdownV2.

        Args:
            text (str): Текст, который нужно экранировать.

        Returns:
            str: Экранированный текст.
        """
        escape_chars = r"_*[]()~`>#+-=|{}.!"
        escaped_text = ''.join(f"\\{char}" if char in escape_chars else char for char in text)
        logger.debug(f"Экранированный текст: {escaped_text}")
        return escaped_text

    language = translation.language

    # Словарь переводов для разных языков
    translations = {
        'ru': {
            'programming_language': 'Язык',
            'topic': 'Тема',
            'subtopic': 'Подтема',
            'no_subtopic': 'Без подтемы',
            'difficulty': 'Сложность',
            'quiz_question': "Какой будет вывод?"
        },
        'en': {
            'programming_language': 'Language',
            'topic': 'Topic',
            'subtopic': 'Subtopic',
            'no_subtopic': 'No subtopic',
            'difficulty': 'Difficulty',
            'quiz_question': "What will be the output?"
        },
        'es': {
            'programming_language': 'Idioma',
            'topic': 'Tema',
            'subtopic': 'Subtema',
            'no_subtopic': 'Sin subtema',
            'difficulty': 'Dificultad',
            'quiz_question': "¿Cuál será el resultado?"
        },
        'tr': {
            'programming_language': 'Dil',
            'topic': 'Konu',
            'subtopic': 'Alt Konu',
            'no_subtopic': 'Alt konu yok',
            'difficulty': 'Zorluk',
            'quiz_question': "Çıktı ne olacak?"
        },
        'ar': {
            'programming_language': 'اللغة',
            'topic': 'الموضوع',
            'subtopic': 'الموضوع الفرعي',
            'no_subtopic': 'لا يوجد موضوع فرعي',
            'difficulty': 'الصعوبة',
            'quiz_question': "ما هي النتيجة؟"
        }
    }

    # Получение перевода по языку, если язык отсутствует, используем английский как дефолт
    lang_translations = translations.get(language, translations['en'])
    logger.debug(f"Используем переводы для языка '{language}': {lang_translations}")

    # Подготовка текстового сообщения с деталями задачи
    escaped_topic = escape_md(task.topic.name)
    escaped_subtopic = escape_md(task.subtopic.name if task.subtopic else lang_translations['no_subtopic'])
    escaped_difficulty = escape_md(task.difficulty.capitalize())

    task_details_text = (
        f"🖥️ *{lang_translations['programming_language']}*: {escaped_topic}\n"
        f"📂 *{lang_translations['topic']}*: {escaped_subtopic}\n"
        f"🎯 *{lang_translations['difficulty']}*: {escaped_difficulty}\n"
    )

    logger.info(f"📋 Подготовлено текстовое сообщение с деталями задачи:\n{task_details_text}")

    text_message = {
        "type": "text",
        "text": task_details_text,
        "parse_mode": "MarkdownV2"
    }

    # Подготовка сообщения с изображением
    question_text = lang_translations['quiz_question']
    logger.info(f"📝 Текст вопроса на языке '{language}': {question_text}")

    image_message = {
        "type": "photo",
        "photo": image_url,
        "caption": question_text
    }
    logger.info(f"🖼️ Подготовлено сообщение с изображением и вопросом: {image_message['caption']}")

    # Подготовка опроса
    if isinstance(translation.answers, str):
        try:
            wrong_answers = json.loads(translation.answers)
            if not isinstance(wrong_answers, list):
                raise ValueError("Десериализованные answers должны быть списком.")
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка десериализации answers: {e}")
            raise
    elif isinstance(translation.answers, list):
        wrong_answers = translation.answers.copy()
    else:
        logger.error(f"Неподдерживаемый тип для translation.answers: {type(translation.answers)}")
        raise TypeError("translation.answers должен быть списком или JSON-строкой.")

    correct_answer = translation.correct_answer

    # Если правильный ответ уже содержится в вариантах, удаляем его
    if correct_answer in wrong_answers:
        wrong_answers.remove(correct_answer)
        logger.warning(f"⚠️ Дублирующийся правильный ответ удален, обновленные варианты: {wrong_answers}")

    # Формируем варианты ответов
    options = wrong_answers + [correct_answer]
    random.shuffle(options)
    correct_option_id = options.index(correct_answer)

    # Добавляем "Я не знаю, но хочу узнать"
    dont_know_option = {
        'ru': "Я не знаю, но хочу узнать",
        'en': "I don't know, but I want to learn",
        'es': "No lo sé, pero quiero aprender",
        'tr': "Bilmiyorum, ama öğrenmek istiyorum",
        'ar': "لا أعرف، ولكن أريد أن أتعلم"
    }.get(language, "Я не знаю, но хочу узнать")
    options.append(dont_know_option)

    logger.info(f"🔍 Вопрос: {question_text}")
    logger.info(f"🔍 Варианты ответов: {options}")
    logger.info(f"🔍 Индекс правильного ответа: {correct_option_id} (Правильный ответ: {correct_answer})")

    poll_message = {
        "question": question_text,  # Используем общий вопрос
        "options": options,
        "correct_option_id": correct_option_id,
        "explanation": translation.explanation or "",
        "is_anonymous": True,
        "type": "quiz"
    }

    logger.info(
        f"📊 Подготовлено сообщение для опроса:\n"
        f"Вопрос: {question_text}\n"
        f"Варианты: {options}\n"
        f"Правильный ответ: {correct_answer} (Индекс: {correct_option_id})\n"
        f"Тип опроса: {poll_message['type']}"
    )

    # Подготовка инлайн-кнопки "Узнать больше"
    learn_more_text = {
        'ru': "Узнать подробнее",
        'en': "Learn more",
        'es': "Saber más",
        'tr': "Daha fazla öğren",
        'ar': "تعلم المزيد"
    }.get(language, "Узнать подробнее")
    logger.info(f"🔗 Текст кнопки 'Узнать больше' на языке '{language}': {learn_more_text}")

    learn_more_about_task_text = {
        'ru': "Узнать больше о задаче:",
        'en': "Learn more about the task:",
        'es': "Saber más sobre la tarea:",
        'tr': "Görev hakkında daha fazla öğren:",
        'ar': "تعرف على المزيد حول المهمة:"
    }.get(language, "Узнать больше о задаче:")

    logger.info(f"✅ Текст 'Узнать больше о задаче' на языке '{language}': {learn_more_about_task_text}")

    # Если external_link не передан или отсутствует, пытаемся взять его из задачи или базы
    if not external_link:
        external_link = task.external_link
        if not external_link:
            logger.warning(f"🔗 external_link не задан для задачи ID {task.id}. Попытка получить ссылку по умолчанию...")
            external_link = await default_link_service.get_default_link(language, task.topic.name)
            if external_link:
                logger.info(f"🔗 Получена ссылка по умолчанию: {external_link}")
            else:
                # Резервная ссылка, если ничего не найдено
                external_link = "https://t.me/developers_hub_ru"
                logger.info(f"🔗 Не удалось получить ссылку по умолчанию, используется резервная: {external_link}")
    else:
        logger.info(f"🔗 Используется переданная извне ссылка: {external_link}")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=learn_more_text, url=external_link))
    learn_more_button = builder.as_markup()

    button_message = {
        "type": "text",
        "text": learn_more_about_task_text,
        "reply_markup": learn_more_button
    }
    logger.info(f"✅ Подготовлено сообщение с кнопкой 'Узнать больше'")

    logger.info(f"✅ Подготовка публикации завершена для задачи ID {task.id}")

    # Загрузка изображения в S3 и обновление external_link
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    image = Image.open(io.BytesIO(image_data)).convert("RGB")
                    image_name = f"{task.id}_{os.path.basename(image_url)}"
                    s3_url = await save_image_to_storage(image, image_name, user_chat_id)  # Передаем user_chat_id
                    if not s3_url:
                        raise Exception("Не удалось загрузить изображение в S3.")
                    # Обновляем external_link задачи с URL S3
                    task.external_link = s3_url
                    await db_session.commit()
                else:
                    raise Exception(f"Не удалось скачать изображение по URL: {image_url}")
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке изображения для задачи ID {task.id}: {e}")
        raise e  # Пробрасываем исключение для обработки отката

    return image_message, text_message, poll_message, button_message









async def import_tasks_from_json(file_path: str, db_session: AsyncSession, user_chat_id: int):
    """
    Импорт задач из файла JSON в базу данных.

    Args:
        file_path (str): Путь к JSON файлу.
        db_session (AsyncSession): Сессия базы данных.
        user_chat_id (int): ID чата пользователя для уведомлений.

    Returns:
        (successfully_loaded, failed_tasks, successfully_loaded_ids, error_messages)
    """
    successfully_loaded = 0
    failed_tasks = 0
    successfully_loaded_ids = []
    error_messages = []

    # Открываем и читаем файл
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    logger.info(f"📄 Содержимое файла JSON: {data}")

    default_link_service_instance = DefaultLinkService(db_session)

    for task_data in data.get("tasks", []):
        try:
            topic_name = task_data["topic"]
            translations = task_data.get("translations", [])
            if not translations:
                error_msg = f"Задача по топику '{topic_name}' не содержит переводов."
                logger.error(f"❌ {error_msg}")
                error_messages.append(error_msg)
                failed_tasks += 1
                continue

            # Получаем или создаём тему
            topic_id = await get_or_create_topic(db_session, topic_name)

            subtopic_name = task_data.get("subtopic")
            subtopic_id = None

            if subtopic_name:
                logger.debug(f"🔍 Поиск подтемы '{subtopic_name}' для топика '{topic_name}'.")
                result = await db_session.execute(select(Subtopic).where(Subtopic.name == subtopic_name))
                subtopic = result.scalar_one_or_none()
                if subtopic is None:
                    new_subtopic = Subtopic(name=subtopic_name, topic_id=topic_id)
                    db_session.add(new_subtopic)
                    await db_session.commit()
                    logger.info(f"✅ Подтема '{subtopic_name}' успешно создана с ID {new_subtopic.id}.")
                    subtopic_id = new_subtopic.id
                else:
                    subtopic_id = subtopic.id
                    logger.info(f"✅ Подтема '{subtopic_name}' найдена с ID {subtopic_id}.")
            else:
                logger.info(f"🔍 Подтема не задана для топика '{topic_name}'. Используется значение по умолчанию.")

            translation_group_id = task_data.get("translation_group_id", str(uuid.uuid4()))
            logger.debug(f"📁 Используем translation_group_id: {translation_group_id}")

            for translation in translations:
                language = translation["language"]
                question = translation.get("question")
                answers = translation.get("answers")
                correct_answer = translation.get("correct_answer")
                explanation = translation.get("explanation")
                external_link = translation.get("external_link")  # Может быть None

                if not all([question, answers, correct_answer]):
                    error_msg = f"Перевод на языке '{language}' неполный для задачи по топику '{topic_name}'."
                    logger.error(f"❌ {error_msg}")
                    error_messages.append(error_msg)
                    failed_tasks += 1
                    continue  # Продолжаем с другими переводами

                if isinstance(answers, str):
                    try:
                        wrong_answers = json.loads(answers)
                        if not isinstance(wrong_answers, list):
                            raise ValueError("Десериализованные answers должны быть списком.")
                    except json.JSONDecodeError as e:
                        error_msg = f"Ошибка десериализации answers на языке '{language}': {e}"
                        logger.error(f"❌ {error_msg}")
                        error_messages.append(error_msg)
                        failed_tasks += 1
                        continue
                elif isinstance(answers, list):
                    wrong_answers = answers.copy()
                else:
                    error_msg = f"Неподдерживаемый тип для translation.answers на языке '{language}': {type(answers)}"
                    logger.error(f"❌ {error_msg}")
                    error_messages.append(error_msg)
                    failed_tasks += 1
                    continue

                # **Всегда сериализуем answers как JSON строку**
                serialized_answers = json.dumps(wrong_answers + [correct_answer])

                if correct_answer in wrong_answers:
                    wrong_answers.remove(correct_answer)
                    logger.warning(f"⚠️ Дублирующийся правильный ответ удален, обновленные варианты: {wrong_answers}")

                options = wrong_answers + [correct_answer]
                random.shuffle(options)
                correct_option_id = options.index(correct_answer)

                dont_know_option = {
                    'ru': "Я не знаю, но хочу узнать",
                    'en': "I don't know, but I want to learn",
                    'es': "No lo sé, pero quiero aprender",
                    'tr': "Bilmiyorum, ama öğrenmek istiyorum",
                    'ar': "لا أعرف، ولكن أريد أن أتعلم"
                }.get(language, "Я не знаю, но хочу узнать")
                options.append(dont_know_option)

                logger.info(f"🔍 Вопрос: {question}")
                logger.info(f"🔍 Варианты ответов: {options}")
                logger.info(f"🔍 Индекс правильного ответа: {correct_option_id} (Правильный ответ: {correct_answer})")

                result = await db_session.execute(
                    select(Group).where(
                        Group.topic_id == topic_id,
                        Group.language == language
                    )
                )
                group = result.scalar_one_or_none()

                if group is None:
                    error_msg = f"Группа не найдена для топика '{topic_name}' и языка '{language}'."
                    logger.error(f"⚠️ {error_msg}")
                    error_messages.append(error_msg)
                    failed_tasks += 1
                    continue  # Продолжаем с другими переводами

                # Создаём Task с external_link = None
                new_task = Task(
                    topic_id=topic_id,
                    subtopic_id=subtopic_id,
                    difficulty=task_data["difficulty"],
                    published=False,
                    group_id=group.id,
                    translation_group_id=translation_group_id,
                    external_link=None  # Устанавливаем external_link в None
                )
                db_session.add(new_task)
                try:
                    await db_session.commit()
                    logger.info(f"✅ Задача успешно создана с ID {new_task.id} для группы '{group.group_name}'.")
                    successfully_loaded += 1
                    successfully_loaded_ids.append(new_task.id)
                except IntegrityError as ie:
                    await db_session.rollback()
                    error_msg = f"Ошибка при создании задачи с ID {new_task.id}: {ie}"
                    logger.error(f"❌ {error_msg}")
                    error_messages.append(error_msg)
                    failed_tasks += 1
                    continue
                except Exception as e:
                    await db_session.rollback()
                    error_msg = f"Неизвестная ошибка при создании задачи с ID {new_task.id}: {e}"
                    logger.error(f"❌ {error_msg}")
                    error_messages.append(error_msg)
                    failed_tasks += 1
                    continue

                # Создаём TaskTranslation
                new_translation = TaskTranslation(
                    task_id=new_task.id,
                    language=language,
                    question=question,
                    answers=json.dumps(wrong_answers + [correct_answer]),
                    correct_answer=correct_answer,
                    explanation=explanation
                )
                db_session.add(new_translation)
                try:
                    await db_session.commit()
                    logger.info(f"✅ Перевод на языке '{language}' для задачи ID {new_task.id} успешно сохранён.")
                except IntegrityError as ie:
                    await db_session.rollback()
                    error_msg = f"Ошибка при сохранении перевода для задачи ID {new_task.id}: {ie}"
                    logger.error(f"❌ {error_msg}")
                    error_messages.append(error_msg)
                    failed_tasks += 1
                    continue
                except Exception as e:
                    await db_session.rollback()
                    error_msg = f"Неизвестная ошибка при сохранении перевода для задачи ID {new_task.id}: {e}"
                    logger.error(f"❌ {error_msg}")
                    error_messages.append(error_msg)
                    failed_tasks += 1
                    continue

                image_url = task_data.get("image_url")
                if not image_url:
                    error_msg = f"Не задан image_url для задачи ID {new_task.id}."
                    logger.error(f"❌ {error_msg}")
                    error_messages.append(error_msg)
                    failed_tasks += 1
                    continue

                try:
                    # Передаём user_chat_id
                    image_message, text_message, poll_message, button_message = await prepare_publication(
                        task=new_task,
                        translation=new_translation,
                        image_url=image_url,
                        db_session=db_session,
                        default_link_service=default_link_service_instance,
                        external_link=external_link,  # Может быть None
                        user_chat_id=user_chat_id  # Добавлено
                    )
                    await send_publication_messages(new_task, new_translation, image_message, text_message, poll_message, button_message)
                except Exception as e:
                    error_msg = f"Ошибка при подготовке публикации для задачи ID {new_task.id}: {e}"
                    logger.error(f"❌ {error_msg}")
                    error_messages.append(error_msg)
                    failed_tasks += 1

                    # Откат: удаляем загруженное изображение из S3, если оно было загружено
                    if new_task.external_link:
                        s3_key = new_task.external_link.split(f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/")[-1]
                        await delete_image_from_s3(s3_key)
                        logger.info(f"🗑️ Изображение удалено из S3: {s3_key}")

                    # Откат: удаляем созданную задачу и перевод
                    await db_session.delete(new_translation)
                    await db_session.delete(new_task)
                    await db_session.commit()
                    logger.info(f"🔙 Откат изменений для задачи ID {new_task.id}")

                    continue

        except Exception as task_error:
            failed_tasks += 1
            error_msg = f"Ошибка при обработке задачи по топику '{task_data.get('topic', 'неизвестно')}': {task_error}"
            logger.error(f"❌ {error_msg}")
            error_messages.append(error_msg)
            logger.error(traceback.format_exc())

    logger.info(
        f"📊 Импорт завершен: успешно загружено {successfully_loaded}, проигнорировано {failed_tasks}."
    )
    logger.info(f"🆔 ID загруженных задач: {', '.join(map(str, successfully_loaded_ids)) if successfully_loaded_ids else 'нет задач'}")
    logger.info(f"📂 Обработка загрузки задач завершена.")

    if error_messages:
        global last_import_error_msg
        last_import_error_msg = "\n".join(error_messages)
        logger.error(f"❌ Импорт завершился с ошибками:\n{last_import_error_msg}")
    else:
        last_import_error_msg = ""

    return successfully_loaded, failed_tasks, successfully_loaded_ids, error_messages


async def get_or_create_topic(db_session: AsyncSession, topic_name: str) -> int:
    """
    Получаем или создаем тему.

    Args:
        db_session (AsyncSession): Сессия базы данных.
        topic_name (str): Название темы.

    Returns:
        int: ID темы.
    """
    logger.info(f"🔍 Поиск топика с именем '{topic_name}' в базе данных.")
    logger.debug(f"💡 db_session is async: {isinstance(db_session, AsyncSession)}")

    result = await db_session.execute(select(Topic).where(Topic.name == topic_name))
    topic = result.scalar_one_or_none()

    if not topic:
        logger.info(f"🆕 Топик '{topic_name}' не найден. Создание нового топика.")
        new_topic = Topic(name=topic_name)
        db_session.add(new_topic)
        try:
            await db_session.commit()
            logger.info(f"✅ Топик '{topic_name}' успешно создан с ID {new_topic.id}.")
            return new_topic.id
        except IntegrityError as ie:
            await db_session.rollback()
            logger.error(f"🔴 Ошибка при создании топика '{topic_name}': {ie}")
            raise ie
        except Exception as e:
            await db_session.rollback()
            logger.error(f"🔴 Неизвестная ошибка при создании топика '{topic_name}': {e}")
            raise e
    else:
        logger.info(f"✅ Топик '{topic_name}' найден с ID {topic.id}.")
        return topic.id




async def send_publication_messages(task, translation, image_message, text_message, poll_message, button_message):
    await bot.send_photo(chat_id=translation.group_id, photo=image_message['photo'], caption=image_message['caption'])
    await bot.send_message(chat_id=translation.group_id, text=text_message['text'], parse_mode=text_message['parse_mode'])
    await bot.send_poll(chat_id=translation.group_id, **poll_message)
    await bot.send_message(chat_id=translation.group_id, text=button_message['text'], reply_markup=button_message['reply_markup'])




