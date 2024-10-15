import json
import logging
import traceback

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Task, TaskTranslation, Topic, Subtopic, Group



# Настройка локального логирования
logger = logging.getLogger(__name__)




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
            logger.info(f"Содержимое файла JSON: {data}")

        successfully_loaded = 0  # Количество успешно загруженных задач
        failed_tasks = 0  # Количество проигнорированных задач
        successfully_loaded_ids = []  # Список ID успешно загруженных задач

        # Перебираем задачи в JSON
        for task_data in data["tasks"]:
            try:
                topic_name = task_data["topic"]
                topic_description = task_data.get("description", "")

                # Получаем значение external_link или используем значение по умолчанию
                external_link = task_data.get("external_link", "https://t.me/tyt_python")

                # Поиск или создание темы
                logger.info("Попытка выполнить запрос к базе данных для поиска топика.")
                logger.info(f"db_session is async: {isinstance(db_session, AsyncSession)}")
                result = await db_session.execute(select(Topic).where(Topic.name == topic_name))
                logger.info("Запрос выполнен успешно.")
                topic = result.scalar_one_or_none()

                if topic is None:
                    logger.info(f"Создание нового топика: {topic_name}.")
                    new_topic = Topic(name=topic_name, description=topic_description)
                    db_session.add(new_topic)
                    await db_session.commit()
                    logger.info("Транзакция для создания топика выполнена успешно.")
                    topic = new_topic

                topic_id = topic.id
                subtopic_name = task_data.get("subtopic")
                subtopic_id = None

                if subtopic_name:
                    logger.info(f"Попытка выполнить запрос к базе данных для подтемы: {subtopic_name}.")
                    logger.info(f"db_session is async: {isinstance(db_session, AsyncSession)}")
                    result = await db_session.execute(select(Subtopic).where(Subtopic.name == subtopic_name))
                    logger.info("Запрос выполнен успешно.")
                    subtopic = result.scalar_one_or_none()

                    if subtopic is None:
                        logger.info(f"Создание новой подтемы: {subtopic_name}.")
                        new_subtopic = Subtopic(name=subtopic_name, topic_id=topic_id)
                        db_session.add(new_subtopic)
                        await db_session.commit()
                        logger.info("Транзакция для создания подтемы выполнена успешно.")
                        subtopic = new_subtopic

                    subtopic_id = subtopic.id

                # Обрабатываем переводы для задачи
                for translation in task_data["translations"]:
                    language = translation["language"]

                    logger.info(f"Поиск группы для топика '{topic_name}' и языка '{language}'.")
                    logger.info(f"db_session is async: {isinstance(db_session, AsyncSession)}")
                    result = await db_session.execute(
                        select(Group).where(Group.topic_id == topic_id).where(Group.language == language))
                    logger.info("Запрос выполнен успешно.")
                    group = result.scalar_one_or_none()

                    if group is None:
                        logger.error(f"Группа не найдена для топика '{topic_name}' и языка '{language}'.")
                        raise ValueError(f"Группа не найдена для топика '{topic_name}' и языка '{language}'.")

                    group_id = group.id

                    # Проверка наличия поля correct_answer
                    if "correct_answer" not in translation:
                        logger.error(
                            f"Перевод на {language} для задачи по топику '{topic_name}' не содержит 'correct_answer'.")
                        raise KeyError(f"Отсутствует обязательное поле 'correct_answer' в переводе на {language}.")

                    # Создаем новую задачу
                    logger.info(f"Создание новой задачи для топика '{topic_name}'.")
                    new_task = Task(
                        topic_id=topic_id,
                        subtopic_id=subtopic_id,
                        difficulty=task_data["difficulty"],
                        published=False,
                        group_id=group_id,
                        external_link=external_link  # Заполняем поле ссылкой на канал
                    )
                    db_session.add(new_task)
                    await db_session.commit()
                    logger.info("Транзакция для создания задачи выполнена успешно.")
                    successfully_loaded += 1  # Увеличиваем счетчик загруженных задач

                    # Сохраняем ID успешно загруженной задачи
                    successfully_loaded_ids.append(new_task.id)

                    logger.info(f"Задача успешно создана: {new_task.id} для группы {group.group_name}.")

                    # Сохраняем переводы задачи
                    new_translation = TaskTranslation(
                        task_id=new_task.id,
                        language=language,
                        question=translation["question"],
                        answers=translation["answers"],
                        correct_answer=translation["correct_answer"],  # Уже проверено на наличие
                        explanation=translation.get("explanation")  # Опциональное поле объяснения
                    )
                    db_session.add(new_translation)
                await db_session.commit()
                logger.info(f"Переводы для задачи {new_task.id} успешно сохранены.")

            except Exception as task_error:
                failed_tasks += 1  # Увеличиваем счетчик неудачных задач
                logger.error(f"Ошибка при обработке задачи: {task_data}. Ошибка: {task_error}")
                logger.error(traceback.format_exc())  # Логирование стека ошибки

        # Сообщаем о количестве загруженных и пропущенных задач
        logger.info(
            f"Импорт завершен. Успешно загружено задач: {successfully_loaded}, проигнорировано: {failed_tasks}."
        )
        logger.info(f"ID загруженных задач: {', '.join(map(str, successfully_loaded_ids))}")
        return successfully_loaded, failed_tasks, successfully_loaded_ids

    except Exception as e:
        logger.error(f"Произошла ошибка при импорте задач: {e}")
        logger.error(traceback.format_exc())
        # Откат транзакции при общей ошибке
        await db_session.rollback()
        return None


async def get_or_create_topic(db_session: AsyncSession, topic_name: str) -> int:
    """Получаем или создаем тему."""
    logger.info("Попытка выполнить запрос к базе данных для топика.")
    logger.info(f"db_session is async: {isinstance(db_session, AsyncSession)}")
    result = await db_session.execute(select(Topic).where(Topic.name == topic_name))
    logger.info("Запрос выполнен успешно.")
    topic = result.scalar_one_or_none()

    if not topic:
        logger.info(f"Создание нового топика: {topic_name}.")
        new_topic = Topic(name=topic_name)
        db_session.add(new_topic)
        await db_session.commit()
        logger.info("Транзакция для создания топика выполнена успешно.")
        return new_topic.id
    return topic.id


async def get_or_create_subtopic(db_session: AsyncSession, topic_id: int, subtopic_name: str) -> int:
    """Получаем или создаем подтему."""
    logger.info("Попытка выполнить запрос к базе данных для подтемы.")
    logger.info(f"db_session is async: {isinstance(db_session, AsyncSession)}")
    result = await db_session.execute(
        select(Subtopic).where(Subtopic.name == subtopic_name, Subtopic.topic_id == topic_id)
    )
    logger.info("Запрос выполнен успешно.")
    subtopic = result.scalar_one_or_none()

    if not subtopic:
        logger.info(f"Создание новой подтемы: {subtopic_name}.")
        new_subtopic = Subtopic(name=subtopic_name, topic_id=topic_id)
        db_session.add(new_subtopic)
        await db_session.commit()
        logger.info("Транзакция для создания подтемы выполнена успешно.")
        return new_subtopic.id
    return subtopic.id