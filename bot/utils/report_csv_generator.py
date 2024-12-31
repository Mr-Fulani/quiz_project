import csv
from datetime import datetime
import logging
import os
from collections import defaultdict
from io import StringIO
from textwrap import wrap

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Task



# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)








async def generate_detailed_task_status_csv(
    unpublished_tasks,
    published_tasks,
    old_published_tasks,
    total_tasks,
    topics,
    db_session: AsyncSession
):
    """
    Генерация CSV-файла с детальной информацией по задачам, включая поле 'error'.
    Отображает все ID задач в каждой колонке с переносами строк для удобства чтения.
    """
    logger.info("Начало генерации CSV отчета статуса задач")

    # Создание буфера для CSV
    csv_buffer = StringIO()
    csv_writer = csv.writer(csv_buffer, quoting=csv.QUOTE_ALL)

    # Заголовки CSV
    headers = [
        "Топик",
        "Кол-во неопубл.",
        "ID неопубл. задач",
        "Кол-во опубл.",
        "ID опубл. задач",
        "Кол-во ст. опубл.",
        "ID ст. опубл. задач",
        "Общее кол-во задач",
        "Ошибки (Да/Нет)"
    ]
    csv_writer.writerow(headers)

    # Подготовка данных
    topic_data = defaultdict(
        lambda: {
            "unpublished": 0,
            "unpublished_ids": [],
            "published": 0,
            "published_ids": [],
            "old_published": 0,
            "old_published_ids": []
        }
    )

    logger.info("Начало обработки данных по задачам")

    # Обработка неопубликованных задач
    for topic_id, count, task_ids in unpublished_tasks:
        topic_data[topic_id]["unpublished"] += count
        topic_data[topic_id]["unpublished_ids"].extend(task_ids)
        logger.debug(f"Топик {topic_id}: добавлено {count} неопубликованных задач")

    # Обработка опубликованных задач
    for task in published_tasks:
        topic_id = task.topic_id
        task_id = task.id
        topic_data[topic_id]["published"] += 1
        topic_data[topic_id]["published_ids"].append(task_id)
        logger.debug(f"Топик {topic_id}: добавлена опубликованная задача ID {task_id}")

    # Обработка старых опубликованных задач
    for topic_id, task_id in old_published_tasks:
        topic_data[topic_id]["old_published"] += 1
        topic_data[topic_id]["old_published_ids"].append(task_id)
        logger.debug(f"Топик {topic_id}: добавлена старая опубликованная задача ID {task_id}")

    logger.info("Завершена обработка данных по задачам")

    # Фильтрация топиков, у которых есть хотя бы одна задача
    filtered_topics = {}
    for topic_id, topic_name in topics.items():
        data = topic_data[topic_id]
        total_topic_tasks = data["unpublished"] + data["published"] + data["old_published"]
        if total_topic_tasks > 0:
            # Если название топика содержит подстроку, связанную с subtopic, убираем ее
            if isinstance(topic_name, str) and '-' in topic_name:  # Пример, если subtopic отделен тире
                topic_name = topic_name.split('-')[0].strip()  # Оставляем только основной топик
            filtered_topics[topic_id] = topic_name
            logger.debug(
                f"Топик {topic_id}: всего задач {total_topic_tasks} "
                f"(неопубл: {data['unpublished']}, опубл: {data['published']}, ст. опубл: {data['old_published']})"
            )
        else:
            logger.debug(f"Топик {topic_id} пропущен (нет задач)")

    if not filtered_topics:
        logger.warning("Нет топиков с задачами для отображения.")
        return None

    # Сбор всех ID задач для проверки ошибок
    all_task_ids = []
    for data in topic_data.values():
        all_task_ids.extend(data["unpublished_ids"] + data["published_ids"] + data["old_published_ids"])

    # Получение задач из базы данных
    task_error_map = {}
    if all_task_ids:
        try:
            tasks_query = select(Task.id, Task.error).where(Task.id.in_(all_task_ids))
            result = await db_session.execute(tasks_query)
            tasks = result.fetchall()
            task_error_map = {task.id: task.error for task in tasks}
            logger.info(f"Получено {len(task_error_map)} задач для проверки ошибок.")
        except Exception as e:
            logger.error(f"Ошибка при получении задач для проверки ошибок: {e}")
            # Установим все ошибки как False в случае ошибки
            task_error_map = {task_id: False for task_id in all_task_ids}

    # Функция для форматирования ID с переносом строк
    def format_ids(ids, max_width):
        if not ids:
            return "Нет задач"
        ids_str = ', '.join(str(i) for i in ids)
        return '\r\n'.join(wrap(ids_str, width=max_width))

    # Запись данных в CSV
    for topic_id, topic_name in filtered_topics.items():
        data = topic_data[topic_id]
        total_topic_tasks = data["unpublished"] + data["published"] + data["old_published"]

        # Проверка наличия ошибок у задач
        error_exists = any(
            task_error_map.get(task_id, False)
            for task_id in data["unpublished_ids"] + data["published_ids"] + data["old_published_ids"]
        )
        error_status = "Да" if error_exists else "Нет"

        # Запись строки в CSV
        csv_writer.writerow([
            topic_name,
            data["unpublished"],
            format_ids(data["unpublished_ids"], 40),
            data["published"],
            format_ids(data["published_ids"], 40),
            data["old_published"],
            format_ids(data["old_published_ids"], 40),
            total_topic_tasks,
            error_status
        ])

    # Создание пути для сохранения CSV-файла
    csv_filename = f"detailed_task_status_report_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"  # Используем datetime.utcnow()
    csv_path = os.path.join("/tmp", csv_filename)  # Используем временную директорию

    try:
        with open(csv_path, mode='w', encoding='utf-8-sig', newline='') as csv_file:
            csv_file.write(csv_buffer.getvalue())
        logger.info(f"CSV отчет сохранен: {csv_path}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении CSV файла: {e}")
        return None

    return csv_path










async def generate_zero_task_topics_text(zero_task_topics: list) -> str:
    """
    Генерация текстового отчета со списком топиков без задач.
    Возвращает путь к сохранённому текстовому файлу.
    """
    logger.info("Начало генерации текстового отчета топиков без задач")

    if not zero_task_topics:
        logger.warning("Все топики имеют хотя бы одну задачу. Текстовый отчет не будет сгенерирован.")
        return None

    report_lines = ["📊 *Отчет топиков без задач:*\n"]
    for topic in zero_task_topics:
        line = f"• ID: {topic['id']} - Название: {topic['name']}"
        report_lines.append(line)

    report_content = "\n".join(report_lines)
    report_path = "/quiz_project/zero_task_topics_report.txt"

    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        logger.info(f"Текстовый отчет сохранен: {report_path}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении текстового отчета: {e}")
        return None

    return report_path