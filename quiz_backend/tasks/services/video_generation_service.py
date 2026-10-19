"""
Сервис генерации видео из кода для задач.
Создает видео в формате reels (9:16, 1080x1920) с анимацией появления кода.
"""
import gc
import io
import logging
import os
import random
import re
import tempfile
import uuid
import textwrap
from pathlib import Path
from typing import Optional, List
import numpy as np

from PIL import Image, ImageDraw, ImageFont
from PIL.Image import Resampling
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.styles import get_style_by_name
from django.conf import settings
from django.core.files.storage import default_storage
from tenants.scoping import site_url_for

# Импортируем функции из image_generation_service для переиспользования
from .image_generation_service import (
    extract_code_from_markdown,
    smart_format_code,
    wrap_text,
    get_lexer
)

logger = logging.getLogger(__name__)


def sanitize_filename(text: str, max_length: int = 100) -> str:
    """
    Очищает строку для использования в имени файла.
    Удаляет специальные символы, оставляет только буквы, цифры, дефисы и подчеркивания.
    
    Args:
        text: Исходная строка
        max_length: Максимальная длина результата
        
    Returns:
        Очищенная строка, пригодная для имени файла
    """
    if not text:
        return ""
    
    # Заменяем пробелы и специальные символы на подчеркивания
    text = re.sub(r'[^\w\s-]', '', text)  # Удаляем все кроме букв, цифр, пробелов, дефисов и подчеркиваний
    text = re.sub(r'[\s_-]+', '_', text)  # Заменяем пробелы и множественные подчеркивания на одно
    text = text.strip('_-')  # Удаляем подчеркивания и дефисы с краев
    
    # Ограничиваем длину
    if len(text) > max_length:
        text = text[:max_length].rstrip('_-')
    
    return text.lower()


def _get_keyboard_audio_path() -> Optional[str]:
    """
    Возвращает путь к аудиофайлу со звуком клавиатуры, если он существует.

    Returns:
        Путь к аудиофайлу или None если файл не найден
    """
    # Сначала проверяем настройку KEYBOARD_AUDIO_PATH
    audio_path = getattr(settings, 'KEYBOARD_AUDIO_PATH', None)
    if audio_path and os.path.exists(audio_path):
        return audio_path

    # Затем проверяем в static директории
    base_dir = settings.BASE_DIR
    static_audio_path = base_dir / 'tasks' / 'static' / 'tasks' / 'keyboard_sounds' / 'keyboard_typing.wav'
    if static_audio_path.exists():
        return str(static_audio_path)

    # Пробуем mp3 версию
    static_audio_path_mp3 = base_dir / 'tasks' / 'static' / 'tasks' / 'keyboard_sounds' / 'keyboard_typing.mp3'
    if static_audio_path_mp3.exists():
        return str(static_audio_path_mp3)

    return None


def _get_background_audio_path() -> Optional[str]:
    """
    Возвращает источник фоновой музыки.

    Возможные варианты возврата:
      - None: не найден трек
      - экземпляр BackgroundMusic: если в БД найдена активная запись (будет обработана через storage)
      - локальный путь (str): если найден файл на диске через BACKGROUND_AUDIO_PATH или static
    """
    try:
        # Попытка использовать записи из БД — предпочтительный вариант
        from ..models import BackgroundMusic
        candidates = BackgroundMusic.objects.filter(is_active=True)
        if candidates.exists():
            # Выбираем случайную активную запись
            bgm = random.choice(list(candidates))
            logger.info(f"🎵 Выбран фон из БД: {bgm.name} (id={bgm.id})")
            return bgm
    except Exception as e:
        # Если что-то не так с доступом к БД — логируем и продолжаем fallback
        logger.debug(f"Не удалось получить BackgroundMusic из БД: {e}")

    # Фоллбек на настройку BACKGROUND_AUDIO_PATH (локальный путь)
    audio_path = getattr(settings, 'BACKGROUND_AUDIO_PATH', None)
    if audio_path and os.path.exists(audio_path):
        return str(audio_path)

    # Затем ищем все аудиофайлы в директории background_music
    base_dir = settings.BASE_DIR
    background_dir = base_dir / 'tasks' / 'static' / 'tasks' / 'background_music'

    if not background_dir.exists():
        return None

    # Поддерживаемые форматы аудио
    supported_extensions = ['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac']

    # Находим все аудиофайлы
    audio_files = []
    for ext in supported_extensions:
        audio_files.extend(background_dir.glob(f'*.{ext}'))

    # Если файлы найдены, выбираем случайный
    if audio_files:
        selected_file = random.choice(audio_files)
        logger.info(f"🎵 Выбрана фоновая музыка (static): {selected_file.name}")
        return str(selected_file)

    return None


def _generate_console_frame_vertical(
    formatted_code_text: str,
    language: str,
    visible_chars: int,
    logo_path: Optional[str] = None,
    question_text: str = "Каким будет результат кода?",
    frame_index: int = 0
) -> Image.Image:
    """
    Генерирует кадр консоли с кодом в вертикальном формате (9:16, 1080x1920).
    Показывает только первые visible_chars символов кода.
    
    Args:
        formatted_code_text: УЖЕ ОТФОРМАТИРОВАННЫЙ текст кода (не форматируем повторно!)
        language: Язык программирования
        visible_chars: Количество видимых символов от начала кода
        logo_path: Путь к логотипу (опционально)
        question_text: Текст вопроса внизу экрана (по умолчанию "Каков результат кода?")
        
    Returns:
        PIL Image объект кадра
    """
    # Получаем размеры видео из настроек
    video_width = getattr(settings, 'VIDEO_WIDTH', 1080)
    video_height = getattr(settings, 'VIDEO_HEIGHT', 1920)
    
    # Отступ между консолью и текстом вопроса
    question_text_gap = 30
    question_text_height = 100
    
    # Вырезаем видимую часть кода (код уже отформатирован)
    # Убеждаемся, что последний кадр покажет весь код
    if visible_chars >= len(formatted_code_text):
        # Показываем весь код
        visible_code = formatted_code_text
    else:
        # Показываем код посимвольно для плавной анимации печати
        visible_code = formatted_code_text[:visible_chars]
    
    # Пустые строки уже добавлены в formatted_code перед генерацией кадров
    # Здесь мы только обрезаем код до visible_chars, но сохраняем пустые строки если они есть
    # Если код обрезан, проверяем, есть ли пустые строки в конце
    if not visible_code.endswith('\n\n'):
        # Если пустые строки были обрезаны, добавляем их обратно
        visible_code = visible_code.rstrip('\n')
        visible_code += '\n\n'
    
    # Настройки для вертикального формата (размеры консоли для вертикального экрана)
    MIN_CONSOLE_WIDTH = 950  # Уменьшено чтобы поместилось на экране
    MIN_CONSOLE_HEIGHT = 1000  # Минимальная высота, но будет увеличиваться если код длиннее
    MAX_CONSOLE_HEIGHT = video_height - 300  # Максимальная высота с учетом текста вопроса и отступов
    
    lexer = get_lexer(language)
    
    # Подбираем размер шрифта для вертикального формата (увеличен для лучшей читаемости)
    font_size = 55
    code_img = None
    while font_size >= 35:  # Минимум увеличен до 35 чтобы не было слишком мелко
        formatter = ImageFormatter(
            font_size=font_size,
            style=get_style_by_name('monokai'),
            line_numbers=True,
            line_number_start=1,
            line_number_fg='#888888',
            line_number_bg='#272822',
            image_pad=8,  # Уменьшено с 15 до 8 для большего размера кода
            line_pad=4,   # Уменьшено с 8 до 4 для большего размера кода
            background_color='#272822'
        )
        code_image_io = io.BytesIO()
        # НЕ используем rstrip() - передаем код как есть, с пустыми строками в конце
        # Pygments должен сохранить пустые строки
        highlight(visible_code, lexer, formatter, outfile=code_image_io)
        code_image_io.seek(0)
        tmp_code_img = Image.open(code_image_io).convert("RGBA")
        
        # Проверяем, помещается ли изображение кода в консоль (уменьшены отступы для большего размера)
        max_code_width = MIN_CONSOLE_WIDTH - 120  # Уменьшено с 160 до 120
        # Используем динамическую высоту вместо фиксированной MIN_CONSOLE_HEIGHT
        max_code_height = video_height - 400  # Оставляем место для текста вопроса и отступов
        
        if tmp_code_img.width <= max_code_width and tmp_code_img.height <= max_code_height:
            code_img = tmp_code_img
            break
        
        font_size -= 2
    
    if code_img is None:
        code_img = tmp_code_img
        # Не масштабируем код - пусть консоль увеличивается по высоте
        # Масштабируем только по ширине если код слишком широкий
        max_code_width = MIN_CONSOLE_WIDTH - 120
        if code_img.width > max_code_width:
            scale = max_code_width / code_img.width
            new_width = int(code_img.width * scale)
            new_height = int(code_img.height * scale)
            # Создаем новое изображение вместо изменения существующего
            new_code_img = code_img.resize((new_width, new_height), Resampling.LANCZOS)
            code_img.close()  # Закрываем старое изображение
            code_img = new_code_img
            logger.debug(f"Код масштабирован по ширине: {code_img.width}x{code_img.height}")
    else:
        # Если code_img был присвоен из tmp_code_img, закрываем tmp_code_img
        if 'tmp_code_img' in locals() and tmp_code_img != code_img:
            tmp_code_img.close()
    
    # Рассчитываем ширину консоли (но не больше ширины экрана)
    max_console_width = video_width - 100  # Оставляем отступы по бокам
    console_width = min(max_console_width, max(MIN_CONSOLE_WIDTH, code_img.width + 140))
    
    # Пустые строки уже добавлены в formatted_code и должны быть отрендерены Pygments с номерами строк
    # Проверяем, что пустые строки присутствуют в коде
    code_lines = visible_code.split('\n')
    num_lines = len(code_lines)
    
    # Логируем информацию о коде (только для первого кадра)
    if frame_index == 0:
        logger.info(f"📊 Код содержит {num_lines} строк, заканчивается на: {repr(visible_code[-20:])}")
        logger.info(f"📏 Высота изображения кода после рендеринга: {code_img.height}px")
    
    # ВАЖНО: Рассчитываем высоту консоли ПОСЛЕ добавления пустых строк
    # Сначала рассчитываем необходимую высоту консоли на основе кода и отступов
    padding_top = 100  # Отступ сверху, чтобы код был ниже
    bottom_padding = 70  # Отступ снизу, такой же как сверху для симметрии
    needed_height = code_img.height + padding_top + bottom_padding
    # НЕ используем MIN_CONSOLE_HEIGHT - консоль должна быть ровно такой, какая нужна
    console_height = needed_height
    
    # Создаем изображение фона
    background_color = (173, 216, 230)
    image = Image.new("RGB", (video_width, video_height), background_color)
    draw = ImageDraw.Draw(image)
    
    # Цвета для кнопок окна
    red, yellow, green = (255, 59, 48), (255, 204, 0), (40, 205, 65)
    console_color = (40, 40, 40)
    corner_radius = 30
    
    # Центрируем консоль вертикально, оставляя место для текста вопроса снизу
    console_x0 = (video_width - console_width) // 2
    # Размещаем консоль выше, чтобы под ней было место для текста вопроса
    # Высота текста вопроса примерно 70px + gap 40px = 110px
    question_text_height = 80
    top_margin = 50  # Отступ сверху от края экрана
    bottom_margin = 50  # Отступ снизу от края экрана (такой же как сверху)
    available_height = video_height - question_text_height - question_text_gap - top_margin - bottom_margin
    console_y0 = top_margin + (available_height - console_height) // 2  # Симметричные отступы сверху и снизу
    console_x1 = console_x0 + console_width
    console_y1 = console_y0 + console_height
    
    # Рисуем консоль
    draw.rounded_rectangle(
        (console_x0, console_y0, console_x1, console_y1),
        radius=corner_radius,
        fill=console_color
    )
    
    # Рисуем кнопки окна
    circle_radius = 15
    circle_spacing = 25
    circle_y = console_y0 + 30
    for i, color in enumerate([red, yellow, green]):
        draw.ellipse((
            console_x0 + (2 * i + 1) * circle_spacing,
            circle_y,
            console_x0 + (2 * i + 1) * circle_spacing + 2 * circle_radius,
            circle_y + 2 * circle_radius
        ), fill=color)
    
    # Добавляем логотип если есть (опускаем ниже, ближе к консоли)
    if logo_path:
        # Проверяем существование файла несколькими способами
        logo_exists = os.path.exists(logo_path) or Path(logo_path).exists()
        if logo_exists:
            try:
                logo = Image.open(logo_path).convert("RGBA")
                logo_size = (180, 180)  # Меньше для вертикального формата
                logo = logo.resize(logo_size, Resampling.LANCZOS)
                logo_x = video_width - logo.width - 20
                # Размещаем логотип ближе к консоли (примерно на уровне верхнего края консоли)
                logo_y = max(console_y0 - logo.height - 30, 50)  # На 30px выше консоли, минимум 50px от верха
                image.paste(logo, (logo_x, logo_y), logo)
            except Exception as e:
                logger.error(f"Ошибка при загрузке логотипа: {e}")
    
    # Вставляем код в консоль
    shift_left = 40
    padding_left = (console_width - code_img.width) // 2 - shift_left
    code_x = console_x0 + padding_left
    code_y = console_y0 + padding_top
    
    # Перерисовываем консоль с точной высотой
    draw.rounded_rectangle(
        (console_x0, console_y0, console_x1, console_y1),
        radius=corner_radius,
        fill=console_color
    )
    # Перерисовываем кнопки
    for i, color in enumerate([red, yellow, green]):
        draw.ellipse((
            console_x0 + (2 * i + 1) * circle_spacing,
            circle_y,
            console_x0 + (2 * i + 1) * circle_spacing + 2 * circle_radius,
            circle_y + 2 * circle_radius
        ), fill=color)
    
    # Вставляем код в консоль - ВЕСЬ код должен быть виден, включая пустые строки
    image.paste(code_img, (code_x, code_y), code_img)
    
    # Добавляем текст вопроса прямо под консолью жирным шрифтом
    # Пытаемся загрузить жирный шрифт, если не получается - используем стандартный
    question_font_size = 45  # Немного уменьшен чтобы точно поместился
    font = None
    
    # Список возможных путей к жирным шрифтам (Linux/Docker)
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, question_font_size)
                break
            except Exception:
                continue
    
    # Если не нашли шрифт, используем стандартный
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            # Если даже стандартный не загружается, создаём минимальный шрифт
            font = ImageFont.load_default()
    
    # Цвет текста - тёмный для контраста на светлом фоне
    text_color = (30, 30, 30)
    
    # Разбиваем длинный текст на несколько строк с учетом ширины экрана
    max_text_width = video_width - 100  # Оставляем отступы по бокам
    line_spacing = 5  # Отступ между строками
    
    # Функция для разбиения текста на строки с учетом ширины
    def wrap_question_text(text: str, font: ImageFont, draw_obj: ImageDraw, max_width: int) -> List[str]:
        """Разбивает текст на строки, которые помещаются в max_width."""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            # Пробуем добавить слово к текущей строке
            test_line = ' '.join(current_line + [word])
            try:
                bbox = draw_obj.textbbox((0, 0), test_line, font=font)
                test_width = bbox[2] - bbox[0]
            except AttributeError:
                # Fallback для старых версий PIL - приблизительный расчет
                # Используем среднюю ширину символа (примерно 0.6 от размера шрифта)
                test_width = len(test_line) * question_font_size * 0.6
            
            if test_width <= max_width:
                current_line.append(word)
            else:
                # Текущая строка заполнена, начинаем новую
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        # Добавляем последнюю строку
        if current_line:
            lines.append(' '.join(current_line))
        
        # Если текст все еще не помещается (одно длинное слово), разбиваем по символам
        if not lines:
            # Разбиваем по символам, используя приблизительную ширину символа
            chars_per_line = int(max_width / (question_font_size * 0.6))
            if chars_per_line < 1:
                chars_per_line = 1
            lines = [text[i:i+chars_per_line] for i in range(0, len(text), chars_per_line)]
        
        return lines
    
    # Разбиваем текст на строки
    text_lines = wrap_question_text(question_text, font, draw, max_text_width)
    
    # Вычисляем общую высоту текста
    try:
        bbox = draw.textbbox((0, 0), "Ag", font=font)  # Используем тестовую строку для высоты
        line_height = bbox[3] - bbox[1]
    except AttributeError:
        line_height = question_font_size
    
    total_text_height = len(text_lines) * line_height + (len(text_lines) - 1) * line_spacing
    
    # Позиция текста: по центру горизонтально, прямо под консолью
    text_y = console_y1 + question_text_gap  # Прямо под консолью с отступом
    
    # Проверяем, чтобы текст не выходил за пределы экрана
    if text_y + total_text_height > video_height - 20:
        # Если текст выходит, сдвигаем выше
        text_y = video_height - total_text_height - 20
    
    # Рисуем каждую строку текста с небольшим контуром для читаемости (эффект жирного)
    outline_color = (255, 255, 255)
    for line_idx, line in enumerate(text_lines):
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
        except AttributeError:
            line_width = len(line) * question_font_size // 2
        
        line_x = (video_width - line_width) // 2
        line_y = text_y + line_idx * (line_height + line_spacing)
        
        # Рисуем контур
        for adj in [(-2, -2), (-2, 2), (2, -2), (2, 2), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            draw.text((line_x + adj[0], line_y + adj[1]), line, font=font, fill=outline_color)
        # Рисуем основной текст
        draw.text((line_x, line_y), line, font=font, fill=text_color)

    # Освобождаем память от изображений
    if 'logo' in locals():
        logo.close()
    if 'code_img' in locals():
        code_img.close()

    return image


def generate_code_typing_video(
    code: str,
    language: str,
    logo_path: Optional[str] = None,
    question_text: str = "Каким будет результат кода?",
    selected_bgm: Optional[object] = None,
) -> Optional[str]:
    """
    Создает видео с анимацией набора кода в формате reels (9:16, 1080x1920).
    
    Args:
        code: Текст кода для анимации
        language: Язык программирования
        logo_path: Путь к логотипу (опционально)
        question_text: Текст вопроса для отображения внизу экрана
        selected_bgm: Экземпляр BackgroundMusic или путь к аудиофайлу (опционально)

    Returns:
        Путь к временному файлу видео или None при ошибке
    """
    try:
        # Проверяем наличие MoviePy
        try:
            from moviepy.editor import ImageSequenceClip, AudioFileClip, CompositeVideoClip
        except ImportError:
            logger.error("MoviePy не установлен. Установите: pip install moviepy imageio-ffmpeg")
            return None
        
        # Получаем настройки
        typing_speed = getattr(settings, 'VIDEO_TYPING_SPEED', 25)  # символов в секунду (побуквенное печатание)
        fps = getattr(settings, 'VIDEO_FPS', 24)
        # Максимальная длительность видео в секундах. По умолчанию 30s — можно переопределить через settings.MAX_VIDEO_DURATION
        max_video_duration = getattr(settings, 'MAX_VIDEO_DURATION', 30)

        # Форматируем код ОДИН РАЗ перед генерацией кадров
        formatted_code = smart_format_code(code, language)
        # Обрезаем длинные строки для вертикального формата (45 символов для большего шрифта)
        formatted_code = wrap_text(formatted_code, max_line_length=50)
        # ВАЖНО: Добавляем две пустые строки в конец кода ПЕРЕД генерацией кадров
        # Это гарантирует, что Pygments их отрендерит с номерами строк
        formatted_code = formatted_code.rstrip('\n')  # Убираем все переносы в конце
        formatted_code += '\n\n'  # Добавляем точно две пустые строки
        total_chars = len(formatted_code)
        
        # Если код очень длинный — предварительно увеличиваем скорость, чтобы укладываться в max_video_duration
        # Это нужно сделать до расчёта количества кадров, чтобы избежать рассинхрона и деления на ноль.
        if total_chars > 0 and (total_chars / typing_speed) > max_video_duration:
            typing_speed = total_chars / max_video_duration
            logger.info(f"Код слишком длинный ({total_chars} символов), увеличена скорость набора до {typing_speed:.1f} символов/сек")

        # Рассчитываем количество кадров для печати с ограничением максимальной длительности
        typing_duration = min(total_chars / typing_speed if typing_speed > 0 else max_video_duration, max_video_duration)  # секунды на печать
        typing_frames = max(1, int(typing_duration * fps))  # гарантируем минимум 1 кадр, чтобы не было деления на ноль

        # Вычисляем паузу так, чтобы общее время было ровно max_video_duration
        pause_duration = max(0, max_video_duration - typing_duration)
        pause_frames = int(pause_duration * fps)

        # Общее количество кадров
        total_frames = typing_frames + pause_frames

        logger.info(f"Видео длительностью: max={max_video_duration}s, печать={typing_duration:.1f}s, пауза={pause_duration:.1f}s, fps={fps}, frames={total_frames}")

        # Создаем временную директорию для кадров
        # Используем TMPDIR из окружения или /app/tmp вместо /tmp для избежания проблем с правами доступа
        base_temp_dir = os.getenv('TMPDIR', '/app/tmp')
        try:
            os.makedirs(base_temp_dir, exist_ok=True)
            # Устанавливаем права доступа на директорию (rwxrwxrwx)
            os.chmod(base_temp_dir, 0o777)
        except PermissionError:
            # Если нет прав на /app/tmp, используем системную /tmp
            logger.warning(f"Нет прав на создание {base_temp_dir}, используем /tmp")
            base_temp_dir = '/tmp'
        temp_dir = tempfile.mkdtemp(dir=base_temp_dir)
        # Устанавливаем права доступа на созданную директорию
        try:
            os.chmod(temp_dir, 0o777)
        except PermissionError:
            logger.warning(f"Не удалось установить права на {temp_dir}, продолжаем")
        frame_paths = []
        
        # Генерируем кадры и сразу сохраняем на диск (не накапливаем в памяти)
        logger.info(f"Генерация {total_frames} кадров для видео (печать: {typing_frames}, пауза: {pause_frames})...")

        for frame_num in range(total_frames):
            # После завершения печати показываем весь код полностью
            if frame_num >= typing_frames:
                visible_chars = total_chars  # Весь код (пауза)
            else:
                # Пропорционально показываем код во время печати
                # Используем более плавную интерполяцию для побуквенного эффекта
                progress = (frame_num + 1) / typing_frames
                # Добавляем небольшую нелинейность для более естественного эффекта
                smooth_progress = progress ** 0.95  # слегка замедляем в конце
                visible_chars = max(1, int(smooth_progress * total_chars))
            frame = _generate_console_frame_vertical(formatted_code, language, visible_chars, logo_path, question_text, frame_num)
            
            # Сразу сохраняем кадр на диск
            frame_path = os.path.join(temp_dir, f"frame_{frame_num:06d}.png")
            frame.save(frame_path, 'PNG', optimize=True)
            frame_paths.append(frame_path)
            
            # Освобождаем память
            del frame
            gc.collect()  # Принудительная сборка мусора после каждого кадра
            
            # Прогресс каждые 50 кадров
            if (frame_num + 1) % 50 == 0:
                logger.info(f"Сгенерировано {frame_num + 1}/{total_frames} кадров...")
        
        logger.info(f"Создание видео из {len(frame_paths)} кадров...")
        
        # Создаем видео из кадров с оптимизацией памяти
        clip = ImageSequenceClip(frame_paths, fps=fps)

        # Оптимизация памяти и CPU для продакшена
        if os.getenv('DEBUG') != 'True':
            # Ограничиваем использование памяти MoviePy
            import moviepy.config as mp_config
            mp_config.MAX_MEMORY_CACHE = 512 * 1024 * 1024  # 512MB вместо дефолтных 2GB
            logger.info("Оптимизация памяти: MAX_MEMORY_CACHE=512MB")

            # Ограничиваем количество ядер CPU для стабильности
            # os уже импортирован в начале файла
            os.environ['MOVIEPY_NUM_THREADS'] = '1'
            logger.info("Оптимизация CPU: MOVIEPY_NUM_THREADS=1")
        
        # Добавляем аудио: фоновая музыка + звук клавиатуры
        # Если передан selected_bgm (экземпляр BackgroundMusic или путь) — используем его
        if selected_bgm:
            background_audio_path = selected_bgm
            try:
                if hasattr(selected_bgm, 'name'):
                    logger.info(f"🎵 Использован трек, переданный в функцию: {getattr(selected_bgm, 'name', str(selected_bgm))}")
                else:
                    logger.info(f"🎵 Использован трек, переданный в функцию: {str(selected_bgm)}")
            except Exception:
                logger.debug("Не удалось залогировать selected_bgm")
        else:
            background_audio_path = _get_background_audio_path()

        keyboard_audio_path = _get_keyboard_audio_path()

        logger.info(f"Поиск аудио: фон={background_audio_path}, клавиатура={keyboard_audio_path}")
        if background_audio_path:
            logger.info(f"Путь к фоновой музыке найден: {background_audio_path}")
        else:
            logger.warning("Путь к фоновой музыки НЕ найден")

        if background_audio_path or keyboard_audio_path:
            try:
                # Получаем настройки громкости
                background_volume = getattr(settings, 'BACKGROUND_AUDIO_VOLUME', 0.3)

                # Загружаем фоновую музыку (если есть)
                background_audio = None
                background_temp_path = None
                bgm_obj = None
                if background_audio_path:
                    try:
                        # Если background_audio_path — экземпляр модели BackgroundMusic
                        if hasattr(background_audio_path, 'audio_file'):
                            bgm_obj = background_audio_path
                            # Открываем файл через default_storage
                            logger.info(f"Загрузка фоновой музыки из storage для BackgroundMusic id={bgm_obj.id}")
                            try:
                                file_name = bgm_obj.audio_file.name
                                logger.info(f"Путь к файлу в storage: {file_name}")
                                logger.info(f"URL файла: {bgm_obj.audio_file.url}")
                                with default_storage.open(file_name, 'rb') as f:
                                    file_content = f.read()
                                    logger.info(f"Прочитано {len(file_content)} байт из storage")
                                    # создаём временный файл в temp_dir
                                    background_temp = tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, suffix=os.path.splitext(file_name)[1])
                                    background_temp.write(file_content)
                                    background_temp.flush()
                                    background_temp_path = background_temp.name
                                    background_temp.close()
                                    logger.info(f"Фоновая музыка сохранена во временный файл: {background_temp_path} (размер: {len(file_content)} байт)")
                                background_audio = AudioFileClip(background_temp_path)
                            except Exception as stor_err:
                                logger.error(f"Не удалось загрузить фон из storage: {stor_err}")
                                background_audio = None
                        else:
                            # background_audio_path — локальный путь
                            background_audio = AudioFileClip(str(background_audio_path))

                        if background_audio:
                            logger.info(f"Фоновая музыка загружена: длительность={background_audio.duration:.1f}сек")
                            # Обрезаем или зацикливаем до длительности видео
                            if background_audio.duration < clip.duration:
                                # В moviepy 1.0.3+ используем loop() с duration
                                try:
                                    background_audio = background_audio.loop(duration=clip.duration)
                                    logger.info(f"Фоновая музыка зациклена до длительности {clip.duration:.1f} сек")
                                except AttributeError as loop_error:
                                    # Fallback: используем concatenate_audioclips для зацикливания
                                    from moviepy.editor import concatenate_audioclips
                                    repeats = int(clip.duration // background_audio.duration) + 1
                                    clips = [background_audio] * repeats
                                    background_audio = concatenate_audioclips(clips).subclip(0, clip.duration)
                                    logger.info(f"Фоновая музыка зациклена через concatenate_audioclips: {repeats} раз")
                            else:
                                background_audio = background_audio.subclip(0, clip.duration)
                            # Устанавливаем громкость
                            try:
                                background_audio = background_audio.multiply_volume(background_volume)
                            except (AttributeError, Exception) as vol_error:
                                logger.warning(f"multiply_volume не сработал ({vol_error})")

                    except Exception as bg_error:
                        logger.error(f"Не удалось загрузить фоновую музыку {background_audio_path}: {bg_error}")
                        background_audio = None

                # Загружаем аудио клавиатуры (если есть)
                keyboard_audio = None
                if keyboard_audio_path:
                    try:
                        keyboard_audio = AudioFileClip(keyboard_audio_path)

                        # Рассчитываем длительность печати
                        typing_duration = typing_frames / fps  # секунды печати

                        # Обрезаем аудио до длительности печати
                        if keyboard_audio.duration > typing_duration:
                            keyboard_audio = keyboard_audio.subclip(0, typing_duration)
                        else:
                            logger.warning(f"Аудио клавиатуры короче чем нужно: {keyboard_audio.duration:.1f}сек вместо {typing_duration:.1f}сек")
                        logger.info(f"Аудио клавиатуры загружено: {keyboard_audio_path}")
                    except Exception as kb_error:
                        logger.warning(f"Не удалось загрузить аудио клавиатуры: {kb_error}")
                        keyboard_audio = None

                # Создаем финальное аудио
                final_audio = None

                if background_audio and keyboard_audio:
                    # Смешиваем фоновую музыку и звук клавиатуры
                    try:
                        from moviepy.audio.AudioClip import CompositeAudioClip
                        final_audio = CompositeAudioClip([background_audio, keyboard_audio])
                        logger.info("Аудио: фоновая музыка + звук клавиатуры (CompositeAudioClip)")
                    except Exception as mix_error:
                        logger.warning(f"CompositeAudioClip не сработал: {mix_error}, пробую простое сложение")
                        # Пробуем простое сложение аудио
                        try:
                            final_audio = background_audio + keyboard_audio
                            logger.info("Аудио: фоновая музыка + звук клавиатуры (простое сложение)")
                        except Exception as add_error:
                            logger.error(f"Простое сложение тоже не сработало: {add_error}")
                            final_audio = background_audio  # Используем только фоновую музыку

                elif background_audio:
                    # Только фоновая музыка
                    final_audio = background_audio
                    logger.info("Аудио: только фоновая музыка")
                elif keyboard_audio:
                    # Только звук клавиатуры (с тишиной в конце)
                    pause_duration_actual = pause_frames / fps  # секунды паузы
                    audio_fps = keyboard_audio.fps if hasattr(keyboard_audio, 'fps') and keyboard_audio.fps else 44100

                    # Создаем тишину для паузы
                    silence_samples = int(pause_duration_actual * audio_fps)
                    silence_array = np.zeros((silence_samples, 2))  # stereo silence

                    from moviepy.audio.AudioClip import AudioArrayClip
                    silence = AudioArrayClip(silence_array, fps=audio_fps)

                    # Объединяем: печать + тишина
                    from moviepy.audio.AudioClip import concatenate_audioclips
                    final_audio = concatenate_audioclips([keyboard_audio, silence])
                    logger.info("Аудио: звук клавиатуры + тишина")

                # Применяем финальное аудио к видео
                if final_audio:
                    logger.info(f"Применяю финальное аудио к видео: длительность аудио={final_audio.duration:.1f}сек, видео={clip.duration:.1f}сек")
                    clip = clip.set_audio(final_audio)
                    logger.info(f"Аудио добавлено к видео (длительность: {clip.duration:.1f}сек)")
                else:
                    logger.warning("Не удалось создать аудио для видео")

            except Exception as e:
                logger.error(f"Критическая ошибка при обработке аудио: {e}")
                logger.info("Видео будет создано без звука")
        else:
            logger.info("Аудиофайлы не найдены, создается видео без звука")
        
        # Экспортируем видео
        # Убеждаемся, что temp_dir существует и имеет правильные права
        try:
            os.makedirs(temp_dir, exist_ok=True)
            # Пытаемся установить права на temp_dir
            try:
                os.chmod(temp_dir, 0o777)
            except PermissionError:
                logger.warning(f"Не удалось установить права на {temp_dir}, продолжаем")
        except Exception as e:
            logger.error(f"Ошибка при создании/проверке {temp_dir}: {e}")
            raise
        
        # Сохраняем текущую рабочую директорию
        original_cwd = os.getcwd()
        
        # Устанавливаем TMPDIR для MoviePy явно перед вызовом
        old_tmpdir = os.environ.get('TMPDIR')
        os.environ['TMPDIR'] = temp_dir
        
        try:
            # Меняем рабочую директорию на temp_dir, чтобы MoviePy создавал временные файлы там
            os.chdir(temp_dir)
            
            # Используем относительный путь, так как мы уже в temp_dir
            output_filename = "output.mp4"
            
            # Параметры записи с оптимизацией для продакшена
            write_params = {
                'filename': output_filename,
                'fps': fps,
                'codec': 'libx264',
                'audio_codec': 'aac' if final_audio is not None else None,
                'preset': 'medium',
                'ffmpeg_params': ['-pix_fmt', 'yuv420p']
            }

            if os.getenv('DEBUG') != 'True':
                # Продакшен: меньше логов, стабильнее работа
                write_params['verbose'] = False
                write_params['threads'] = 1
                logger.info("Оптимизация записи: verbose=False, threads=1")

            clip.write_videofile(**write_params)
            
            # Получаем абсолютный путь к созданному файлу (пока мы еще в temp_dir)
            output_path = os.path.abspath(output_filename)
        finally:
            # Восстанавливаем рабочую директорию
            os.chdir(original_cwd)
            # Восстанавливаем TMPDIR
            if old_tmpdir:
                os.environ['TMPDIR'] = old_tmpdir
            elif 'TMPDIR' in os.environ:
                del os.environ['TMPDIR']
        
        # Очищаем временные файлы кадров
        for frame_path in frame_paths:
            try:
                os.remove(frame_path)
            except Exception:
                pass

        # Удаляем временный файл фоновой музыки, если был создан из storage
        try:
            if 'background_temp_path' in locals() and background_temp_path and os.path.exists(background_temp_path):
                os.remove(background_temp_path)
                logger.debug(f"🗑️ Удален временный фоновой файл: {background_temp_path}")
        except Exception:
            logger.warning("Не удалось удалить временный файл фоновой музыки")

        logger.info(f"✅ Видео создано: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Ошибка при создании видео: {e}", exc_info=True)
        return None


def generate_video_for_task(
    task_question: str,
    topic_name: str,
    subtopic_name: str = None,
    difficulty: str = None,
    admin_chat_id: str = None,
    task_id: int = None,
    video_language: str = 'ru',
    selected_bgm: Optional[object] = None,
) -> Optional[str]:
    """
    Генерирует видео для задачи в формате reels.

    Args:
        task_question: Текст вопроса задачи (может содержать markdown блоки кода)
        topic_name: Название темы (например, 'Python', 'JavaScript')
        subtopic_name: Название подтемы (опционально)
        difficulty: Сложность задачи (опционально)
        admin_chat_id: ID чата админа для отправки видео (опционально, если не указан, будет получен из настроек/БД)
        task_id: ID задачи для использования в имени файла (опционально)
        video_language: Язык видео ('ru', 'en') - для правильного отображения в caption
        selected_bgm: Экземпляр BackgroundMusic или путь к аудиофайлу (опционально)

    Returns:
        URL видео в S3/R2 или None при ошибке
    """
    try:
        # Проверяем, включена ли генерация видео
        if not getattr(settings, 'VIDEO_GENERATION_ENABLED', True):
            logger.debug("Генерация видео отключена в настройках")
            return None
        
        # Извлекаем код из markdown блоков
        code, detected_language = extract_code_from_markdown(task_question)

        # Выбираем текст вопроса в зависимости от языка видео
        # Сначала проверяем кастомный текст из задачи, если task_id передан
        question_text = None
        if task_id:
            try:
                from ..models import Task as TaskModel
                task = TaskModel.objects.get(pk=task_id)
                if task.video_question_texts and isinstance(task.video_question_texts, dict):
                    custom_text = task.video_question_texts.get(video_language)
                    # Используем кастомный текст только если он не пустой
                    if custom_text and custom_text.strip():
                        question_text = custom_text.strip()
            except Exception as e:
                logger.warning(f"Не удалось загрузить задачу {task_id} для получения кастомного текста: {e}")
        
        # Если кастомный текст не найден, используем дефолтный
        if not question_text:
            question_texts = {
                'ru': "Каким будет результат кода?",
                'en': "What will be the result?",
                'ar': "ما سيكون نتيجة الكود؟",
                'tr': "Kodun sonucu ne olacak?"
            }
            question_text = question_texts.get(video_language, question_texts['ru'])

        # Если язык не определён из markdown, используем topic
        if detected_language == 'python' and topic_name:
            topic_lower = topic_name.lower()
            if topic_lower in ['python', 'java', 'javascript', 'go', 'golang', 'rust', 'sql', 'php']:
                detected_language = topic_lower

        logger.info(f"Генерация видео, video_language: {video_language}, detected_language: {detected_language}, вопрос: {question_text}")
        
        # Получаем путь к логотипу (ТОЧНО ТА ЖЕ логика, что и в generate_image_for_task)
        logo_path = os.getenv('LOGO_PATH')
        if not logo_path:
            logo_path = getattr(settings, 'LOGO_PATH', None)
        
        # Если путь из настроек есть, но файл не существует - пробуем fallback
        if logo_path and not os.path.exists(logo_path):
            logger.warning(f"⚠️ Логотип по пути из настроек не найден: {logo_path}, пробуем fallback...")
            logo_path = None
        
        if not logo_path:
            # Fallback: ищем логотип в bot/assets/logo.png (как в боте)
            # Список возможных путей в порядке приоритета
            possible_paths = [
                '/quiz_project/bot/assets/logo.png',  # Docker контейнер (volume)
                '/app/../bot/assets/logo.png',  # Относительно /app
                str(settings.BASE_DIR.parent / 'bot' / 'assets' / 'logo.png'),  # Локальная разработка
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    logo_path = path
                    logger.info(f"🔍 Использован путь к логотипу: {logo_path}")
                    break
            
            if not logo_path:
                logger.warning(f"⚠️ Логотип не найден. Проверены пути: {', '.join(possible_paths)}")
        
        if logo_path:
            # Проверяем существование файла несколькими способами
            exists_os = os.path.exists(logo_path)
            exists_path = Path(logo_path).exists()
            if exists_os or exists_path:
                logger.info(f"✅ Логотип найден: {logo_path} (os.path.exists={exists_os}, Path.exists={exists_path})")
            else:
                logger.warning(f"⚠️ Логотип не найден по пути: {logo_path} (os.path.exists={exists_os}, Path.exists={exists_path})")
        else:
            logger.warning("⚠️ Путь к логотипу не установлен, видео будет сгенерировано без логотипа")
        
        if logo_path:
            logger.info(f"✅ Логотип будет использован: {logo_path}")
        else:
            logger.warning(f"⚠️ Логотип не найден, видео будет сгенерировано без логотипа")
        
        # Если task_id передан и selected_bgm не передан — пробуем получить трек из задачи
        if task_id and not selected_bgm:
            try:
                from ..models import Task as TaskModel
                task_obj = TaskModel.objects.filter(id=task_id).select_related('background_music').first()
                if task_obj and getattr(task_obj, 'background_music', None):
                    selected_bgm = task_obj.background_music
                    logger.info(f"🎵 Использован трек, привязанный к задаче: id={task_obj.id}, bgm_id={selected_bgm.id}")
            except Exception as e:
                logger.debug(f"Не удалось получить background_music из задачи {task_id}: {e}")

        # Генерируем видео
        video_path = generate_code_typing_video(code, detected_language, logo_path, question_text, selected_bgm=selected_bgm)
        if not video_path:
            return None
        
        # Загружаем в S3/R2
        from .s3_service import upload_video_to_s3
        
        # Формируем понятное имя файла на основе темы видео
        # Формат: video_{topic}_{subtopic}_{programming_language}_{difficulty}_{video_language}_{task_id}.mp4
        name_parts = ["video"]

        # Добавляем тему (обязательно)
        if topic_name:
            name_parts.append(sanitize_filename(topic_name, max_length=30))

        # Добавляем подтему (если есть)
        if subtopic_name:
            name_parts.append(sanitize_filename(subtopic_name, max_length=30))

        # Добавляем язык программирования
        if detected_language:
            name_parts.append(sanitize_filename(detected_language, max_length=20))

        # Добавляем сложность (если есть)
        if difficulty:
            name_parts.append(sanitize_filename(difficulty, max_length=15))

        # Добавляем язык видео (для различения видео на разных языках)
        if video_language:
            name_parts.append(sanitize_filename(video_language, max_length=5))

        # Добавляем ID задачи или короткий уникальный ID для уникальности
        if task_id:
            name_parts.append(str(task_id))
        else:
            # Если task_id не передан, используем короткий уникальный ID
            unique_id = str(uuid.uuid4())[:8]
            name_parts.append(unique_id)
        
        # Собираем имя файла
        video_name = "_".join(name_parts) + ".mp4"
        
        logger.info(f"📝 Сформировано имя файла видео: {video_name}")
        
        # Переименовываем файл с output.mp4 на правильное имя перед загрузкой
        video_dir = os.path.dirname(video_path)
        new_video_path = os.path.join(video_dir, video_name)
        
        try:
            # Переименовываем файл
            os.rename(video_path, new_video_path)
            logger.info(f"✅ Файл переименован: {os.path.basename(video_path)} -> {video_name}")
            video_path = new_video_path  # Используем новый путь для загрузки
        except Exception as e:
            logger.warning(f"⚠️ Не удалось переименовать файл {video_path} в {new_video_path}: {e}")
            logger.info(f"   Продолжаем с исходным именем файла")
            # Если не удалось переименовать, используем исходный путь, но имя для S3 будет правильным
        
        video_url = upload_video_to_s3(video_path, video_name)
        
        # Отправляем видео админу в Telegram (ПЕРЕД удалением файла!)
        # Если admin_chat_id не передан явно, получаем из настроек или базы данных
        if not admin_chat_id:
            admin_chat_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)
            
            # Если не задан в настройках, пытаемся получить из базы (первый активный админ)
            if not admin_chat_id:
                try:
                    from accounts.models import TelegramAdmin
                    admin = TelegramAdmin.objects.filter(is_active=True).first()
                    if admin:
                        admin_chat_id = str(admin.telegram_id)
                        logger.info(f"📱 Используется chat_id первого активного админа: {admin_chat_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось получить chat_id админа из базы: {e}")
        else:
            # Преобразуем в строку, если передан как число
            admin_chat_id = str(admin_chat_id)
            logger.info(f"📱 Используется переданный admin_chat_id: {admin_chat_id}")
        
        # Отправляем видео файл напрямую админу (если есть chat_id и файл существует)
        if admin_chat_id and video_path and os.path.exists(video_path):
            try:
                from .telegram_service import send_video_file, send_message
                
                # Отправляем видео файл напрямую
                language_name = {'ru': '🇷🇺 Русский', 'en': '🇺🇸 English'}.get(video_language, video_language.upper())
                caption = f"🎬 Видео сгенерировано для задачи (язык: {language_name})"
                result = send_video_file(str(admin_chat_id), video_path, caption)
                
                if result:
                    logger.info(f"✅ Видео файл отправлен админу в Telegram (chat_id: {admin_chat_id})")
                    
                    # Локализация заголовков для описания задачи
                    task_labels = {
                        'ru': {
                            'language': 'Язык',
                            'topic': 'Тема',
                            'difficulty': 'Сложность'
                        },
                        'en': {
                            'language': 'Language',
                            'topic': 'Topic',
                            'difficulty': 'Difficulty'
                        }
                    }

                    labels = task_labels.get(video_language, task_labels['ru'])

                    # Формируем и отправляем детали задачи
                    task_details = f"🖥️ {labels['language']}: {topic_name}"
                    if subtopic_name:
                        task_details += f"\n📂 {labels['topic']}: {subtopic_name}"
                    if difficulty:
                        # Для английского капитализируем сложность
                        difficulty_text = difficulty.title() if video_language == 'en' else difficulty
                        task_details += f"\n🎯 {labels['difficulty']}: {difficulty_text}"
                    from tasks.models import Task as TaskModel
                    task_row = TaskModel.objects.filter(id=task_id).select_related('tenant').first() if task_id else None
                    task_tenant = task_row.tenant if task_row else None
                    mini_url = (task_tenant.mini_app_url if task_tenant else None) or site_url_for(task_tenant)
                    if mini_url:
                        task_details += f"\n🔗 URL: {mini_url}"

                    # Генерируем хэштеги
                    hashtags = ["code", "quizes", "programming", "coding", "learntocode"]
                    if topic_name:
                        # Добавляем хештег языка программирования
                        topic_hashtag = topic_name.lower().replace(' ', '').replace('+', 'plus')
                        hashtags.append(topic_hashtag)
                    if subtopic_name:
                        # Добавляем хештег подтемы
                        subtopic_hashtag = subtopic_name.lower().replace(' ', '').replace('-', '')
                        hashtags.append(subtopic_hashtag)

                    # Форматируем хэштеги
                    hashtags_text = ' '.join([f'#{tag}' for tag in hashtags])
                    task_details += f"\n\n{hashtags_text}"

                    # Отправляем детали задачи текстовым сообщением (без parse_mode для корректного отображения emoji)
                    send_message(str(admin_chat_id), task_details, parse_mode=None)
                    logger.info(f"✅ Детали задачи отправлены админу")
                else:
                    logger.warning(f"⚠️ Не удалось отправить видео файл админу, пробуем по URL...")
                    # Пробуем отправить по URL как fallback
                    if video_url:
                        from .telegram_service import send_video
                        send_video(str(admin_chat_id), video_url, caption)
                        logger.info(f"✅ Видео отправлено админу по URL (chat_id: {admin_chat_id})")
                
            except Exception as e:
                logger.warning(f"⚠️ Не удалось отправить видео админу: {e}")
                logger.exception(e)  # Логируем полный traceback для отладки
        elif admin_chat_id:
            logger.warning(f"⚠️ Не удалось отправить видео админу: файл не найден по пути {video_path}")
        elif not admin_chat_id:
            logger.warning(f"⚠️ Не удалось отправить видео админу: chat_id не найден")
        
        # Удаляем временный файл ПОСЛЕ отправки
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
                logger.debug(f"🗑️ Временный файл видео удален: {video_path}")
            # Удаляем временную директорию если пустая
            temp_dir = os.path.dirname(video_path)
            if os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                    logger.debug(f"🗑️ Временная директория удалена: {temp_dir}")
                except OSError:
                    pass  # Директория не пустая
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл видео: {e}")
        
        return video_url
        
    except Exception as e:
        logger.error(f"Ошибка при генерации видео для задачи: {e}", exc_info=True)
        return None

