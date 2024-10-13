import json
import logging
import traceback

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Task, TaskTranslation, Topic, Subtopic, Group




# Настройка локального логирования
logger = logging.getLogger(__name__)





async def import_tasks_from_json(file_path: str, db_session: AsyncSession):
    try:
        # Чтение JSON файла
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            logger.info(f"Содержимое файла JSON: {data}")

        successfully_loaded = 0  # Количество успешно загруженных задач
        failed_tasks = 0  # Количество проигнорированных задач

        # Перебираем задачи в JSON
        for task_data in data["tasks"]:
            try:
                topic_name = task_data["topic"]
                topic_description = task_data.get("description", "")

                # Получаем значение external_link или используем значение по умолчанию
                external_link = task_data.get("external_link", "https://t.me/tyt_python")

                # Поиск или создание темы
                result = await db_session.execute(select(Topic).where(Topic.name == topic_name))
                topic = result.scalar_one_or_none()

                if topic is None:
                    new_topic = Topic(name=topic_name, description=topic_description)
                    db_session.add(new_topic)
                    await db_session.commit()
                    topic = new_topic

                topic_id = topic.id
                subtopic_name = task_data.get("subtopic")
                subtopic_id = None

                if subtopic_name:
                    result = await db_session.execute(select(Subtopic).where(Subtopic.name == subtopic_name))
                    subtopic = result.scalar_one_or_none()
                    if subtopic is None:
                        new_subtopic = Subtopic(name=subtopic_name, topic_id=topic_id)
                        db_session.add(new_subtopic)
                        await db_session.commit()
                        subtopic = new_subtopic
                    subtopic_id = subtopic.id

                # Обрабатываем переводы для задачи
                for translation in task_data["translations"]:
                    language = translation["language"]

                    result = await db_session.execute(
                        select(Group).where(Group.topic_id == topic_id).where(Group.language == language))
                    group = result.scalar_one_or_none()

                    if group is None:
                        logger.error(
                            f"Группа не найдена для топика '{topic_name}' и языка '{language}'. Задача не будет сохранена.")
                        raise ValueError(f"Группа не найдена для топика '{topic_name}' и языка '{language}'")

                    group_id = group.id

                    # Проверка наличия поля correct_answer
                    if "correct_answer" not in translation:
                        logger.error(
                            f"Ошибка: Перевод на {language} для задачи по топику '{topic_name}' не содержит 'correct_answer'.")
                        raise KeyError(f"Отсутствует обязательное поле 'correct_answer' в переводе на {language}")

                    # Создаем новую задачу
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
                    successfully_loaded += 1  # Увеличиваем счетчик загруженных задач

                    logger.info(f"Задача успешно создана: {new_task.id} для группы {group.group_name}")

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

                logger.info(f"Перевод задачи {new_task.id} для языка {language} успешно создан.")


            except Exception as task_error:
                failed_tasks += 1  # Увеличиваем счетчик неудачных задач
                logger.error(f"Ошибка при обработке задачи: {task_data}. Ошибка: {task_error}")
                logger.error(traceback.format_exc())  # Логирование стека ошибки

        # Сообщаем о количестве загруженных и пропущенных задач
        logger.info(
            f"Импорт завершен. Успешно загружено задач: {successfully_loaded}, проигнорировано: {failed_tasks}.")
        return successfully_loaded, failed_tasks

    except Exception as e:
        logger.error(f"Произошла ошибка при импорте задач: {e}")
        logger.error(traceback.format_exc())
        return None



async def get_or_create_topic(db_session: AsyncSession, topic_name: str) -> int:
    """Получаем или создаем тему."""
    result = await db_session.execute(select(Topic).where(Topic.name == topic_name))
    topic = result.scalar_one_or_none()

    if not topic:
        new_topic = Topic(name=topic_name)
        db_session.add(new_topic)
        await db_session.commit()
        return new_topic.id
    return topic.id





async def get_or_create_subtopic(db_session: AsyncSession, topic_id: int, subtopic_name: str) -> int:
    """Получаем или создаем подтему."""
    result = await db_session.execute(
        select(Subtopic).where(Subtopic.name == subtopic_name, Subtopic.topic_id == topic_id)
    )
    subtopic = result.scalar_one_or_none()

    if not subtopic:
        new_subtopic = Subtopic(name=subtopic_name, topic_id=topic_id)
        db_session.add(new_subtopic)
        await db_session.commit()
        return new_subtopic.id
    return subtopic.id