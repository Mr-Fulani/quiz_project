import logging
from collections import defaultdict
from textwrap import wrap
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select

from database.models import Topic

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)











async def generate_detailed_task_status_image(unpublished_tasks, old_published_tasks, total_tasks, topics,
                                              published_tasks):
    """
    Генерация изображения с информацией по задачам.
    """
    logger.info("Начало генерации изображения статуса задач")

    # Размеры изображения
    row_height = 150  # Увеличенная высота строки для лучшего отображения
    max_rows = len(topics)  # Используем количество топиков для определения числа строк
    table_height = max_rows * row_height + 200
    width, height = 2400, table_height  # Увеличена ширина изображения

    # Цвета и фон
    background_color = (255, 255, 255)  # Белый фон
    text_color = (0, 0, 0)  # Черный текст
    line_color = (200, 200, 200)  # Цвет линий

    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    font_path = "/Library/Fonts/Arial Unicode.ttf"  # Путь к шрифту
    font = ImageFont.truetype(font_path, 16)  # Шрифт текста
    small_font = ImageFont.truetype(font_path, 12)  # Уменьшенный шрифт для длинных списков ID
    header_font = ImageFont.truetype(font_path, 20)  # Шрифт для заголовков

    title = f"Отчет по задачам (Всего задач: {total_tasks})"
    y_offset = 20
    draw.text((width // 2 - draw.textbbox((0, 0), title, font=header_font)[2] // 2, y_offset), title, font=header_font,
              fill=text_color)

    # Заголовки колонок
    headers = [
        "Топик", "Кол-во неопубл.", "ID неопубл. задач", "Кол-во опубл.", "ID опубл. задач",
        "Кол-во ст. опубл.", "ID ст. опубл. задач", "Общее кол-во задач"
    ]

    y_offset += 50
    column_widths = [250, 150, 400, 150, 400, 150, 400, 150]  # Настроены ширины колонок

    # Рисуем заголовки
    for i, header in enumerate(headers):
        draw.text((sum(column_widths[:i]) + 10, y_offset), header, font=font, fill=text_color)

    y_offset += 40
    draw.line([(0, y_offset), (width, y_offset)], fill=line_color, width=2)
    y_offset += 10

    # Вертикальные линии таблицы
    for x_offset in [sum(column_widths[:i]) for i in range(len(column_widths) + 1)]:
        draw.line([(x_offset, y_offset - 40), (x_offset, height)], fill=line_color, width=2)

    # Функция для форматирования ID с переносом строк
    def format_ids(ids, max_width):
        if not ids:
            return "Нет задач"
        ids_str = ', '.join(str(i) for i in ids)
        return '\n'.join(wrap(ids_str, width=max_width))

    # Подготовка данных
    topic_data = defaultdict(
        lambda: {"unpublished": 0, "unpublished_ids": [], "published": 0, "published_ids": [], "old_published": 0,
                 "old_published_ids": []})

    logger.info("Начало обработки данных по задачам")

    # Обработка неопубликованных задач
    for topic_id, _, task_ids in unpublished_tasks:
        topic_data[topic_id]["unpublished"] += len(task_ids)
        topic_data[topic_id]["unpublished_ids"].extend(task_ids)
        logger.debug(f"Топик {topic_id}: добавлено {len(task_ids)} неопубликованных задач")

    # Логирование списка опубликованных задач
    logger.debug(f"Опубликованные задачи: {published_tasks}")

    for task in published_tasks:
        topic_id = task[0]  # Первый элемент — topic_id
        task_ids = task[1]  # Остальные элементы — task_ids
        logger.debug(f"Топик {topic_id}: опубликованные задачи {task_ids}")
        topic_data[topic_id]["published"] += len(task_ids)  # Количество опубликованных задач
        topic_data[topic_id]["published_ids"].extend(task_ids)  # Добавляем ID задач
        logger.debug(f"Топик {topic_id}: добавлено {len(task_ids)} опубликованных задач")

    for topic_id, task_id in old_published_tasks:
        topic_data[topic_id]["old_published"] += 1
        topic_data[topic_id]["old_published_ids"].append(task_id)
        logger.debug(f"Топик {topic_id}: добавлена 1 старая опубликованная задача")

    logger.info("Завершена обработка данных по задачам")

    for topic_id, topic_name in topics.items():
        # Если topic_name содержит подстроку, связанную с subtopic, убираем ее
        if isinstance(topic_name, str) and '-' in topic_name:  # Пример, если subtopic отделен тире
            topic_name = topic_name.split('-')[0].strip()  # Оставляем только основной топик

        data = topic_data[topic_id]
        current_y = y_offset
        max_y = current_y

        # Подсчет общего количества задач (опубликованных и неопубликованных)
        total_topic_tasks = data["unpublished"] + data["published"]
        logger.debug(
            f"Топик {topic_id}: всего задач {total_topic_tasks} (неопубл: {data['unpublished']}, опубл: {data['published']})")

        # Функция для отрисовки текста с переносом
        def draw_wrapped_text(text, x, y, max_width, font):
            lines = wrap(text, width=max_width)
            for line in lines:
                draw.text((x, y), line, font=font, fill=text_color)
                y += font.getbbox(line)[3] + 5
            return y

        # Отрисовка данных
        max_y = max(max_y, draw_wrapped_text(topic_name, 10, current_y, 30, font))
        max_y = max(max_y,
                    draw_wrapped_text(str(data["unpublished"]), sum(column_widths[:1]) + 10, current_y, 15, font))
        max_y = max(max_y,
                    draw_wrapped_text(format_ids(data["unpublished_ids"], 40), sum(column_widths[:2]) + 10, current_y,
                                      40, small_font))
        max_y = max(max_y, draw_wrapped_text(str(data["published"]), sum(column_widths[:3]) + 10, current_y, 15, font))
        max_y = max(max_y,
                    draw_wrapped_text(format_ids(data["published_ids"], 40), sum(column_widths[:4]) + 10, current_y, 40,
                                      small_font))
        max_y = max(max_y,
                    draw_wrapped_text(str(data["old_published"]), sum(column_widths[:5]) + 10, current_y, 15, font))
        max_y = max(max_y,
                    draw_wrapped_text(format_ids(data["old_published_ids"], 40), sum(column_widths[:6]) + 10, current_y,
                                      40, small_font))
        max_y = max(max_y, draw_wrapped_text(str(total_topic_tasks), sum(column_widths[:7]) + 10, current_y, 15,
                                             font))  # Общее количество задач

        # Рисуем горизонтальную линию после каждой строки
        draw.line([(0, max_y + 5), (width, max_y + 5)], fill=line_color, width=1)

        y_offset = max_y + 10  # Переход на новую строку с дополнительным отступом

    # Сохранение изображения
    image_path = "detailed_task_status_report.png"
    image.save(image_path)
    logger.info(f"Изображение сохранено: {image_path}")

    return image_path




async def get_topic_names(db_session):
    """
    Получаем все темы в формате словаря {id_топика: название_топика}.
    """
    result = await db_session.execute(select(Topic.id, Topic.name))
    topics = {row[0]: row[1] for row in result.fetchall()}
    return topics