from PIL import Image, ImageDraw, ImageFont
import os
from django.conf import settings
from django.core.files.base import ContentFile
import textwrap
import io


def generate_og_image(title, category, width=1200, height=630):
    """
    Генерирует динамическую Open Graph картинку для поста/проекта.
    """
    try:
        # Создаем изображение с градиентным фоном
        img = Image.new('RGB', (width, height), color='#1a1a2e')
        draw = ImageDraw.Draw(img)
        
        # Градиентный фон
        for y in range(height):
            r = int(26 + (56 - 26) * y / height)  # От #1a1a2e до #16213e
            g = int(26 + (33 - 26) * y / height)
            b = int(46 + (62 - 46) * y / height)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        # Пытаемся загрузить шрифты
        try:
            title_font = ImageFont.truetype(
                os.path.join(settings.BASE_DIR, 'bot/fonts/Arial Unicode.ttf'), 
                60
            )
            category_font = ImageFont.truetype(
                os.path.join(settings.BASE_DIR, 'bot/fonts/Arial Unicode.ttf'), 
                30
            )
        except:
            # Fallback на дефолтный шрифт
            title_font = ImageFont.load_default()
            category_font = ImageFont.load_default()
        
        # Обрезаем заголовок если слишком длинный
        wrapped_title = textwrap.fill(title, width=40)
        title_lines = wrapped_title.split('\n')
        
        # Позиционирование текста
        y_offset = height // 2 - len(title_lines) * 35
        
        # Рисуем категорию
        if category:
            category_bbox = draw.textbbox((0, 0), category.upper(), font=category_font)
            category_width = category_bbox[2] - category_bbox[0]
            draw.text(
                ((width - category_width) // 2, y_offset - 80), 
                category.upper(),
                font=category_font,
                fill='#ffd700'  # Золотой цвет
            )
        
        # Рисуем заголовок
        for i, line in enumerate(title_lines):
            line_bbox = draw.textbbox((0, 0), line, font=title_font)
            line_width = line_bbox[2] - line_bbox[0]
            draw.text(
                ((width - line_width) // 2, y_offset + i * 70),
                line,
                font=title_font,
                fill='white'
            )
        
        # Добавляем логотип QuizHub внизу
        draw.text(
            (50, height - 80),
            'QuizHub',
            font=category_font,
            fill='#ffd700'
        )
        
        # Сохраняем в BytesIO
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=90)
        output.seek(0)
        
        return output
        
    except Exception as e:
        print(f"Ошибка при генерации OG изображения: {e}")
        return None


def save_og_image(title, category, slug, content_type='post'):
    """
    Генерирует и сохраняет OG изображение в медиа директорию.
    """
    image_data = generate_og_image(title, category)
    if not image_data:
        return None
    
    # Создаем путь для сохранения
    filename = f'og_{content_type}_{slug}.jpg'
    relative_path = f'og_images/{filename}'
    full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    
    # Создаем директорию если не существует
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    # Сохраняем файл
    with open(full_path, 'wb') as f:
        f.write(image_data.getvalue())
    
    return f'{settings.MEDIA_URL}{relative_path}' 