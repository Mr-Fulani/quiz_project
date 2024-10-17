import logging
import os
import re
import tempfile
from functools import partial
from typing import Optional

from PIL import Image, ImageDraw
from dotenv import load_dotenv
from pygments import highlight
from pygments.lexers import PythonLexer, JavaLexer, SqlLexer, GoLexer
from pygments.formatters import ImageFormatter
from pygments.styles import get_style_by_name
import textwrap
import io

import asyncio
from concurrent.futures import ThreadPoolExecutor

from bot.services.s3_services import save_image_to_storage
from database.models import Task



# Загружаем переменные окружения из файла .env
load_dotenv()



# Настройка логгера
logger = logging.getLogger(__name__)



logo_path = os.getenv('LOGO_PATH', '/default/path/to/logo.png')



KEYWORDS = {
    'python': r"\b(if|for|def|class|while|else|elif|try|except|finally|with|return|pass)\b",
    'java': r"\b(if|for|public|class|private|try|catch|finally|return|new|else)\b",
    'golang': r"\b(func|for|if|else|return|defer|go|select|case|break)\b",
    'sql': r"\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|JOIN|ON|GROUP BY|ORDER BY)\b"
}




async def generate_image_with_executor(task_text, language, logo_path=None):
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor()

    # Выполняем блокирующую операцию в отдельном потоке
    image_generation_fn = partial(generate_console_image, task_text, language, logo_path)
    image = await loop.run_in_executor(executor, image_generation_fn)

    # Освобождаем ресурсы
    executor.shutdown(wait=True)

    return image





async def generate_image_if_needed(task: Task) -> Optional[str]:
    """
    Асинхронная генерация изображения для задачи, используя перевод, если изображение ещё не было сгенерировано.

    :param task: Объект задачи Task
    :return: URL сгенерированного изображения или None, если не удалось сгенерировать
    """
    try:
        # Проверяем, было ли уже сгенерировано изображение
        if task.image_url:
            logger.info(f"Изображение для задачи с ID {task.id} уже сгенерировано.")
            return task.image_url

        # Ищем перевод на 'ru', если его нет, берем первый доступный перевод
        translation = next((t for t in task.translations if t.language == 'ru'), None)
        if not translation:
            # Если нет перевода на 'ru', пытаемся взять любой доступный перевод
            translation = task.translations[0] if task.translations else None

        if not translation or not translation.question:
            raise ValueError(f"Перевод задачи с ID {task.id} не найден или отсутствует вопрос.")

        task_text = translation.question  # Используем поле 'question' из перевода

        # Генерация изображения с использованием run_in_executor для избежания блокировки
        logger.info(f"Генерация изображения для задачи с ID {task.id}")
        image = await generate_image_with_executor(task_text, 'python', logo_path)

        # Формируем имя файла для изображения на основе темы, подтемы и ID задачи (для SEO)
        image_name = f"{task.topic.name}_{task.subtopic.name if task.subtopic else 'general'}_{task.id}.png".replace(" ", "_").lower()

        # Асинхронное сохранение изображения в облачное хранилище (например, S3)
        image_url = await save_image_to_storage(image, image_name)

        if not image_url:
            logger.error(f"Ошибка при сохранении изображения для задачи с ID {task.id}.")
            raise ValueError(f"Не удалось сохранить изображение для задачи с ID {task.id} в облако.")

        # Обновляем задачу с URL изображения
        task.image_url = image_url
        logger.info(f"Изображение для задачи с ID {task.id} успешно сгенерировано и сохранено.")
        return image_url

    except Exception as e:
        logger.error(f"Ошибка при генерации изображения для задачи с ID {task.id}: {e}")
        return None



def add_indentation(task_text: str, language: str) -> str:
    if language not in KEYWORDS:
        raise ValueError(f"Язык {language} не поддерживается.")

    keywords = KEYWORDS[language]
    lines = task_text.split('\n')
    indented_lines = []
    indent_level = 0

    for i, line in enumerate(lines):
        stripped_line = line.strip()

        # Проверяем, является ли текущая строка началом нового блока
        is_block_start = re.search(keywords, stripped_line) and stripped_line.endswith((':'))

        # Уменьшаем отступ для закрывающих конструкций
        if stripped_line in ('}', 'else:', 'elif:', 'except:', 'finally:'):
            indent_level = max(0, indent_level - 1)

        # Добавляем отступы
        indented_line = '    ' * indent_level + stripped_line
        indented_lines.append(indented_line)

        # Увеличиваем отступ после открывающих конструкций
        if is_block_start:
            # Проверяем, есть ли содержимое блока на следующей строке
            if i + 1 < len(lines) and lines[i + 1].strip():
                indent_level += 1

        # Обрабатываем случай с одиночными командами без отступа (например, вложенный def)
        elif stripped_line.startswith(('def', 'class')) and not is_block_start:
            # Не увеличиваем отступ, так как это отдельная конструкция
            pass

    return '\n'.join(indented_lines)










def wrap_text(task_text: str, max_line_length: int = 60) -> str:
    wrapped_lines = []
    for line in task_text.split('\n'):
        if len(line) > max_line_length:
            wrapped_lines.extend(textwrap.wrap(line, max_line_length,
                                               subsequent_indent='    ',
                                               break_long_words=False,
                                               replace_whitespace=False))
        else:
            wrapped_lines.append(line)
    return '\n'.join(wrapped_lines)

def get_lexer(language: str):
    lexers = {
        'python': PythonLexer,
        'java': JavaLexer,
        'golang': GoLexer,
        'sql': SqlLexer
    }

    if language not in lexers:
        raise ValueError(f"Лексер для {language} не поддерживается.")

    return lexers[language]()





def generate_console_image(task_text: str, language: str, logo_path: Optional[str] = None) -> Image.Image:
    """
    Генерирует изображение консоли с подсвеченным кодом задачи и логотипом.

    :param task_text: Текст задачи (код).
    :param language: Язык программирования задачи ('python', 'java', 'golang', 'sql').
    :param logo_path: Путь к логотипу (опционально).
    :return: Объект изображения PIL с отрисованной консолью и кодом.
    """

    # Размеры изображения и консольного окна
    width, height = 800, 500
    console_width, console_height = 700, 350

    # Создаем изображение с фоном светло-синего цвета
    background_color = (173, 216, 230)
    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    # Цвета для "кнопок" и консоли
    red, yellow, green = (255, 59, 48), (255, 204, 0), (40, 205, 65)
    console_color = (40, 40, 40)
    corner_radius = 20

    # Позиционирование консоли
    console_x0 = (width - console_width) // 2
    console_y0 = (height - console_height) // 2
    console_x1 = console_x0 + console_width
    console_y1 = console_y0 + console_height

    # Отрисовка консоли со скругленными углами
    draw.rounded_rectangle((console_x0, console_y0, console_x1, console_y1), radius=corner_radius, fill=console_color)

    # Отрисовка "кнопок" в верхнем левом углу консоли
    circle_radius = 10
    circle_spacing = 15
    circle_y = console_y0 + 15
    for i, color in enumerate([red, yellow, green]):
        draw.ellipse((console_x0 + (2 * i + 1) * circle_spacing,
                      circle_y,
                      console_x0 + (2 * i + 1) * circle_spacing + 2 * circle_radius,
                      circle_y + 2 * circle_radius),
                     fill=color)

    # Добавление логотипа в правый верхний угол (если есть)
    if logo_path:
        try:
            logo = Image.open(logo_path)
            logo.thumbnail((80, 80))
            if logo.mode != 'RGBA':
                logo = logo.convert("RGBA")
            logo_x = width - logo.width - 20
            logo_y = 20
            image.paste(logo, (logo_x, logo_y), logo)
        except Exception as e:
            print(f"Ошибка при загрузке логотипа: {e}")

    # Форматирование и вывод кода на консоль
    task_text_with_indent = task_text.strip()
    padding_left = 40
    padding_top = 40
    max_code_width = console_width - (padding_left + 20)
    max_code_height = console_height - (padding_top + 30)

    font_size = 20
    code_img = None
    while font_size >= 8:
        # Создаем форматтер для подсветки кода
        lexer = get_lexer(language)
        formatter = ImageFormatter(
            font_size=font_size,
            style=get_style_by_name('monokai'),
            line_numbers=False,
            image_pad=10,
            line_pad=5,
            background_color='transparent'
        )

        # Используем буфер для создания изображения
        code_image_io = io.BytesIO()
        highlight(task_text_with_indent, lexer, formatter, outfile=code_image_io)
        code_image_io.seek(0)
        code_img = Image.open(code_image_io).convert("RGBA")

        if code_img.width <= max_code_width and code_img.height <= max_code_height:
            break

        font_size -= 1

    # Вставляем изображение кода в консоль
    if code_img:
        code_x = console_x0 + padding_left
        code_y = console_y0 + padding_top
        image.paste(code_img, (code_x, code_y), code_img)

    return image







# def save_and_show_image(image: Image.Image, filename: str = "console_image.png"):
#     image.save(filename)
#     image.show()
#
#
#
# if __name__ == "__main__":
#     task_text = """
# def hello_world():
#     if True:
#         print("Hello, World!")
#     for i in range(5):
#         def inner_function():
#             pass
#     print("End of hello_world")
#     """
#     language = 'python'
#     logo_path = '/Users/user/telegram_quiz_bots/quiz_project/bot/assets/logo.png'  # Путь к логотипу
#     image = generate_console_image(task_text, language, logo_path)
#     save_and_show_image(image)