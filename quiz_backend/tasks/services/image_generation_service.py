"""
Сервис генерации изображений с кодом для задач.
Портирован из bot/services/image_service.py.
"""
import io
import logging
import os
import re
import subprocess
import textwrap
from typing import Tuple, Optional

from PIL import Image, ImageDraw
from PIL.Image import Resampling
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.styles import get_style_by_name
from django.conf import settings

logger = logging.getLogger(__name__)


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
# УМНОЕ ФОРМАТИРОВАНИЕ КОДА
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
# ГЛАВНАЯ ФУНКЦИЯ ФОРМАТИРОВАНИЯ
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
        
        'go': format_golang_code,
        'golang': format_golang_code,
        
        'sql': format_sql_code,
        'mysql': format_sql_code,
        'postgresql': format_sql_code,
        
        'java': format_curly_braces_language,
        'c#': format_curly_braces_language,
        'csharp': format_curly_braces_language,
        'c++': format_curly_braces_language,
        'cpp': format_curly_braces_language,
        'swift': format_curly_braces_language,
        'kotlin': format_curly_braces_language,
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
    """
    # Нормализуем название
    lang = language.lower().strip()
    
    # Маппинг популярных названий на имена лексеров Pygments
    lexer_aliases = {
        'py': 'python',
        'js': 'javascript',
        'ts': 'typescript',
        'golang': 'go',
        'cs': 'csharp',
        'c#': 'csharp',
        'c++': 'cpp',
        'mysql': 'mysql',
        'postgresql': 'postgresql',
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


def generate_console_image(task_text: str, language: str, logo_path: Optional[str] = None) -> Image.Image:
    """
    Генерация «консольного» изображения с подсветкой кода/текста и логотипом.
    Использует умное форматирование и нумерацию строк.
    """
    # Умное форматирование кода
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
            line_numbers=True,
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

    if logo_path and os.path.exists(logo_path):
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


def generate_image_for_task(task_question: str, topic_name: str) -> Optional[Image.Image]:
    """
    Генерирует изображение для задачи, автоматически определяя язык программирования.
    
    Args:
        task_question: Текст вопроса задачи (может содержать markdown блоки кода)
        topic_name: Название темы (например, 'Python', 'JavaScript')
        
    Returns:
        PIL Image объект или None при ошибке
    """
    try:
        # Извлекаем код из markdown блоков и определяем язык
        code, detected_language = extract_code_from_markdown(task_question)
        
        # Если язык не определён из markdown, используем topic
        if detected_language == 'python' and topic_name:
            topic_lower = topic_name.lower()
            # Пытаемся использовать topic как fallback для языка
            if topic_lower in ['python', 'java', 'javascript', 'go', 'golang', 'rust', 'sql']:
                detected_language = topic_lower

        logger.info(f"Генерация изображения, язык: {detected_language}")
        
        # Получаем путь к логотипу из настроек
        logo_path = getattr(settings, 'LOGO_PATH', None)
        
        image = generate_console_image(code, detected_language, logo_path)
        return image
        
    except Exception as e:
        logger.error(f"Ошибка при генерации изображения: {e}")
        return None

