# image_service.py

import asyncio
import io
import logging
import os
import re
import textwrap
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Optional

from PIL import Image, ImageDraw
from PIL.Image import Resampling
from dotenv import load_dotenv
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import PythonLexer, JavaLexer, SqlLexer, GoLexer
from pygments.styles import get_style_by_name

from bot.services.s3_services import save_image_to_storage
from bot.database.models import Task

# Загружаем переменные окружения из файла .env
load_dotenv()

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

logo_path = os.getenv('LOGO_PATH', '/default/path/to/logo.png')

KEYWORDS = {
    'python': r"\b(if|for|def|class|while|else|elif|try|except|finally|with|return|pass)\b",
    'java': r"\b(if|for|public|class|private|try|catch|finally|return|new|else)\b",
    'golang': r"\b(func|for|if|else|return|defer|go|select|case|break)\b",
    'sql': r"\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|JOIN|ON|GROUP BY|ORDER BY)\b",
    'javascript': r"\b(function|if|else|for|while|return|var|let|const|class|try|catch|finally)\b",
    'c++': r"\b(if|else|for|while|class|struct|try|catch|return|namespace|template)\b",
    'c#': r"\b(if|else|for|while|class|public|private|protected|return|namespace|try|catch|finally)\b",
    'php': r"\b(if|else|foreach|while|function|class|public|private|protected|return|try|catch)\b",
    'rust': r"\b(fn|let|if|else|for|while|loop|match|return|impl|struct|enum|trait)\b"
}


async def generate_image_with_executor(task_text, language, logo_path=None):
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor()

    image_generation_fn = partial(generate_console_image, task_text, language, logo_path)
    image = await loop.run_in_executor(executor, image_generation_fn)

    executor.shutdown(wait=True)
    return image


async def generate_image_if_needed(task: Task, user_chat_id: int) -> Optional[Image.Image]:
    try:
        if task.image_url:
            logger.info(f"Изображение для задачи с ID {task.id} уже сгенерировано.")
            return None

        translation = next((t for t in task.translations if t.language == 'ru'), None)
        if not translation:
            translation = task.translations[0] if task.translations else None

        if not translation or not translation.question:
            raise ValueError(f"Перевод задачи с ID {task.id} не найден или отсутствует вопрос.")

        task_text = translation.question

        logger.info(f"Генерация изображения для задачи с ID {task.id}")
        image = await generate_image_with_executor(task_text, 'python', logo_path)

        return image

    except Exception as e:
        logger.error(f"Ошибка при генерации изображения для задачи с ID {task.id}: {e}")
        return None


def add_indentation(task_text: str, language: str) -> str:
    """
    Опциональная функция для расстановки отступов по ключевым словам, если это необходимо.
    Если требуется просто переносить текст, данную функцию можно отключить.
    """
    if language not in KEYWORDS:
        return task_text  # или ValueError, если строго нужно обрабатывать только поддерживаемые языки

    keywords = KEYWORDS[language]
    lines = task_text.split('\n')
    indented_lines = []
    indent_level = 0

    for i, line in enumerate(lines):
        stripped_line = line.strip()
        is_block_start = re.search(keywords, stripped_line) and stripped_line.endswith(':')

        # Уменьшаем отступ для закрывающих конструкций
        if stripped_line in ('}', 'else:', 'elif:', 'except:', 'finally:'):
            indent_level = max(0, indent_level - 1)

        # Добавляем отступы
        indented_line = '    ' * indent_level + stripped_line
        indented_lines.append(indented_line)

        # Пример добавления пустой строки после return
        if stripped_line.startswith('return'):
            if i + 1 < len(lines) and lines[i + 1].strip():
                indented_lines.append('')

        # Увеличиваем отступ после открывающих конструкций
        if is_block_start:
            if i + 1 < len(lines) and lines[i + 1].strip():
                indent_level += 1

        elif stripped_line.startswith(('def', 'class')) and not is_block_start:
            pass

    return '\n'.join(indented_lines)


def wrap_text(task_text: str, max_line_length: int = 60) -> str:
    """
    Принудительный перенос строк, превышающих max_line_length символов,
    чтобы избежать слишком длинных строк (например, по рекомендациям PEP8).
    """
    wrapped_lines = []
    for line in task_text.split('\n'):
        if len(line) > max_line_length:
            wrapped_lines.extend(
                textwrap.wrap(
                    line,
                    max_line_length,
                    subsequent_indent='    ',
                    break_long_words=False,
                    replace_whitespace=False
                )
            )
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
        # Если хотим без подсветки, можно вернуть PythonLexer или PlainTextLexer
        return PythonLexer()
    return lexers[language]()


def generate_console_image(task_text: str, language: str, logo_path: Optional[str] = None) -> Image.Image:
    """
    Генерация «консольного» изображения с подсветкой кода/текста и логотипом.
    """
    # Сначала опционально расставляем отступы
    formatted_text = add_indentation(task_text, language)
    # Затем ограничиваем длину строки PEP8-стилем (79 символов)
    formatted_text = wrap_text(formatted_text, max_line_length=79)

    # Минимальные размеры
    MIN_WIDTH, MIN_HEIGHT = 1600, 1000
    MIN_CONSOLE_WIDTH, MIN_CONSOLE_HEIGHT = 1400, 700

    lexer = get_lexer(language)

    # Начинаем с более крупного шрифта, чем раньше
    font_size = 50
    code_img = None
    while font_size >= 24:  # минимальный шрифт увеличили с 20 до 24
        formatter = ImageFormatter(
            font_size=font_size,
            style=get_style_by_name('monokai'),
            line_numbers=False,
            image_pad=20,
            line_pad=10,
            background_color='transparent'
        )
        code_image_io = io.BytesIO()
        highlight(formatted_text.strip(), lexer, formatter, outfile=code_image_io)
        code_image_io.seek(0)
        tmp_code_img = Image.open(code_image_io).convert("RGBA")

        console_width = max(MIN_CONSOLE_WIDTH, tmp_code_img.width + 160)
        console_height = max(MIN_CONSOLE_HEIGHT, tmp_code_img.height + 240)
        width = max(MIN_WIDTH, console_width + 300)
        height = max(MIN_HEIGHT, console_height + 300)

        if (tmp_code_img.width <= (console_width - 160)
                and tmp_code_img.height <= (console_height - 240)):
            code_img = tmp_code_img
            logger.info(f"Selected font size: {font_size}")
            break

        font_size -= 2

    # Если вообще не поместилось, берём последнее (самое маленькое) изображение
    if code_img is None:
        code_img = tmp_code_img

    console_width = max(MIN_CONSOLE_WIDTH, code_img.width + 160)
    console_height = max(MIN_CONSOLE_HEIGHT, code_img.height + 240)
    width = max(MIN_WIDTH, console_width + 300)
    height = max(MIN_HEIGHT, console_height + 300)

    background_color = (173, 216, 230)
    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    # Цвета и параметры "окна"
    red, yellow, green = (255, 59, 48), (255, 204, 0), (40, 205, 65)
    console_color = (40, 40, 40)
    corner_radius = 40

    console_x0 = (width - console_width) // 2
    console_y0 = (height - console_height) // 2
    console_x1 = console_x0 + console_width
    console_y1 = console_y0 + console_height

    # Рисуем "консоль" со скруглёнными углами
    draw.rounded_rectangle(
        (console_x0, console_y0, console_x1, console_y1),
        radius=corner_radius,
        fill=console_color
    )

    # "Кнопки" в верхнем левом углу
    circle_radius = 20
    circle_spacing = 30
    circle_y = console_y0 + 40
    for i, color in enumerate([red, yellow, green]):
        draw.ellipse((
            console_x0 + (2 * i + 1) * circle_spacing,
            circle_y,
            console_x0 + (2 * i + 1) * circle_spacing + 2 * circle_radius,
            circle_y + 2 * circle_radius
        ), fill=color)

    # Логотип в правом верхнем углу, если указан
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            fixed_logo_size = (240, 240)
            logo = logo.resize(fixed_logo_size, Resampling.LANCZOS)
            logo_x = width - logo.width - 30
            logo_y = 10
            image.paste(logo, (logo_x, logo_y), logo)
        except Exception as e:
            logger.error(f"Ошибка при загрузке логотипа: {e}")

    # Вставляем подготовленное "изображение кода" (или текста) внутрь консоли
    shift_left = 50
    padding_left = (console_width - code_img.width) // 2 - shift_left
    padding_top = 150
    code_x = console_x0 + padding_left
    code_y = console_y0 + padding_top
    image.paste(code_img, (code_x, code_y), code_img)


    return image


def save_and_show_image(image: Image.Image, filename: str = "console_image.png"):
    image.save(filename, format='PNG', dpi=(300, 300))
    image.show()







# if __name__ == "__main__":
#     task_text = """
# def hello_world():
#     print("Hello, World!") print("Hello, World!") print("Hello, World!")print("Hello, World!")print("Hello, World!") print("Hello, World!") print("Hello, World!")print("Hello, World!")print("Hello, World!") print("Hello, World!") print("Hello, World!")print("Hello, World!")
# def hello_world():
#     print("Hello, World!")
# def hello_world():
#     print("Hello, World!")
# def hello_world():
#     print("Hello, World!")
# def hello_world():
#     print("Hello, World!")
#     return
#     return
# def hello_world():
#     print("Hello, World!")
#
#     """
#     language = 'python'
#     logo_path = '/Users/user/telegram_quiz_bots/quiz_project/bot/assets/logo.png'  # Путь к логотипу
#
#     # Форматирование текста перед генерацией изображения
#     formatted_text = add_indentation(task_text, language)
#     formatted_text = wrap_text(formatted_text, max_line_length=80)  # Увеличенное значение для больших изображений
#
#     image = generate_console_image(formatted_text, language, logo_path)
#     save_and_show_image(image)
#
#     if __name__ == "__main__":
#         test_text = """
#     def hello_world():
#         print("Hello, World!")
#         return
#
#     def long_function_name(argument1, argument2, argument3, argument4, argument5, argument6):
#         if argument1 and argument2:
#             print("This is a long function with many arguments and logic.")
#         else:
#             print("Short branch.")
#         return
#         """
#
#         test_language = 'python'
#         test_logo_path = logo_path  # или укажи вручную путь
#
#         image = generate_console_image(test_text, test_language, test_logo_path)
#
#         # Проверка размеров
#         print(f"Image size: {image.size}")
#         print(f"Aspect ratio: {image.size[0] / image.size[1]:.2f}")
#
#         save_and_show_image(image, "test_output.png")
