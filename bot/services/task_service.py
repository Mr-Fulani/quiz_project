import json
import logging
import random
import traceback
import uuid

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.models import Task, TaskTranslation, Topic, Subtopic, Group

# Настройка локального логирования
logger = logging.getLogger(__name__)





async def prepare_publication(task: Task, translation: TaskTranslation, image_url: str):
    """
    Подготавливает данные для публикации задачи в четыре сообщения:
    изображение, текст с деталями задачи, опрос и инлайн-кнопка.

    Args:
        task (Task): Объект задачи.
        translation (TaskTranslation): Перевод задачи.
        image_url (str): URL изображения для задачи.

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
        return ''.join(f"\\{char}" if char in escape_chars else char for char in text)

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
        'arab': {
            'programming_language': 'اللغة',
            'topic': 'الموضوع',
            'subtopic': 'الموضوع الفرعي',
            'no_subtopic': 'لا يوجد موضوع فرعي',
            'difficulty': 'الصعوبة'
        }
    }

    # Подготовка текстового сообщения с деталями задачи
    escaped_topic = escape_md(task.topic.name)
    escaped_subtopic = escape_md(task.subtopic.name if task.subtopic else translations[language]['no_subtopic'])
    escaped_difficulty = escape_md(task.difficulty.capitalize())

    task_details_text = (
        f"🖥️ *{translations[language]['programming_language']}*: {escaped_topic}\n"
        f"📂 *{translations[language]['topic']}*: {escaped_subtopic}\n"
        f"🎯 *{translations[language]['difficulty']}*: {escaped_difficulty}\n"
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
        'arab': "ما هي النتيجة؟"
    }
    question_text = question_texts.get(language, "Какой будет вывод?")
    logger.info(f"📝 Текст вопроса на языке {language}: {question_text}")

    image_message = {
        "type": "photo",
        "photo": image_url,
        "caption": question_text
    }
    logger.info(f"🖼️ Подготовлено сообщение с изображением и вопросом: {image_message['caption']}")

    # Подготовка опроса с исправленной логикой
    wrong_answers = translation.answers
    correct_answer = translation.correct_answer

    # Если правильный ответ уже содержится в вариантах, удаляем его перед тем, как добавить обратно
    if correct_answer in wrong_answers:
        wrong_answers.remove(correct_answer)
        logger.info(f"⚠️ Дублирующийся правильный ответ удален, обновленные варианты: {wrong_answers}")

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
        'arab': "لا أعرف، ولكن أريد أن أتعلم"
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
        "explanation": translation.explanation,
        "is_anonymous": True,
        "type": "quiz"  # Явно указываем тип опроса "quiz"
    }

    logger.info(
        f"📊 Подготовлено сообщение для опроса:\n"
        f"Вопрос: {translation.question}\n"
        f"Варианты: {options}\n"
        f"Правильный ответ: {correct_answer} (Индекс: {correct_option_id})\n"
        f"Тип опроса: quiz"
    )

    # Подготовка инлайн-кнопки с переводом текста "Узнать больше о задаче"
    learn_more_text = {
        'ru': "Узнать подробнее",
        'en': "Learn more",
        'es': "Saber más",
        'tr': "Daha fazla öğren",
        'arab': "تعلم المزيد"
    }.get(language, "Узнать подробнее")
    logger.info(f"🔗 Текст кнопки 'Узнать больше' на языке {language}: {learn_more_text}")


    # Текст для вывода перед кнопкой, также с переводом
    learn_more_about_task_text = {
        'ru': "Узнать больше о задаче:",
        'en': "Learn more about the task:",
        'es': "Saber más sobre la tarea:",
        'tr': "Görev hakkında daha fazla öğren:",
        'arab': "تعرف على المزيد حول المهمة:"
    }.get(language, "Узнать больше о задаче:")

    logger.info(f"✅ Текст 'Узнать больше о задаче' на языке {language}: {learn_more_about_task_text}")

    external_link = task.external_link or "https://t.me/tyt_python"

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






DEFAULT_LINKS = {
    "en": {
        "Python": "https://t.me/tyt_python",
        "SQL": "https://t.me/tyt_python",
        "Golang": "https://t.me/golang_eng",
        "Java": "https://t.me/tyt_python",
        "JavaScript": "https://t.me/tyt_python",
        "Django": "https://t.me/tyt_python",
    },
    "ru": {
        "Python": "https://t.me/tyt_python",
        "SQL": "https://t.me/sql_hub_channel",
        "Golang": "https://t.me/tyt_python",
        "Java": "https://t.me/tyt_python",
        "JavaScript": "https://t.me/tyt_python",
        "Django": "https://t.me/tyt_python",
    },
    "tr": {
        "Python": "https://t.me/pythonchik_tr",
        "SQL": "https://t.me/tyt_python",
        "Golang": "https://t.me/tyt_python",
        "Java": "https://t.me/tyt_python",
        "JavaScript": "https://t.me/tyt_python",
        "Django": "https://t.me/tyt_python",
    },
}





def get_default_link(language: str, topic: str) -> str:
    """
    Возвращает ссылку по умолчанию для указанного языка и темы. Если ссылки нет, возвращает стандартную ссылку.
    """
    return DEFAULT_LINKS.get(language, {}).get(topic, "https://t.me/tyt_python")





async def import_tasks_from_json(file_path: str, db_session: AsyncSession):
    """
    Импорт задач из файла JSON в базу данных.

    :param file_path: Путь к файлу JSON.
    :param db_session: Асинхронная сессия базы данных.
    :return: Количество успешно загруженных и неудачных задач, а также список ID загруженных задач.
    """
    try:
        # Чтение JSON файла
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            logger.info(f"📄 Содержимое файла JSON: {data}")

        successfully_loaded = 0  # Количество успешно загруженных задач
        failed_tasks = 0  # Количество проигнорированных задач
        successfully_loaded_ids = []  # Список ID успешно загруженных задач

        # Перебираем задачи в JSON
        for task_data in data["tasks"]:
            try:
                topic_name = task_data["topic"]
                topic_description = task_data.get("description", "")
                language = task_data["translations"][0]["language"]  # Предполагаем, что первый перевод содержит язык

                # Если external_link отсутствует, назначаем его по умолчанию
                external_link = task_data.get("external_link")
                if not external_link:
                    external_link = get_default_link(language, topic_name)
                    logger.info(f"🔗 Ссылка по умолчанию для топика '{topic_name}' и языка '{language}': {external_link}")

                # Поиск или создание темы
                logger.info(f"🔍 Поиск топика: {topic_name}.")
                result = await db_session.execute(select(Topic).where(Topic.name == topic_name))
                topic = result.scalar_one_or_none()

                if topic is None:
                    logger.info(f"🆕 Создание нового топика: {topic_name}.")
                    new_topic = Topic(name=topic_name, description=topic_description)
                    db_session.add(new_topic)
                    await db_session.commit()
                    logger.info(f"✅ Топик '{topic_name}' успешно создан.")
                    topic = new_topic

                topic_id = topic.id
                subtopic_name = task_data.get("subtopic")
                subtopic_id = None

                if subtopic_name:
                    logger.info(f"🔍 Поиск подтемы: {subtopic_name}.")
                    result = await db_session.execute(select(Subtopic).where(Subtopic.name == subtopic_name))
                    subtopic = result.scalar_one_or_none()

                    if subtopic is None:
                        logger.info(f"🆕 Создание новой подтемы: {subtopic_name}.")
                        new_subtopic = Subtopic(name=subtopic_name, topic_id=topic_id)
                        db_session.add(new_subtopic)
                        await db_session.commit()
                        logger.info(f"✅ Подтема '{subtopic_name}' успешно создана.")
                        subtopic = new_subtopic

                    subtopic_id = subtopic.id

                # Получаем или генерируем translation_group_id для задачи
                translation_group_id = task_data.get("translation_group_id", str(uuid.uuid4()))

                # Обрабатываем переводы для задачи
                for translation in task_data["translations"]:
                    language = translation["language"]

                    logger.info(f"🌐 Поиск группы для топика '{topic_name}' и языка '{language}'.")
                    result = await db_session.execute(
                        select(Group).where(Group.topic_id == topic_id).where(Group.language == language))
                    group = result.scalar_one_or_none()

                    if group is None:
                        logger.error(f"⚠️ Группа не найдена для топика '{topic_name}' и языка '{language}'.")
                        raise ValueError(f"Группа не найдена для топика '{topic_name}' и языка '{language}'.")

                    group_id = group.id

                    # Проверка наличия поля correct_answer
                    if "correct_answer" not in translation:
                        logger.error(
                            f"❌ Перевод на {language} для задачи по топику '{topic_name}' не содержит 'correct_answer'.")
                        raise KeyError(f"Отсутствует обязательное поле 'correct_answer' в переводе на {language}.")

                    # Создаем новую задачу
                    logger.info(f"📝 Создание новой задачи для топика '{topic_name}' с языком '{language}'.")
                    new_task = Task(
                        topic_id=topic_id,
                        subtopic_id=subtopic_id,
                        difficulty=task_data["difficulty"],
                        published=False,
                        group_id=group_id,
                        external_link=external_link,
                        translation_group_id=translation_group_id
                    )
                    db_session.add(new_task)
                    await db_session.commit()
                    successfully_loaded += 1  # Увеличиваем счетчик загруженных задач
                    successfully_loaded_ids.append(new_task.id)
                    logger.info(f"✅ Задача успешно создана с ID {new_task.id} для группы {group.group_name}.")

                    # Сохраняем переводы задачи
                    new_translation = TaskTranslation(
                        task_id=new_task.id,
                        language=language,
                        question=translation["question"],
                        answers=translation["answers"],
                        correct_answer=translation["correct_answer"],
                        explanation=translation.get("explanation")
                    )
                    db_session.add(new_translation)
                await db_session.commit()
                logger.info(f"✅ Переводы для задачи с ID {new_task.id} успешно сохранены.")

            except Exception as task_error:
                failed_tasks += 1  # Увеличиваем счетчик неудачных задач
                logger.error(f"❌ Ошибка при обработке задачи по топику '{topic_name}': {task_error}")
                logger.error(traceback.format_exc())  # Логирование стека ошибки

        # Сообщаем о количестве загруженных и пропущенных задач
        logger.info(
            f"📊 Импорт завершен: успешно загружено {successfully_loaded}, проигнорировано {failed_tasks}."
        )
        logger.info(f"🆔 ID загруженных задач: {', '.join(map(str, successfully_loaded_ids))}")
        return successfully_loaded, failed_tasks, successfully_loaded_ids

    except Exception as e:
        logger.error(f"❌ Произошла ошибка при импорте задач: {e}")
        logger.error(traceback.format_exc())
        # Откат транзакции при общей ошибке
        await db_session.rollback()
        return None




async def get_or_create_topic(db_session: AsyncSession, topic_name: str) -> int:
    """Получаем или создаем тему."""
    logger.info(f"🔍 Поиск топика с именем '{topic_name}' в базе данных.")
    logger.info(f"💡 db_session is async: {isinstance(db_session, AsyncSession)}")

    # Запрос к базе данных
    result = await db_session.execute(select(Topic).where(Topic.name == topic_name))
    topic = result.scalar_one_or_none()

    if not topic:
        logger.info(f"🆕 Топик '{topic_name}' не найден. Создание нового топика.")
        new_topic = Topic(name=topic_name)
        db_session.add(new_topic)
        await db_session.commit()
        logger.info(f"✅ Топик '{topic_name}' успешно создан с ID {new_topic.id}.")
        return new_topic.id

    logger.info(f"✅ Топик '{topic_name}' найден с ID {topic.id}.")
    return topic.id













