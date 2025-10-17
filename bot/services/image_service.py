# image_service.py

import asyncio
import io
import logging
import os
import re
import subprocess
import textwrap
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Optional, Tuple

from PIL import Image, ImageDraw
from PIL.Image import Resampling
from dotenv import load_dotenv
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import PythonLexer, JavaLexer, SqlLexer, GoLexer, get_lexer_by_name, TextLexer
from pygments.styles import get_style_by_name

from bot.services.s3_services import save_image_to_storage
from bot.database.models import Task

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

logo_path = os.getenv('LOGO_PATH', '/default/path/to/logo.png')


# ============================================================================
# ИЗВЛЕЧЕНИЕ КОДА ИЗ MARKDOWN БЛОКОВ
# ============================================================================

def extract_code_from_markdown(text: str) -> Tuple[str, str]:
    """
    Извлекает код из markdown блоков вида ```language\ncode\n```
    
    Returns:
        (code, language) - извлеченный код и определенный язык
    """
    # Паттерн для markdown блоков кода (закрытых)
    pattern = r'```(\w+)?\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    if matches:
        # Берем первый блок кода
        language, code = matches[0]
        language = language.strip() if language else 'python'
        code = code.strip()
        logger.info(f"✅ Извлечен код из markdown блока, язык: {language}")
        return code, language
    
    # Попытка найти незакрытый блок кода
    open_pattern = r'```(\w+)?\n(.*)'
    open_matches = re.findall(open_pattern, text, re.DOTALL)
    
    if open_matches:
        # Берем первый незакрытый блок
        language, code = open_matches[0]
        language = language.strip() if language else 'python'
        code = code.strip()
        logger.info(f"✅ Извлечен код из незакрытого markdown блока, язык: {language}")
        return code, language
    
    # Если markdown блоков нет, возвращаем весь текст
    logger.debug("Markdown блоки кода не найдены, используется весь текст")
    return text.strip(), 'python'


# ============================================================================
# УМНОЕ ФОРМАТИРОВАНИЕ КОДА - ГЛАВНОЕ УЛУЧШЕНИЕ
# ============================================================================

def format_python_code(code: str) -> str:
    """
    Форматирование Python с приоритетом: black > autopep8 > базовое
    """
    # Попытка 1: black (самый надёжный)
    try:
        import black
        mode = black.Mode(
            line_length=79,
            string_normalization=False,
            is_pyi=False,
        )
        formatted = black.format_str(code, mode=mode)
        logger.info("✅ Использован black для форматирования")
        return formatted
    except ImportError:
        logger.debug("black не установлен")
    except Exception as e:
        logger.warning(f"black не смог отформатировать: {e}")
    
    # Попытка 2: autopep8
    try:
        import autopep8
        formatted = autopep8.fix_code(
            code,
            options={
                'max_line_length': 79,
                'aggressive': 2,
                'experimental': True,
            }
        )
        logger.info("✅ Использован autopep8 для форматирования")
        return formatted
    except ImportError:
        logger.debug("autopep8 не установлен")
    except Exception as e:
        logger.warning(f"autopep8 не смог отформатировать: {e}")
    
    # Попытка 3: базовое форматирование (безопасное)
    logger.info("⚠️ Использовано базовое форматирование для Python")
    return safe_basic_format(code)


def format_javascript_typescript(code: str) -> str:
    """
    Форматирование JS/TS через prettier или базовое
    """
    # Попытка 1: prettier (если установлен Node.js)
    try:
        result = subprocess.run(
            ['npx', '--yes', 'prettier', '--stdin-filepath', 'code.js'],
            input=code.encode(),
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            logger.info("✅ Использован prettier для JS/TS")
            return result.stdout.decode()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.debug("prettier недоступен (npx не найден или timeout)")
    except Exception as e:
        logger.warning(f"prettier ошибка: {e}")
    
    # Базовое форматирование
    logger.info("⚠️ Использовано базовое форматирование для JS/TS")
    return format_curly_braces_language(code)


def format_java_code(code: str) -> str:
    """
    Форматирование Java через улучшенное базовое форматирование
    """
    return format_curly_braces_language(code)


def format_csharp_code(code: str) -> str:
    """
    Форматирование C# через улучшенное базовое форматирование
    """
    return format_curly_braces_language(code)


def format_golang_code(code: str) -> str:
    """
    Форматирование Go через gofmt
    """
    try:
        result = subprocess.run(
            ['gofmt'],
            input=code.encode(),
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            logger.info("✅ Использован gofmt")
            return result.stdout.decode()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.debug("gofmt недоступен")
    except Exception as e:
        logger.warning(f"gofmt ошибка: {e}")
    
    logger.info("⚠️ Использовано базовое форматирование для Go")
    return format_curly_braces_language(code)


def format_rust_code(code: str) -> str:
    """
    Форматирование Rust через rustfmt
    """
    try:
        result = subprocess.run(
            ['rustfmt', '--emit', 'stdout'],
            input=code.encode(),
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            logger.info("✅ Использован rustfmt")
            return result.stdout.decode()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.debug("rustfmt недоступен")
    except Exception as e:
        logger.warning(f"rustfmt ошибка: {e}")
    
    logger.info("⚠️ Использовано базовое форматирование для Rust")
    return format_curly_braces_language(code)


def format_sql_code(code: str) -> str:
    """
    Форматирование SQL через sqlparse
    """
    try:
        import sqlparse
        formatted = sqlparse.format(
            code,
            reindent=True,
            keyword_case='upper',
            indent_width=4
        )
        logger.info("✅ Использован sqlparse")
        return formatted
    except ImportError:
        logger.debug("sqlparse не установлен")
    except Exception as e:
        logger.warning(f"sqlparse ошибка: {e}")
    
    logger.info("⚠️ SQL код оставлен без изменений")
    return code


def format_curly_braces_language(code: str) -> str:
    """
    УЛУЧШЕННОЕ базовое форматирование для языков со скобками { }
    Работает для: Java, C++, C#, JavaScript, TypeScript, Go, Swift, Kotlin
    """
    lines = code.split('\n')
    formatted = []
    indent = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            formatted.append('')
            continue
        
        # Определяем отступ для текущей строки
        current_indent = indent
        
        # Уменьшаем отступ ПЕРЕД строкой с }
        if stripped.startswith('}'):
            current_indent = max(0, indent - 1)
        
        # Добавляем строку с правильным отступом
        formatted.append('    ' * current_indent + stripped)
        
        # Обновляем отступ для следующих строк
        # Считаем открывающие и закрывающие скобки
        opening = stripped.count('{')
        closing = stripped.count('}')
        indent += opening - closing
        indent = max(0, indent)  # Не даём стать отрицательным
    
    return '\n'.join(formatted)


def safe_basic_format(code: str) -> str:
    """
    Безопасное базовое форматирование - не ломает код
    Просто убирает лишние пробелы, сохраняя структуру
    """
    lines = code.split('\n')
    formatted = []
    
    for line in lines:
        # Убираем trailing пробелы, но сохраняем структуру
        if line.strip():
            formatted.append(line.rstrip())
        else:
            formatted.append('')
    
    return '\n'.join(formatted)


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ ФОРМАТИРОВАНИЯ - ВЫБИРАЕТ ЛУЧШИЙ МЕТОД
# ============================================================================

def smart_format_code(code: str, language: str) -> str:
    """
    Умное форматирование кода в зависимости от языка.
    Динамически выбирает лучший доступный форматтер.
    """
    code = code.strip()
    
    # Нормализуем название языка
    lang = language.lower().strip()
    
    # Маппинг языков на функции форматирования
    formatters = {
        'python': format_python_code,
        'py': format_python_code,
        
        'javascript': format_javascript_typescript,
        'js': format_javascript_typescript,
        'typescript': format_javascript_typescript,
        'ts': format_javascript_typescript,
        'jsx': format_javascript_typescript,
        'tsx': format_javascript_typescript,
        'react': format_javascript_typescript,
        'vue': format_javascript_typescript,
        'angular': format_javascript_typescript,
        
        'java': format_java_code,
        
        'c#': format_csharp_code,
        'csharp': format_csharp_code,
        'cs': format_csharp_code,
        
        'c++': format_curly_braces_language,
        'cpp': format_curly_braces_language,
        'c': format_curly_braces_language,
        
        'go': format_golang_code,
        'golang': format_golang_code,
        
        'rust': format_rust_code,
        'rs': format_rust_code,
        
        'php': format_curly_braces_language,
        
        'sql': format_sql_code,
        'mysql': format_sql_code,
        'postgresql': format_sql_code,
        'postgres': format_sql_code,
        
        'swift': format_curly_braces_language,
        'kotlin': format_curly_braces_language,
        'scala': format_curly_braces_language,
        'dart': format_curly_braces_language,
    }
    
    # Выбираем форматтер
    formatter_func = formatters.get(lang, safe_basic_format)
    
    try:
        formatted = formatter_func(code)
        # Проверяем что форматирование сработало
        if formatted and formatted.strip():
            return formatted
    except Exception as e:
        logger.error(f"Ошибка форматирования {language}: {e}")
    
    # Если всё упало - возвращаем безопасную версию
    logger.warning(f"Использован fallback форматтер для {language}")
    return safe_basic_format(code)


# ============================================================================
# УСТАРЕВШИЕ ФУНКЦИИ - СОХРАНЕНЫ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
# ============================================================================

def fix_python_indentation(code: str) -> str:
    """
    Исправляет неправильные отступы в Python коде.
    Автоматически определяет правильный уровень отступа для каждой строки.
    """
    lines = code.split('\n')
    fixed_lines = []
    indent_stack = [0]  # Стек уровней отступов
    
    for i, line in enumerate(lines):
        if not line.strip():
            fixed_lines.append('')
            continue
        
        stripped = line.strip()
        
        # Определяем, нужно ли изменить уровень отступа
        current_indent = indent_stack[-1]
        
        # Ключевые слова, которые уменьшают отступ
        dedent_keywords = ['elif', 'else', 'except', 'finally']
        should_dedent = any(stripped.startswith(kw) for kw in dedent_keywords)
        
        if should_dedent and len(indent_stack) > 1:
            indent_stack.pop()
            current_indent = indent_stack[-1]
        
        # Проверяем, была ли предыдущая строка с увеличением отступа
        if i > 0:
            prev_line = lines[i - 1].strip()
            # Если предыдущая строка заканчивается на : (def, if, for, etc.)
            if prev_line.endswith(':') and not prev_line.startswith('#'):
                # Увеличиваем отступ для текущей строки
                indent_stack.append(current_indent + 1)
                current_indent = indent_stack[-1]
            # Если предыдущая строка - return/break/continue/pass/raise в блоке
            elif any(prev_line.startswith(kw) for kw in ['return', 'break', 'continue', 'pass', 'raise']):
                # Проверяем, нужно ли уменьшить отступ
                # Если текущая строка - не часть того же блока
                if not stripped.startswith(('elif', 'else', 'except', 'finally')):
                    # Возвращаемся на предыдущий уровень отступа
                    if len(indent_stack) > 1:
                        indent_stack.pop()
                        current_indent = indent_stack[-1]
        
        # Применяем отступ
        fixed_lines.append('    ' * current_indent + stripped)
    
    return '\n'.join(fixed_lines)


def format_sql_basic(code: str) -> str:
    """
    Базовое форматирование SQL запросов.
    """
    # Ключевые слова SQL в верхний регистр
    keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 
                'OUTER', 'ON', 'GROUP BY', 'ORDER BY', 'HAVING', 'INSERT', 
                'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'AS', 'AND', 'OR']
    
    formatted = code
    for keyword in keywords:
        pattern = re.compile(r'\b' + keyword + r'\b', re.IGNORECASE)
        formatted = pattern.sub(keyword, formatted)
    
    return formatted


def basic_code_format(code: str) -> str:
    """
    Базовое форматирование для языков без специализированных форматтеров.
    Просто нормализует отступы и удаляет лишние пустые строки.
    """
    lines = code.split('\n')
    formatted_lines = []
    
    for line in lines:
        # Убираем trailing whitespace
        line = line.rstrip()
        if line:  # Пропускаем только совсем пустые строки
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)


def wrap_text(task_text: str, max_line_length: int = 79) -> str:
    """
    Принудительный перенос строк, превышающих max_line_length символов.
    """
    wrapped_lines = []
    for line in task_text.split('\n'):
        if len(line) > max_line_length:
            # Пытаемся разбить по пробелам
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
    """
    Автоматическое определение лексера Pygments для любого языка
    Поддержка alias и популярных вариантов написания
    """
    # Нормализуем название
    lang = language.lower().strip()
    
    # Маппинг популярных названий на имена лексеров Pygments
    lexer_aliases = {
        'py': 'python',
        'js': 'javascript',
        'ts': 'typescript',
        'jsx': 'jsx',
        'tsx': 'tsx',
        'golang': 'go',
        'cs': 'csharp',
        'c#': 'csharp',
        'c++': 'cpp',
        'rs': 'rust',
        'rb': 'ruby',
        'kt': 'kotlin',
        'react': 'jsx',
        'vue': 'vue',
        'angular': 'typescript',
        'mysql': 'mysql',
        'postgresql': 'postgresql',
        'postgres': 'postgresql',
        'dart': 'dart',
        'scala': 'scala',
        'swift': 'swift',
        'php': 'php',
    }
    
    # Преобразуем alias в название лексера
    lexer_name = lexer_aliases.get(lang, lang)
    
    try:
        lexer = get_lexer_by_name(lexer_name)
        logger.debug(f"✅ Найден лексер: {lexer_name}")
        return lexer
    except Exception as e:
        logger.warning(f"⚠️ Лексер для {language} не найден, используется text: {e}")
        return TextLexer()


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
        
        # Извлекаем код из markdown блоков и определяем язык
        code, detected_language = extract_code_from_markdown(task_text)
        
        # Если язык не определён из markdown, используем topic
        if detected_language == 'python' and task.topic:
            topic_name = task.topic.name.lower()
            # Пытаемся использовать topic как fallback для языка
            detected_language = topic_name if topic_name in ['python', 'java', 'javascript', 'go', 'golang', 'rust', 'sql'] else 'python'

        logger.info(f"Генерация изображения для задачи с ID {task.id}, язык: {detected_language}")
        image = await generate_image_with_executor(code, detected_language, logo_path)

        return image

    except Exception as e:
        logger.error(f"Ошибка при генерации изображения для задачи с ID {task.id}: {e}")
        return None


def generate_console_image(task_text: str, language: str, logo_path: Optional[str] = None) -> Image.Image:
    """
    Генерация «консольного» изображения с подсветкой кода/текста и логотипом.
    Использует умное форматирование и нумерацию строк.
    """
    # 🔥 КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: используем умное форматирование
    formatted_text = smart_format_code(task_text, language)
    
    # Дополнительно оборачиваем длинные строки если нужно
    formatted_text = wrap_text(formatted_text, max_line_length=79)

    # Минимальные размеры
    MIN_WIDTH, MIN_HEIGHT = 1600, 1000
    MIN_CONSOLE_WIDTH, MIN_CONSOLE_HEIGHT = 1400, 700

    lexer = get_lexer(language)

    # Начинаем с более крупного шрифта
    font_size = 50
    code_img = None
    while font_size >= 24:
        formatter = ImageFormatter(
            font_size=font_size,
            style=get_style_by_name('monokai'),
            line_numbers=True,  # 🔥 ВКЛЮЧЕНА НУМЕРАЦИЯ СТРОК
            line_number_start=1,
            line_number_fg='#888888',
            line_number_bg='#272822',  # Цвет фона из темы monokai
            image_pad=20,
            line_pad=10,
            background_color='#272822'  # Цвет фона из темы monokai
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
            logger.info(f"✅ Выбран размер шрифта: {font_size}")
            break

        font_size -= 2

    if code_img is None:
        code_img = tmp_code_img

    console_width = max(MIN_CONSOLE_WIDTH, code_img.width + 160)
    console_height = max(MIN_CONSOLE_HEIGHT, code_img.height + 240)
    width = max(MIN_WIDTH, console_width + 300)
    height = max(MIN_HEIGHT, console_height + 300)

    background_color = (173, 216, 230)
    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    red, yellow, green = (255, 59, 48), (255, 204, 0), (40, 205, 65)
    console_color = (40, 40, 40)
    corner_radius = 40

    console_x0 = (width - console_width) // 2
    console_y0 = (height - console_height) // 2
    console_x1 = console_x0 + console_width
    console_y1 = console_y0 + console_height

    draw.rounded_rectangle(
        (console_x0, console_y0, console_x1, console_y1),
        radius=corner_radius,
        fill=console_color
    )

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





# # image_service.py

# import asyncio
# import io
# import logging
# import os
# import re
# import textwrap
# from concurrent.futures import ThreadPoolExecutor
# from functools import partial
# from typing import Optional

# from PIL import Image, ImageDraw
# from PIL.Image import Resampling
# from dotenv import load_dotenv
# from pygments import highlight
# from pygments.formatters import ImageFormatter
# from pygments.lexers import PythonLexer, JavaLexer, SqlLexer, GoLexer
# from pygments.styles import get_style_by_name

# from bot.services.s3_services import save_image_to_storage
# from bot.database.models import Task

# # Загружаем переменные окружения из файла .env
# load_dotenv()

# # Настройка логгера
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

# if not logger.handlers:
#     handler = logging.StreamHandler()
#     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     handler.setFormatter(formatter)
#     logger.addHandler(handler)

# logo_path = os.getenv('LOGO_PATH', '/default/path/to/logo.png')

# KEYWORDS = {
#     'python': r"\b(if|for|def|class|while|else|elif|try|except|finally|with|return|pass)\b",
#     'java': r"\b(if|for|public|class|private|try|catch|finally|return|new|else)\b",
#     'golang': r"\b(func|for|if|else|return|defer|go|select|case|break)\b",
#     'sql': r"\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|JOIN|ON|GROUP BY|ORDER BY)\b",
#     'javascript': r"\b(function|if|else|for|while|return|var|let|const|class|try|catch|finally)\b",
#     'c++': r"\b(if|else|for|while|class|struct|try|catch|return|namespace|template)\b",
#     'c#': r"\b(if|else|for|while|class|public|private|protected|return|namespace|try|catch|finally)\b",
#     'php': r"\b(if|else|foreach|while|function|class|public|private|protected|return|try|catch)\b",
#     'rust': r"\b(fn|let|if|else|for|while|loop|match|return|impl|struct|enum|trait)\b"
# }


# async def generate_image_with_executor(task_text, language, logo_path=None):
#     loop = asyncio.get_event_loop()
#     executor = ThreadPoolExecutor()

#     image_generation_fn = partial(generate_console_image, task_text, language, logo_path)
#     image = await loop.run_in_executor(executor, image_generation_fn)

#     executor.shutdown(wait=True)
#     return image


# async def generate_image_if_needed(task: Task, user_chat_id: int) -> Optional[Image.Image]:
#     try:
#         if task.image_url:
#             logger.info(f"Изображение для задачи с ID {task.id} уже сгенерировано.")
#             return None

#         translation = next((t for t in task.translations if t.language == 'ru'), None)
#         if not translation:
#             translation = task.translations[0] if task.translations else None

#         if not translation or not translation.question:
#             raise ValueError(f"Перевод задачи с ID {task.id} не найден или отсутствует вопрос.")

#         task_text = translation.question

#         logger.info(f"Генерация изображения для задачи с ID {task.id}")
#         image = await generate_image_with_executor(task_text, 'python', logo_path)

#         return image

#     except Exception as e:
#         logger.error(f"Ошибка при генерации изображения для задачи с ID {task.id}: {e}")
#         return None


# def add_indentation(task_text: str, language: str) -> str:
#     """
#     Опциональная функция для расстановки отступов по ключевым словам, если это необходимо.
#     Если требуется просто переносить текст, данную функцию можно отключить.
#     """
#     if language not in KEYWORDS:
#         return task_text  # или ValueError, если строго нужно обрабатывать только поддерживаемые языки

#     keywords = KEYWORDS[language]
#     lines = task_text.split('\n')
#     indented_lines = []
#     indent_level = 0

#     for i, line in enumerate(lines):
#         stripped_line = line.strip()
#         is_block_start = re.search(keywords, stripped_line) and stripped_line.endswith(':')

#         # Уменьшаем отступ для закрывающих конструкций
#         if stripped_line in ('}', 'else:', 'elif:', 'except:', 'finally:'):
#             indent_level = max(0, indent_level - 1)

#         # Добавляем отступы
#         indented_line = '    ' * indent_level + stripped_line
#         indented_lines.append(indented_line)

#         # Пример добавления пустой строки после return
#         if stripped_line.startswith('return'):
#             if i + 1 < len(lines) and lines[i + 1].strip():
#                 indented_lines.append('')

#         # Увеличиваем отступ после открывающих конструкций
#         if is_block_start:
#             if i + 1 < len(lines) and lines[i + 1].strip():
#                 indent_level += 1

#         elif stripped_line.startswith(('def', 'class')) and not is_block_start:
#             pass

#     return '\n'.join(indented_lines)


# def wrap_text(task_text: str, max_line_length: int = 60) -> str:
#     """
#     Принудительный перенос строк, превышающих max_line_length символов,
#     чтобы избежать слишком длинных строк (например, по рекомендациям PEP8).
#     """
#     wrapped_lines = []
#     for line in task_text.split('\n'):
#         if len(line) > max_line_length:
#             wrapped_lines.extend(
#                 textwrap.wrap(
#                     line,
#                     max_line_length,
#                     subsequent_indent='    ',
#                     break_long_words=False,
#                     replace_whitespace=False
#                 )
#             )
#         else:
#             wrapped_lines.append(line)
#     return '\n'.join(wrapped_lines)


# def get_lexer(language: str):
#     lexers = {
#         'python': PythonLexer,
#         'java': JavaLexer,
#         'golang': GoLexer,
#         'sql': SqlLexer
#     }
#     if language not in lexers:
#         # Если хотим без подсветки, можно вернуть PythonLexer или PlainTextLexer
#         return PythonLexer()
#     return lexers[language]()


# def generate_console_image(task_text: str, language: str, logo_path: Optional[str] = None) -> Image.Image:
#     """
#     Генерация «консольного» изображения с подсветкой кода/текста и логотипом.
#     """
#     # Сначала опционально расставляем отступы
#     formatted_text = add_indentation(task_text, language)
#     # Затем ограничиваем длину строки PEP8-стилем (79 символов)
#     formatted_text = wrap_text(formatted_text, max_line_length=79)

#     # Минимальные размеры
#     MIN_WIDTH, MIN_HEIGHT = 1600, 1000
#     MIN_CONSOLE_WIDTH, MIN_CONSOLE_HEIGHT = 1400, 700

#     lexer = get_lexer(language)

#     # Начинаем с более крупного шрифта, чем раньше
#     font_size = 50
#     code_img = None
#     while font_size >= 24:  # минимальный шрифт увеличили с 20 до 24
#         formatter = ImageFormatter(
#             font_size=font_size,
#             style=get_style_by_name('monokai'),
#             line_numbers=False,
#             image_pad=20,
#             line_pad=10,
#             background_color='transparent'
#         )
#         code_image_io = io.BytesIO()
#         highlight(formatted_text.strip(), lexer, formatter, outfile=code_image_io)
#         code_image_io.seek(0)
#         tmp_code_img = Image.open(code_image_io).convert("RGBA")

#         console_width = max(MIN_CONSOLE_WIDTH, tmp_code_img.width + 160)
#         console_height = max(MIN_CONSOLE_HEIGHT, tmp_code_img.height + 240)
#         width = max(MIN_WIDTH, console_width + 300)
#         height = max(MIN_HEIGHT, console_height + 300)

#         if (tmp_code_img.width <= (console_width - 160)
#                 and tmp_code_img.height <= (console_height - 240)):
#             code_img = tmp_code_img
#             logger.info(f"Selected font size: {font_size}")
#             break

#         font_size -= 2

#     # Если вообще не поместилось, берём последнее (самое маленькое) изображение
#     if code_img is None:
#         code_img = tmp_code_img

#     console_width = max(MIN_CONSOLE_WIDTH, code_img.width + 160)
#     console_height = max(MIN_CONSOLE_HEIGHT, code_img.height + 240)
#     width = max(MIN_WIDTH, console_width + 300)
#     height = max(MIN_HEIGHT, console_height + 300)

#     background_color = (173, 216, 230)
#     image = Image.new("RGB", (width, height), background_color)
#     draw = ImageDraw.Draw(image)

#     # Цвета и параметры "окна"
#     red, yellow, green = (255, 59, 48), (255, 204, 0), (40, 205, 65)
#     console_color = (40, 40, 40)
#     corner_radius = 40

#     console_x0 = (width - console_width) // 2
#     console_y0 = (height - console_height) // 2
#     console_x1 = console_x0 + console_width
#     console_y1 = console_y0 + console_height

#     # Рисуем "консоль" со скруглёнными углами
#     draw.rounded_rectangle(
#         (console_x0, console_y0, console_x1, console_y1),
#         radius=corner_radius,
#         fill=console_color
#     )

#     # "Кнопки" в верхнем левом углу
#     circle_radius = 20
#     circle_spacing = 30
#     circle_y = console_y0 + 40
#     for i, color in enumerate([red, yellow, green]):
#         draw.ellipse((
#             console_x0 + (2 * i + 1) * circle_spacing,
#             circle_y,
#             console_x0 + (2 * i + 1) * circle_spacing + 2 * circle_radius,
#             circle_y + 2 * circle_radius
#         ), fill=color)

#     # Логотип в правом верхнем углу, если указан
#     if logo_path:
#         try:
#             logo = Image.open(logo_path).convert("RGBA")
#             fixed_logo_size = (240, 240)
#             logo = logo.resize(fixed_logo_size, Resampling.LANCZOS)
#             logo_x = width - logo.width - 30
#             logo_y = 10
#             image.paste(logo, (logo_x, logo_y), logo)
#         except Exception as e:
#             logger.error(f"Ошибка при загрузке логотипа: {e}")

#     # Вставляем подготовленное "изображение кода" (или текста) внутрь консоли
#     shift_left = 50
#     padding_left = (console_width - code_img.width) // 2 - shift_left
#     padding_top = 150
#     code_x = console_x0 + padding_left
#     code_y = console_y0 + padding_top
#     image.paste(code_img, (code_x, code_y), code_img)


#     return image


# def save_and_show_image(image: Image.Image, filename: str = "console_image.png"):
#     image.save(filename, format='PNG', dpi=(300, 300))
#     image.show()







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
