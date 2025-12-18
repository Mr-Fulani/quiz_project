"""
Сервис генерации видео из кода для задач.
Создает видео в формате reels (9:16, 1080x1920) с анимацией появления кода.
"""
import io
import logging
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
from PIL.Image import Resampling
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.styles import get_style_by_name
from django.conf import settings

# Импортируем функции из image_generation_service для переиспользования
from .image_generation_service import (
    extract_code_from_markdown,
    smart_format_code,
    wrap_text,
    get_lexer
)

logger = logging.getLogger(__name__)


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


def _generate_console_frame_vertical(
    formatted_code_text: str,
    language: str,
    visible_chars: int,
    logo_path: Optional[str] = None,
    question_text: str = "Каким будет результат кода?"
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
        visible_code = formatted_code_text
    else:
        # Берем видимую часть без обрезки до последней строки - показываем весь код до visible_chars
        visible_code = formatted_code_text[:visible_chars]
    
    # Настройки для вертикального формата (размеры консоли для вертикального экрана)
    MIN_CONSOLE_WIDTH = 950  # Уменьшено чтобы поместилось на экране
    MIN_CONSOLE_HEIGHT = 1000  # Уменьшено чтобы поместилось на экране
    
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
        highlight(visible_code.strip(), lexer, formatter, outfile=code_image_io)
        code_image_io.seek(0)
        tmp_code_img = Image.open(code_image_io).convert("RGBA")
        
        # Проверяем, помещается ли изображение кода в консоль (уменьшены отступы для большего размера)
        max_code_width = MIN_CONSOLE_WIDTH - 120  # Уменьшено с 160 до 120
        max_code_height = MIN_CONSOLE_HEIGHT - 160  # Уменьшено с 200 до 160
        
        if tmp_code_img.width <= max_code_width and tmp_code_img.height <= max_code_height:
            code_img = tmp_code_img
            break
        
        font_size -= 2
    
    if code_img is None:
        code_img = tmp_code_img
        # Если код не помещается, масштабируем только если он сильно превышает размеры
        max_code_width = MIN_CONSOLE_WIDTH - 120  # Уменьшено с 160 до 120
        max_code_height = MIN_CONSOLE_HEIGHT - 160  # Уменьшено с 200 до 160
        if code_img.width > max_code_width or code_img.height > max_code_height:
            scale_w = max_code_width / code_img.width if code_img.width > max_code_width else 1.0
            scale_h = max_code_height / code_img.height if code_img.height > max_code_height else 1.0
            scale = min(scale_w, scale_h, 1.0)
            if scale < 1.0:
                new_width = int(code_img.width * scale)
                new_height = int(code_img.height * scale)
                code_img = code_img.resize((new_width, new_height), Resampling.LANCZOS)
    
    # Рассчитываем размеры консоли (но не больше ширины экрана)
    # Уменьшены отступы внутри консоли для большего размера кода
    max_console_width = video_width - 100  # Оставляем отступы по бокам
    console_width = min(max_console_width, max(MIN_CONSOLE_WIDTH, code_img.width + 140))  # Уменьшено с 180 до 140
    console_height = max(MIN_CONSOLE_HEIGHT, code_img.height + 180)  # Уменьшено с 240 до 180
    
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
    available_height = video_height - question_text_height - question_text_gap - 80  # 80 - отступ снизу для запаса
    console_y0 = max(50, (available_height - console_height) // 2)  # Минимум 50px от верха
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
    if logo_path and os.path.exists(logo_path):
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
    
    # Вставляем код в консоль (уменьшены отступы для большего размера кода)
    shift_left = 40
    padding_left = (console_width - code_img.width) // 2 - shift_left
    padding_top = 80  # Уменьшено с 120 до 80 для большего размера кода
    code_x = console_x0 + padding_left
    code_y = console_y0 + padding_top
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
    
    # Получаем размеры текста для центрирования
    try:
        bbox = draw.textbbox((0, 0), question_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        # Fallback для старых версий PIL
        text_width = len(question_text) * question_font_size // 2
        text_height = question_font_size
    
    # Позиция текста: по центру горизонтально, прямо под консолью
    text_x = (video_width - text_width) // 2
    text_y = console_y1 + question_text_gap  # Прямо под консолью с отступом
    
    # Проверяем, чтобы текст не выходил за пределы экрана
    if text_y + text_height > video_height - 20:
        # Если текст выходит, сдвигаем выше
        text_y = video_height - text_height - 20
    
    # Рисуем текст с небольшим контуром для читаемости (эффект жирного)
    outline_color = (255, 255, 255)
    for adj in [(-2, -2), (-2, 2), (2, -2), (2, 2), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
        draw.text((text_x + adj[0], text_y + adj[1]), question_text, font=font, fill=outline_color)
    draw.text((text_x, text_y), question_text, font=font, fill=text_color)
    
    return image


def generate_code_typing_video(
    code: str,
    language: str,
    logo_path: Optional[str] = None,
    question_text: str = "Каким будет результат кода?"
) -> Optional[str]:
    """
    Создает видео с анимацией набора кода в формате reels (9:16, 1080x1920).
    
    Args:
        code: Текст кода для анимации
        language: Язык программирования
        logo_path: Путь к логотипу (опционально)
        question_text: Текст вопроса для отображения внизу экрана
        
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
        typing_speed = getattr(settings, 'VIDEO_TYPING_SPEED', 20)  # символов в секунду (увеличено для меньшего количества кадров)
        fps = getattr(settings, 'VIDEO_FPS', 24)
        max_video_duration = 30  # Максимальная длительность видео в секундах
        
        # Форматируем код ОДИН РАЗ перед генерацией кадров
        formatted_code = smart_format_code(code, language)
        # Обрезаем длинные строки для вертикального формата
        formatted_code = wrap_text(formatted_code, max_line_length=50)
        total_chars = len(formatted_code)
        
        # Рассчитываем количество кадров с ограничением максимальной длительности
        duration = min(total_chars / typing_speed, max_video_duration)  # секунды
        total_frames = int(duration * fps)
        
        # Если код очень длинный, увеличиваем скорость для укладывания в максимальную длительность
        if total_chars / typing_speed > max_video_duration:
            typing_speed = total_chars / max_video_duration
            logger.info(f"Код слишком длинный ({total_chars} символов), увеличена скорость набора до {typing_speed:.1f} символов/сек")
        
        # Создаем временную директорию для кадров
        temp_dir = tempfile.mkdtemp()
        frame_paths = []
        
        # Генерируем кадры и сразу сохраняем на диск (не накапливаем в памяти)
        logger.info(f"Генерация {total_frames} кадров для видео...")
        for frame_num in range(total_frames):
            # Для последнего кадра показываем весь код, иначе пропорционально
            if frame_num == total_frames - 1:
                visible_chars = total_chars  # Последний кадр - весь код
            else:
                visible_chars = int((frame_num / total_frames) * total_chars)
            frame = _generate_console_frame_vertical(formatted_code, language, visible_chars, logo_path, question_text)
            
            # Сразу сохраняем кадр на диск
            frame_path = os.path.join(temp_dir, f"frame_{frame_num:06d}.png")
            frame.save(frame_path, 'PNG', optimize=True)
            frame_paths.append(frame_path)
            
            # Освобождаем память
            del frame
            
            # Прогресс каждые 50 кадров
            if (frame_num + 1) % 50 == 0:
                logger.info(f"Сгенерировано {frame_num + 1}/{total_frames} кадров...")
        
        logger.info(f"Создание видео из {len(frame_paths)} кадров...")
        
        # Создаем видео из кадров
        clip = ImageSequenceClip(frame_paths, fps=fps)
        
        # Добавляем аудио если есть
        audio_path = _get_keyboard_audio_path()
        if audio_path:
            try:
                logger.info(f"Добавление аудио из {audio_path}...")
                audio = AudioFileClip(audio_path)
                # Обрезаем аудио до длины видео если оно длиннее
                if audio.duration > clip.duration:
                    audio = audio.subclip(0, clip.duration)
                clip = clip.set_audio(audio)
            except Exception as e:
                logger.info(f"Не удалось добавить аудио (видео будет без звука): {e}")
        else:
            logger.info("Аудиофайл не найден, создается видео без звука")
        
        # Экспортируем видео
        output_path = os.path.join(temp_dir, "output.mp4")
        clip.write_videofile(
            output_path,
            fps=fps,
            codec='libx264',
            audio_codec='aac' if audio_path else None,
            preset='medium',
            ffmpeg_params=['-pix_fmt', 'yuv420p']  # Для совместимости
        )
        
        # Очищаем временные файлы кадров
        for frame_path in frame_paths:
            try:
                os.remove(frame_path)
            except Exception:
                pass
        
        logger.info(f"✅ Видео создано: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Ошибка при создании видео: {e}", exc_info=True)
        return None


def generate_video_for_task(
    task_question: str, 
    topic_name: str,
    subtopic_name: str = None,
    difficulty: str = None
) -> Optional[str]:
    """
    Генерирует видео для задачи в формате reels.
    
    Args:
        task_question: Текст вопроса задачи (может содержать markdown блоки кода)
        topic_name: Название темы (например, 'Python', 'JavaScript')
        subtopic_name: Название подтемы (опционально)
        difficulty: Сложность задачи (опционально)
        
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
        
        # Используем фиксированный текст вопроса как просил пользователь
        question_text = "Каким будет результат кода?"
        
        # Если язык не определён из markdown, используем topic
        if detected_language == 'python' and topic_name:
            topic_lower = topic_name.lower()
            if topic_lower in ['python', 'java', 'javascript', 'go', 'golang', 'rust', 'sql', 'php']:
                detected_language = topic_lower
        
        logger.info(f"Генерация видео, язык: {detected_language}, вопрос: {question_text}")
        
        # Получаем путь к логотипу
        logo_path = os.getenv('LOGO_PATH')
        if not logo_path:
            logo_path = getattr(settings, 'LOGO_PATH', None)
        
        if logo_path and not os.path.exists(logo_path):
            logger.warning(f"⚠️ Логотип по пути из настроек не найден: {logo_path}")
            logo_path = None
        
        if not logo_path:
            base_dir = settings.BASE_DIR.parent
            fallback_logo_path = base_dir / 'bot' / 'assets' / 'logo.png'
            if fallback_logo_path.exists():
                logo_path = str(fallback_logo_path)
        
        # Генерируем видео
        video_path = generate_code_typing_video(code, detected_language, logo_path, question_text)
        if not video_path:
            return None
        
        # Загружаем в S3/R2
        from .s3_service import upload_video_to_s3
        
        # Формируем имя файла (уникальное для избежания конфликтов)
        unique_id = str(uuid.uuid4())[:8]
        video_name = f"task_video_{topic_name.lower()}_{detected_language}_{unique_id}.mp4"
        video_name = video_name.replace(" ", "_")
        
        video_url = upload_video_to_s3(video_path, video_name)
        
        # Отправляем видео админу в Telegram (ПЕРЕД удалением файла!)
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
        
        # Отправляем видео файл напрямую админу (если есть chat_id и файл существует)
        if admin_chat_id and video_path and os.path.exists(video_path):
            try:
                from .telegram_service import send_video_file, send_message
                
                # Отправляем видео файл напрямую
                caption = f"🎬 Видео сгенерировано для задачи"
                result = send_video_file(str(admin_chat_id), video_path, caption)
                
                if result:
                    logger.info(f"✅ Видео файл отправлен админу в Telegram (chat_id: {admin_chat_id})")
                    
                    # Формируем и отправляем детали задачи
                    task_details = f"🖥️ Язык: {topic_name}"
                    if subtopic_name:
                        task_details += f"\n📂 Тема: {subtopic_name}"
                    if difficulty:
                        task_details += f"\n🎯 Сложность: {difficulty}"
                    if video_url:
                        task_details += f"\n🔗 URL: {video_url}"
                    
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

