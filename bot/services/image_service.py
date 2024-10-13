import re
from PIL import Image, ImageDraw
from pygments import highlight
from pygments.lexers import PythonLexer, JavaLexer, SqlLexer, GoLexer
from pygments.formatters import ImageFormatter
from pygments.styles import get_style_by_name
import textwrap
import io



KEYWORDS = {
    'python': r"\b(if|for|def|class|while|else|elif|try|except|finally|with|return)\b",
    'java': r"\b(if|for|public|class|private|try|catch|finally|return|new|else)\b",
    'golang': r"\b(func|for|if|else|return|defer|go|select|case|break)\b",
    'sql': r"\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|JOIN|ON|GROUP BY|ORDER BY)\b"
}

def add_indentation(task_text: str, language: str) -> str:
    if language not in KEYWORDS:
        raise ValueError(f"Язык {language} не поддерживается.")

    keywords = KEYWORDS[language]
    lines = task_text.split('\n')
    indented_lines = []
    indent_level = 0

    for line in lines:
        stripped_line = line.strip()

        # Проверка на ключевые слова и добавление отступов
        if re.search(keywords, stripped_line) and not stripped_line.endswith((':', '{')):
            indented_lines.append('    ' * indent_level + stripped_line)
            indent_level += 1
        elif stripped_line.endswith((':', '{')):
            indented_lines.append('    ' * indent_level + stripped_line)
            indent_level += 1
        elif stripped_line in ('}', 'else:', 'elif', 'except', 'finally:'):
            indent_level = max(0, indent_level - 1)
            indented_lines.append('    ' * indent_level + stripped_line)
        else:
            indented_lines.append('    ' * indent_level + stripped_line)

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


def generate_console_image(task_text: str, language: str, logo_path: str = None) -> Image.Image:
    width, height = 800, 500
    console_width, console_height = 700, 350

    background_color = (173, 216, 230)
    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    red, yellow, green = (255, 59, 48), (255, 204, 0), (40, 205, 65)
    console_color = (40, 40, 40)
    corner_radius = 20

    console_x0 = (width - console_width) // 2
    console_y0 = (height - console_height) // 2
    console_x1 = console_x0 + console_width
    console_y1 = console_y0 + console_height

    draw.rounded_rectangle((console_x0, console_y0, console_x1, console_y1), radius=corner_radius, fill=console_color)

    circle_radius = 10
    circle_spacing = 15
    circle_y = console_y0 + 15

    for i, color in enumerate([red, yellow, green]):
        draw.ellipse((console_x0 + (2 * i + 1) * circle_spacing,
                      circle_y,
                      console_x0 + (2 * i + 1) * circle_spacing + 2 * circle_radius,
                      circle_y + 2 * circle_radius),
                     fill=color)

    # Добавление логотипа в правый верхний угол
    if logo_path:
        try:
            logo = Image.open(logo_path)
            logo.thumbnail((80, 80))  # Изменяем размер логотипа

            # Проверяем, есть ли альфа-канал (прозрачность)
            if logo.mode != 'RGBA':
                logo = logo.convert("RGBA")

            # Создаем альфа-слой для правильного наложения логотипа
            logo_x = width - logo.width - 20  # Позиция X для логотипа (20 пикселей отступа)
            logo_y = 20  # Позиция Y для логотипа (отступ сверху)

            # Вставляем лого с учетом альфа-канала
            image.paste(logo, (logo_x, logo_y), logo)
        except Exception as e:
            print(f"Ошибка при загрузке логотипа: {e}")


    task_text_with_indent = add_indentation(task_text.strip(), language)

    # Определяем максимальные размеры для кода
    padding_left = 40
    padding_top = 40
    max_code_width = console_width - (padding_left + 20)  # 20 пикселей отступа справа
    max_code_height = console_height - (padding_top + 30)  # 30 пикселей отступа снизу

    # Начинаем с размера шрифта 16 и уменьшаем его, пока текст не поместится
    font_size = 20
    while font_size >= 8:  # Минимальный размер шрифта 8
        wrapped_task_text = wrap_text(task_text_with_indent, max_line_length=int(max_code_width / (font_size * 0.6)))

        lexer = get_lexer(language)
        code_image = highlight(
            wrapped_task_text,
            lexer,
            ImageFormatter(
                font_size=font_size,
                style=get_style_by_name('monokai'),
                line_numbers=False,
                image_pad=10,
                line_pad=5,
                background_color='transparent'
            )
        )

        code_img = Image.open(io.BytesIO(code_image)).convert("RGBA")

        if code_img.width <= max_code_width and code_img.height <= max_code_height:
            break

        font_size -= 1

    # Вычисляем позицию для вставки кода
    code_x = console_x0 + padding_left
    code_y = console_y0 + padding_top

    # Вставляем текст с прозрачным фоном
    image.paste(code_img, (code_x, code_y), code_img)

    return image

def save_and_show_image(image: Image.Image, filename: str = "console_image.png"):
    image.save(filename)
    image.show()



if __name__ == "__main__":
    task_text = """
def hello_world():
    if True:
        print("Hello, World!")
    for i in range(5):
def hello_world()
    """
    language = 'python'
    logo_path = '/Users/user/telegram_quiz_bots/quiz_project/bot/assets/logo.png'  # Путь к логотипу
    image = generate_console_image(task_text, language, logo_path)
    save_and_show_image(image)