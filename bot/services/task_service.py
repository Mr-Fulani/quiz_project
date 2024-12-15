import json
import logging
import random
import traceback
import uuid

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from psycopg2 import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from bot.services.default_link_service import DefaultLinkService
from database.models import Task, TaskTranslation, Topic, Subtopic, Group

# Настройка локального логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Устанавливаем уровень логирования на DEBUG для подробного вывода
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


async def prepare_publication(task: Task, translation: TaskTranslation, image_url: str, db_session: AsyncSession):
    """
    Подготавливает данные для публикации задачи в четыре сообщения:
    изображение, текст с деталями задачи, опрос и инлайн-кнопка.

    Args:
        task (Task): Объект задачи.
        translation (TaskTranslation): Перевод задачи.
        image_url (str): URL изображения для задачи.
        db_session (AsyncSession): Сессия базы данных.

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
            'difficulty': 'Сложность'
        },
        'en': {
            'programming_language': 'Language',
            'topic': 'Topic',
            'subtopic': 'Subtopic',
            'no_subtopic': 'No subtopic',
            'difficulty': 'Difficulty'
        },
        'es': {
            'programming_language': 'Idioma',
            'topic': 'Tema',
            'subtopic': 'Subtema',
            'no_subtopic': 'Sin subtema',
            'difficulty': 'Dificultad'
        },
        'tr': {
            'programming_language': 'Dil',
            'topic': 'Konu',
            'subtopic': 'Alt Konu',
            'no_subtopic': 'Alt konu yok',
            'difficulty': 'Zorluk'
        },
        'ar': {
            'programming_language': 'اللغة',
            'topic': 'الموضوع',
            'subtopic': 'الموضوع الفرعي',
            'no_subtopic': 'لا يوجد موضوع فرعي',
            'difficulty': 'الصعوبة'
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
        "parse_mode": "MarkdownV2"  # Используем MarkdownV2 для форматирования
    }

    # Подготовка сообщения с изображением
    question_texts = {
        'ru': "Какой будет вывод?",
        'en': "What will be the output?",
        'es': "¿Cuál será el resultado?",
        'tr': "Çıktı ne olacak?",
        'ar': "ما هي النتيجة؟"
    }
    question_text = question_texts.get(language, "Какой будет вывод?")
    logger.info(f"📝 Текст вопроса на языке '{language}': {question_text}")

    image_message = {
        "type": "photo",
        "photo": image_url,
        "caption": question_text
    }
    logger.info(f"🖼️ Подготовлено сообщение с изображением и вопросом: {image_message['caption']}")

    # Подготовка опроса с исправленной логикой
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

    # Если правильный ответ уже содержится в вариантах, удаляем его перед тем, как добавить обратно
    if correct_answer in wrong_answers:
        wrong_answers.remove(correct_answer)
        logger.warning(f"⚠️ Дублирующийся правильный ответ удален, обновленные варианты: {wrong_answers}")

    # Объединяем все варианты ответов
    options = wrong_answers + [correct_answer]
    # Перемешиваем варианты ответов
    random.shuffle(options)

    # Определяем индекс правильного ответа
    correct_option_id = options.index(correct_answer)

    # Добавляем вариант "Я не знаю, но хочу узнать" в конец списка
    dont_know_option = {
        'ru': "Я не знаю, но хочу узнать",
        'en': "I don't know, but I want to learn",
        'es': "No lo sé, pero quiero aprender",
        'tr': "Bilmiyorum, ama öğrenmek istiyorum",
        'ar': "لا أعرف، ولكن أريد أن أتعلم"
    }.get(language, "Я не знаю, но хочу узнать")
    options.append(dont_know_option)

    logger.info(f"🔍 Вопрос: {translation.question}")
    logger.info(f"🔍 Варианты ответов: {options}")
    logger.info(f"🔍 Индекс правильного ответа: {correct_option_id} (Правильный ответ: {correct_answer})")

    # Формируем сообщение для опроса
    poll_message = {
        "question": translation.question,
        "options": options,
        "correct_option_id": correct_option_id,
        "explanation": translation.explanation or "",
        "is_anonymous": True,
        "type": "quiz"  # Явно указываем тип опроса "quiz"
    }

    logger.info(
        f"📊 Подготовлено сообщение для опроса:\n"
        f"Вопрос: {translation.question}\n"
        f"Варианты: {options}\n"
        f"Правильный ответ: {correct_answer} (Индекс: {correct_option_id})\n"
        f"Тип опроса: {poll_message['type']}"
    )

    # Подготовка инлайн-кнопки с переводом текста "Узнать больше о задаче"
    learn_more_text = {
        'ru': "Узнать подробнее",
        'en': "Learn more",
        'es': "Saber más",
        'tr': "Daha fazla öğren",
        'ar': "تعلم المزيد"
    }.get(language, "Узнать подробнее")
    logger.info(f"🔗 Текст кнопки 'Узнать больше' на языке '{language}': {learn_more_text}")

    # Текст для вывода перед кнопкой, также с переводом
    learn_more_about_task_text = {
        'ru': "Узнать больше о задаче:",
        'en': "Learn more about the task:",
        'es': "Saber más sobre la tarea:",
        'tr': "Görev hakkında daha fazla öğren:",
        'ar': "تعرف على المزيد حول المهمة:"
    }.get(language, "Узнать больше о задаче:")

    logger.info(f"✅ Текст 'Узнать больше о задаче' на языке '{language}': {learn_more_about_task_text}")

    # Получение ссылки для кнопки через task.external_link или DefaultLinkService
    external_link = task.external_link
    if not external_link:
        logger.warning(f"🔗 external_link не задан для задачи ID {task.id}. Используется дефолтная ссылка.")
        external_link = "https://t.me/developers_hub_ru"

    # Создаем билдер клавиатуры
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=learn_more_text, url=external_link))
    learn_more_button = builder.as_markup()

    button_message = {
        "type": "text",
        "text": learn_more_about_task_text,  # Используем перевод в зависимости от языка
        "reply_markup": learn_more_button
    }
    logger.info(f"✅ Подготовлено сообщение с кнопкой 'Узнать больше'")

    logger.info(f"✅ Подготовка публикации завершена для задачи ID {task.id}")

    return image_message, text_message, poll_message, button_message




async def get_default_link(language: str, topic: str, db_session: AsyncSession) -> str:
    """
    Возвращает ссылку по умолчанию для указанного языка и темы. Если ссылки нет, возвращает стандартную ссылку.

    Args:
        language (str): Язык.
        topic (str): Тема.
        db_session (AsyncSession): Сессия базы данных.

    Returns:
        str: URL ссылки.
    """
    default_link_service = DefaultLinkService(db_session)
    link = await default_link_service.get_default_link(language, topic)
    logger.debug(f"Получена ссылка по умолчанию для языка '{language}' и темы '{topic}': {link}")
    return link


async def import_tasks_from_json(file_path: str, db_session: AsyncSession):
    """
    Импорт задач из файла JSON в базу данных.

    Args:
        file_path (str): Путь к JSON файлу.
        db_session (AsyncSession): Сессия базы данных.

    Returns:
        tuple: Количество успешно загруженных задач, количество ошибок, список ID загруженных задач.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        logger.info(f"📄 Содержимое файла JSON: {data}")

        successfully_loaded = 0
        failed_tasks = 0
        successfully_loaded_ids = []

        default_link_service = DefaultLinkService(db_session)

        for task_data in data.get("tasks", []):
            try:
                topic_name = task_data["topic"]
                translations = task_data.get("translations", [])
                if not translations:
                    logger.error(f"❌ Задача по топику '{topic_name}' не содержит переводов.")
                    raise ValueError(f"Задача по топику '{topic_name}' не содержит переводов.")

                language = translations[0].get("language")
                if not language:
                    logger.error(f"❌ Перевод в задаче по топику '{topic_name}' не содержит языка.")
                    raise KeyError(f"Перевод в задаче по топику '{topic_name}' не содержит языка.")

                # Получение ссылки по умолчанию, если external_link отсутствует
                external_link = task_data.get("external_link")
                if not external_link:
                    external_link = await default_link_service.get_default_link(language, topic_name)
                    logger.info(f"🔗 Ссылка по умолчанию для топика '{topic_name}' и языка '{language}': {external_link}")

                # Поиск или создание темы
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

                    if not all([question, answers, correct_answer]):
                        logger.error(f"❌ Перевод на языке '{language}' неполный для задачи по топику '{topic_name}'.")
                        raise KeyError(f"Перевод на языке '{language}' неполный.")

                    logger.debug(f"🔍 Поиск группы для топика ID {topic_id} и языка '{language}'.")
                    result = await db_session.execute(
                        select(Group).where(Group.topic_id == topic_id, Group.language == language)
                    )
                    group = result.scalar_one_or_none()

                    if group is None:
                        logger.error(f"⚠️ Группа не найдена для топика '{topic_name}' и языка '{language}'.")
                        raise ValueError(f"Группа не найдена для топика '{topic_name}' и языка '{language}'.")

                    # Проверка наличия поля correct_answer
                    if "correct_answer" not in translation or not correct_answer:
                        logger.error(f"❌ Перевод на {language} для задачи по топику '{topic_name}' не содержит 'correct_answer'.")
                        raise KeyError(f"Отсутствует обязательное поле 'correct_answer' в переводе на {language}.")

                    # Создаем новую задачу
                    new_task = Task(
                        topic_id=topic_id,
                        subtopic_id=subtopic_id,
                        difficulty=task_data["difficulty"],
                        published=False,
                        group_id=group.id,
                        external_link=external_link,
                        translation_group_id=translation_group_id
                    )
                    db_session.add(new_task)
                    await db_session.commit()
                    logger.info(f"✅ Задача успешно создана с ID {new_task.id} для группы '{group.group_name}'.")
                    successfully_loaded += 1
                    successfully_loaded_ids.append(new_task.id)

                    # Сохраняем переводы задачи
                    new_translation = TaskTranslation(
                        task_id=new_task.id,
                        language=language,
                        question=question,
                        answers=json.dumps(answers),  # Преобразуем список ответов в JSON строку
                        correct_answer=correct_answer,
                        explanation=explanation
                    )
                    db_session.add(new_translation)
                    await db_session.commit()
                    logger.info(f"✅ Перевод на языке '{language}' для задачи ID {new_task.id} успешно сохранён.")

            except Exception as task_error:
                failed_tasks += 1
                logger.error(f"❌ Ошибка при обработке задачи по топику '{task_data.get('topic', 'неизвестно')}': {task_error}")
                logger.error(traceback.format_exc())

        logger.info(
            f"📊 Импорт завершен: успешно загружено {successfully_loaded}, проигнорировано {failed_tasks}."
        )
        logger.info(f"🆔 ID загруженных задач: {', '.join(map(str, successfully_loaded_ids))}")
        return successfully_loaded, failed_tasks, successfully_loaded_ids

    except Exception as e:
        logger.error(f"❌ Произошла ошибка при импорте задач: {e}")
        logger.error(traceback.format_exc())
        await db_session.rollback()
        return None


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

    # Запрос к базе данных
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




