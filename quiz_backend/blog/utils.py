from PIL import Image, ImageDraw, ImageFont
import os
import re
from django.conf import settings
from django.core.files.base import ContentFile
import textwrap
import io


def generate_og_image(title, category, width=1200, height=630, brand=''):
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
        
        # Название сайта тенанта внизу
        if brand:
            draw.text(
                (50, height - 80),
                brand,
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


def save_og_image(title, category, slug, content_type='post', brand=''):
    """
    Генерирует и сохраняет OG изображение в медиа директорию.
    """
    image_data = generate_og_image(title, category, brand=brand)
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


def process_code_blocks_for_web(html_content):
    """
    Обрабатывает кодовые блоки в HTML контенте для веб-отображения.
    Конвертирует fenced Markdown блоки (```lang) в HTML с классами для highlight.js.
    Также обрабатывает существующие <pre><code> блоки.
    
    Args:
        html_content (str): HTML контент с возможными Markdown блоками или HTML тегами
        
    Returns:
        str: HTML с обработанными кодовыми блоками
    """
    if not html_content:
        return html_content
    
    import logging
    logger = logging.getLogger(__name__)
    
    # Декодируем HTML-сущности, которые мог создать TinyMCE
    from html import unescape
    original_content = html_content
    html_content = unescape(html_content)
    
    # Логируем для отладки
    logger.info(f"Обработка кодовых блоков. Длина контента: {len(html_content)}")
    logger.debug(f"Первые 1000 символов контента: {html_content[:1000]}")
    
    # Проверяем наличие тройных кавычек
    has_triple_backticks = '```' in html_content
    has_html_entities = '&#96;' in html_content
    has_pre_tags = '<pre' in html_content.lower()
    
    logger.info(f"Найдено: тройные кавычки={has_triple_backticks}, HTML-сущности={has_html_entities}, <pre> теги={has_pre_tags}")
    
    # 1. Обрабатываем fenced Markdown блоки: ```language\ncode\n```
    # Более гибкий паттерн, который учитывает возможные пробелы и разные варианты написания
    def replace_fenced_block(match):
        language = (match.group(1) or '').strip()
        code = match.group(2).strip()
        # Экранируем HTML в коде
        from django.utils.html import escape
        code = escape(code)
        # Добавляем класс языка для highlight.js
        if language:
            return f'<pre><code class="language-{language}">{code}</code></pre>'
        else:
            return f'<pre><code>{code}</code></pre>'
    
    # Ищем ```язык или просто ```, затем код до ```
    # Учитываем возможные пробелы после ``` и перед языком
    # Также ищем варианты с HTML-сущностями (&#96;)
    
    # Сначала обрабатываем HTML-сущности (если TinyMCE их создал)
    # Заменяем &#96; на обычные обратные кавычки
    html_content = html_content.replace('&#96;', '`')
    html_content = html_content.replace('&grave;', '`')
    
    # Обрабатываем тройные кавычки - самый простой и надежный паттерн
    # Ищем ```язык или просто ```, затем код до ```
    def process_fenced_blocks(text):
        # Заменяем все варианты тройных кавычек
        # Паттерн: ```язык\nкод\n``` или ```\nкод\n```
        def replace_block(match):
            full_match = match.group(0)
            # Извлекаем язык (если есть) из группы 1
            language = match.group(1) if match.group(1) else ''
            # Извлекаем код из группы 2
            code = match.group(2) if match.group(2) else ''
            
            # Логируем для отладки
            logger.debug(f"Обработка блока кода: язык={language}, длина кода={len(code) if code else 0}")
            if code and len(code) > 0:
                # НЕ используем strip() - это удалит отступы в начале строк
                # Только убираем лишние пустые строки в самом начале и конце блока
                # Но сохраняем все отступы и пустые строки внутри кода
                code = re.sub(r'^\n+', '', code)  # Убираем пустые строки только в начале
                code = re.sub(r'\n+$', '', code)  # Убираем пустые строки только в конце
                # Сохраняем все пробелы и отступы внутри кода
                from django.utils.html import escape
                code = escape(code)
                logger.debug(f"Обработанный код: первые 100 символов={code[:100]}")
                if language:
                    return f'<pre><code class="language-{language}">{code}</code></pre>'
                else:
                    return f'<pre><code>{code}</code></pre>'
            logger.warning(f"Блок кода не содержит кода: {full_match[:200]}")
            return full_match
        
        # Ищем все блоки с тройными кавычками
        # Улучшенный паттерн: захватывает весь код между ```язык и ```, включая многострочный код
        # Используем жадный квантификатор для захвата всего содержимого до последних ```
        # Паттерн: ```язык (опционально) затем любой текст до ```
        return re.sub(
            r'```\s*(\w+)?\s*[\r\n]*(.*?)\s*```',
            replace_block,
            text,
            flags=re.DOTALL
        )
    
    html_content = process_fenced_blocks(html_content)
    
    # 1.4. Повторно обрабатываем блоки кода, если они не были обработаны (на случай, если TinyMCE разбил их)
    # Это нужно для случаев, когда код разбит на несколько параграфов
    html_content = process_fenced_blocks(html_content)
    
    # 1.5. Обрабатываем случаи, когда TinyMCE преобразовал тройные кавычки в HTML с <br> или разбил на параграфы
    # TinyMCE может разбить ```python\nкод\n``` на <p>```python<br>код<br>```</p> или на несколько <p>
    def process_tinymce_code_blocks(text):
        """
        Обрабатывает кодовые блоки, которые TinyMCE преобразовал в HTML.
        Ищет паттерны типа: ```python<br>код<br>``` или <p>```python<br>код<br>```</p>
        или разбитые на несколько параграфов.
        """
        # Сначала обрабатываем случаи, когда код разбит на параграфы
        # Ищем начало ```язык в любом месте и конец ``` в другом параграфе
        
        def find_and_replace_multiparagraph_code(text):
            # Ищем начало блока: ```язык (может быть в любом месте параграфа)
            # Паттерн ищет ```язык или ``` в любом месте текста
            start_pattern = r'```\s*(\w+)?'
            
            # Находим все вхождения ```язык
            matches = list(re.finditer(start_pattern, text, re.IGNORECASE))
            
            for start_match in matches:
                language = start_match.group(1) if start_match.group(1) else ''
                start_pos = start_match.start()
                
                # Ищем конец блока: ``` (должен быть в другом месте)
                # Ищем все возможные закрывающие ``` после начала блока
                remaining_text = text[start_pos + start_match.end():]
                end_match = re.search(r'```', remaining_text, re.IGNORECASE)
                
                if not end_match:
                    continue
                
                # Извлекаем весь блок от начала до конца (включая параграфы)
                # Нужно найти начало параграфа, который содержит ```язык
                # и конец параграфа, который содержит ```
                
                # Ищем начало: находим <p> который содержит ```язык
                text_before_start = text[:start_pos]
                para_start_match = text_before_start.rfind('<p>')
                if para_start_match == -1:
                    # Если не нашли <p>, начинаем с начала найденного ```
                    block_start = start_pos
                else:
                    block_start = para_start_match
                
                # Ищем конец: находим позицию закрывающих ```
                end_pos = start_pos + start_match.end() + end_match.start()
                
                # Теперь ищем, где заканчивается блок кода
                # Ищем закрывающий тег параграфа после ```
                text_after_end = text[end_pos:]
                para_end_match = text_after_end.find('</p>')
                
                # Также проверяем, нет ли еще одного ``` после первого (это может быть начало нового блока)
                next_triple_backticks = text_after_end.find('```', 3)  # Пропускаем первые 3 символа (это наш закрывающий ```)
                
                if para_end_match == -1:
                    # Если не нашли </p>, ищем до следующего <p> или до следующего блока кода
                    next_p = text_after_end.find('<p>')
                    if next_p != -1:
                        # Проверяем, не является ли следующий <p> частью кода
                        # Если между ``` и <p> много текста, это может быть часть кода
                        if next_p < 200:  # Если <p> близко, это может быть конец
                            block_end = end_pos + next_p
                        else:
                            # Ищем до следующего блока кода или до конца
                            if next_triple_backticks != -1 and next_triple_backticks < 500:
                                # Если следующий ``` близко, это может быть новый блок
                                block_end = end_pos + next_triple_backticks
                            else:
                                # Ищем до конца или до следующего явного маркера конца
                                # Ищем маркеры типа эмодзи или хештегов, которые обычно идут после кода
                                markers = ['♎️', '#', '<p>♎️', '<p>#']
                                marker_pos = len(text_after_end)
                                for marker in markers:
                                    pos = text_after_end.find(marker)
                                    if pos != -1 and pos < marker_pos:
                                        marker_pos = pos
                                
                                if marker_pos < len(text_after_end):
                                    block_end = end_pos + marker_pos
                                else:
                                    block_end = end_pos + len(text_after_end)
                    else:
                        # Нет следующего <p>, ищем до следующего блока кода или до конца
                        if next_triple_backticks != -1 and next_triple_backticks < 1000:
                            block_end = end_pos + next_triple_backticks
                        else:
                            # Ищем маркеры конца
                            markers = ['♎️', '#', '<p>♎️', '<p>#']
                            marker_pos = len(text_after_end)
                            for marker in markers:
                                pos = text_after_end.find(marker)
                                if pos != -1 and pos < marker_pos:
                                    marker_pos = pos
                            
                            if marker_pos < len(text_after_end):
                                block_end = end_pos + marker_pos
                            else:
                                block_end = end_pos + len(text_after_end)
                else:
                    # Нашли </p>, но проверяем, не является ли это частью кода
                    # Если между ``` и </p> много текста, это может быть часть кода
                    if para_end_match < 200:
                        block_end = end_pos + para_end_match + 4  # +4 для </p>
                    else:
                        # Ищем до следующего блока кода или маркера
                        if next_triple_backticks != -1 and next_triple_backticks < para_end_match:
                            block_end = end_pos + next_triple_backticks
                        else:
                            block_end = end_pos + para_end_match + 4
                
                # Извлекаем весь блок
                code_block_html = text[block_start:block_end]
                
                # Извлекаем код, заменяя <br> на переносы строк и убирая HTML теги
                # Сначала заменяем <br> на \n
                code_text = code_block_html.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
                # Заменяем &nbsp; на пробелы
                code_text = code_text.replace('&nbsp;', ' ')
                # Убираем HTML теги
                from django.utils.html import strip_tags
                code_text = strip_tags(code_text)
                
                # Убираем ```язык в начале и ``` в конце
                code_text = re.sub(r'^[^`]*```\s*\w*\s*', '', code_text, flags=re.IGNORECASE)
                code_text = re.sub(r'\s*```[^`]*$', '', code_text, flags=re.IGNORECASE)
                # НЕ используем strip() - сохраняем отступы
                # Только убираем пустые строки в самом начале и конце
                code_text = re.sub(r'^\n+', '', code_text)
                code_text = re.sub(r'\n+$', '', code_text)
                
                # Убираем маркеры конца, если они попали в код
                code_text = re.sub(r'\s*♎️.*$', '', code_text, flags=re.MULTILINE)
                code_text = re.sub(r'\s*#\w+.*$', '', code_text, flags=re.MULTILINE)
                # НЕ используем strip() - сохраняем отступы
                
                if code_text and len(code_text) > 10:  # Минимум 10 символов кода
                    from django.utils.html import escape
                    code_text = escape(code_text)
                    
                    logger.info(f"Найден многострочный код блок от TinyMCE, язык: {language or 'не указан'}, длина: {len(code_text)}")
                    logger.debug(f"Первые 200 символов кода: {code_text[:200]}")
                    logger.debug(f"Последние 200 символов кода: {code_text[-200:]}")
                    
                    replacement = f'<pre><code class="language-{language}">{code_text}</code></pre>' if language else f'<pre><code>{code_text}</code></pre>'
                    
                    # Заменяем весь блок
                    return text[:block_start] + replacement + text[block_end:]
            
            return text
        
        # Обрабатываем многострочные блоки (повторяем несколько раз для вложенных случаев)
        # Увеличиваем количество итераций для обработки сложных случаев
        for iteration in range(5):  # Максимум 5 итераций
            new_text = find_and_replace_multiparagraph_code(text)
            if new_text == text:
                logger.debug(f"Обработка многострочных блоков завершена на итерации {iteration + 1}")
                break
            text = new_text
            logger.debug(f"Итерация {iteration + 1}: найдены и обработаны блоки кода")
        
        # Теперь обрабатываем простые случаи в одном параграфе
        def replace_tinymce_block(match):
            full_match = match.group(0)
            
            # Извлекаем язык
            lang_match = re.search(r'```\s*(\w+)?', full_match)
            language = lang_match.group(1) if lang_match and lang_match.group(1) else ''
            
            # Извлекаем код между ```язык<br> и <br>```
            # Заменяем <br> на переносы строк для обработки
            code_text = full_match.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
            code_match = re.search(r'```\s*\w*\s*\n(.*?)\n\s*```', code_text, re.DOTALL)
            
            if not code_match:
                # Пробуем без языка
                code_match = re.search(r'```\s*\n(.*?)\n\s*```', code_text, re.DOTALL)
            
            if code_match:
                code = code_match.group(1)
                # НЕ используем strip() - сохраняем отступы
                # Только убираем пустые строки в начале и конце
                code = re.sub(r'^\n+', '', code)
                code = re.sub(r'\n+$', '', code)
                # Убираем HTML теги из кода
                from django.utils.html import strip_tags
                code = strip_tags(code)
                from django.utils.html import escape
                code = escape(code)
                
                logger.info(f"Найден код блок от TinyMCE, язык: {language or 'не указан'}, длина: {len(code)}")
                
                if language:
                    return f'<pre><code class="language-{language}">{code}</code></pre>'
                else:
                    return f'<pre><code>{code}</code></pre>'
            return full_match
        
        # Ищем паттерны с <br> тегами в одном параграфе
        patterns = [
            # ```язык<br>код<br>``` внутри <p>
            (r'<p>```\s*(\w+)?\s*<br[^>]*>(.*?)<br[^>]*>\s*```</p>', replace_tinymce_block),
            # ```язык<br>код<br>``` без <p>
            (r'```\s*(\w+)?\s*<br[^>]*>(.*?)<br[^>]*>\s*```', replace_tinymce_block),
        ]
        
        for pattern, replacer in patterns:
            text = re.sub(pattern, replacer, text, flags=re.DOTALL | re.IGNORECASE)
        
        return text
    
    html_content = process_tinymce_code_blocks(html_content)
    
    # 1.5.5. Очищаем существующие <pre> блоки от параграфов и <br> внутри
    def clean_existing_pre_blocks(text):
        """
        Очищает существующие <pre> блоки от параграфов и <br> тегов внутри.
        Это нужно, если TinyMCE разбил код на параграфы внутри <pre>.
        """
        def clean_pre_block(match):
            pre_tag = match.group(1)  # <pre> или <pre class="...">
            content = match.group(2)  # содержимое между <pre> и </pre>
            
            # Если внутри есть <p> теги, убираем их
            if '<p>' in content or '</p>' in content:
                # Заменяем <p> и </p> на переносы строк
                content = re.sub(r'</?p[^>]*>', '\n', content)
                # Убираем лишние переносы
                content = re.sub(r'\n{3,}', '\n\n', content)
                content = content.strip()
            
            # Заменяем <br> на переносы строк
            content = content.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
            # Убираем &nbsp; (как HTML entity так и как \xa0)
            content = content.replace('&nbsp;', ' ')
            content = content.replace('\xa0', ' ')
            # Убираем \r (возврат каретки)
            content = content.replace('\r', '')
            
            # Убираем все остальные HTML теги, кроме тех, что уже в <code>
            from django.utils.html import strip_tags
            # Если есть <code> внутри, сохраняем его
            code_match = re.search(r'<code[^>]*>(.*?)</code>', content, re.DOTALL)
            if code_match:
                # Код уже в <code>, просто очищаем от лишних тегов
                code_content = code_match.group(1)
                # АГРЕССИВНО удаляем ВСЕ HTML теги (включая span, div, strong, em и т.д.)
                code_content = strip_tags(code_content)
                # Также удаляем любые оставшиеся теги через regex (на случай если strip_tags что-то пропустил)
                code_content = re.sub(r'<[^>]+>', '', code_content)
                # Декодируем HTML entities
                from html import unescape
                code_content = unescape(code_content)
                # Заменяем неразрывные пробелы на обычные
                code_content = code_content.replace('\xa0', ' ')
                code_content = code_content.replace('&nbsp;', ' ')
                # Убираем \r
                code_content = code_content.replace('\r', '')
                # НЕ нормализуем пробелы - сохраняем все отступы и пробелы
                # НЕ используем strip() - сохраняем отступы в начале и конце
                # Только убираем пустые строки в самом начале и конце
                code_content = re.sub(r'^\n+', '', code_content)
                code_content = re.sub(r'\n+$', '', code_content)
                # Сохраняем класс языка, если есть
                code_tag_match = re.search(r'<code[^>]*class="([^"]*)"', match.group(0), re.IGNORECASE)
                if code_tag_match:
                    lang_class = code_tag_match.group(1)
                    return f'{pre_tag}<code class="{lang_class}">{code_content}</code></pre>'
                else:
                    return f'{pre_tag}<code>{code_content}</code></pre>'
            else:
                # Нет <code>, создаем его
                content = strip_tags(content)
                # Заменяем неразрывные пробелы на обычные
                content = content.replace('\xa0', ' ')
                content = content.replace('&nbsp;', ' ')
                # Убираем \r
                content = content.replace('\r', '')
                # НЕ используем strip() - сохраняем отступы
                # Только убираем пустые строки в начале и конце
                content = re.sub(r'^\n+', '', content)
                content = re.sub(r'\n+$', '', content)
                # Проверяем, есть ли класс языка в <pre>
                pre_class_match = re.search(r'class="([^"]*)"', pre_tag, re.IGNORECASE)
                if pre_class_match and 'language-' in pre_class_match.group(1):
                    lang_class = pre_class_match.group(1)
                    return f'{pre_tag}<code class="{lang_class}">{content}</code></pre>'
                else:
                    return f'{pre_tag}<code>{content}</code></pre>'
        
        # Обрабатываем все <pre> блоки
        return re.sub(
            r'(<pre[^>]*>)(.*?)(</pre>)',
            clean_pre_block,
            text,
            flags=re.DOTALL | re.IGNORECASE
        )
    
    html_content = clean_existing_pre_blocks(html_content)
    
    # 1.6. Обрабатываем блоки кода без тройных кавычек (по контексту)
    # Если код идет после "Пример использования:", "Пример:", "Код:" и т.д.
    def detect_code_blocks_by_context(text):
        """
        Определяет блоки кода по контексту, даже если нет тройных кавычек.
        Ищет паттерны типа: "Пример использования:" затем код Python/JavaScript и т.д.
        """
        # Пропускаем, если уже есть <pre> теги (код уже обработан)
        if '<pre' in text.lower():
            return text
        
        # Маркеры, после которых обычно идет код
        code_markers = [
            r'Пример использования[:\s]',
            r'Пример[:\s]',
            r'Код[:\s]',
            r'Пример кода[:\s]',
            r'Usage[:\s]',
            r'Example[:\s]',
        ]
        
        # Признаки кода Python
        python_keywords = [
            r'\bimport\s+\w+',
            r'\bfrom\s+\w+\s+import',
            r'\bdef\s+\w+\s*\(',
            r'\bclass\s+\w+',
            r'\bif\s+.*:',
            r'\bfor\s+.*\s+in\s+',
            r'\bwhile\s+.*:',
            r'\bwith\s+.*:',
            r'\btry\s*:',
            r'\bexcept\s+',
        ]
        
        # Ищем маркеры
        for marker_pattern in code_markers:
            marker_matches = list(re.finditer(marker_pattern, text, re.IGNORECASE))
            
            for marker_match in marker_matches:
                marker_end = marker_match.end()
                
                # Ищем код после маркера (до следующего параграфа с обычным текстом)
                remaining_text = text[marker_end:]
                
                # Ищем начало потенциального блока кода
                # Это может быть начало параграфа с ключевым словом Python
                code_start_pattern = r'<p>(' + '|'.join(python_keywords) + r')'
                code_start_match = re.search(code_start_pattern, remaining_text, re.IGNORECASE)
                
                if not code_start_match:
                    continue
                
                code_start_pos = marker_end + code_start_match.start()
                
                # Находим начало параграфа, который содержит код
                text_before_code = text[:code_start_pos]
                para_start = text_before_code.rfind('<p>')
                if para_start == -1:
                    para_start = code_start_pos
                
                # Ищем конец блока кода
                code_text_after = text[para_start:]
                
                # Ищем маркеры конца кода
                end_markers = [
                    r'<p>♎️',  # Эмодзи в начале параграфа
                    r'<p>#python',  # Хештег
                    r'<p>#soft',
                    r'<p>#github',
                    r'<p>#\w+',  # Любой хештег
                ]
                
                code_end_pos = len(text)  # По умолчанию до конца
                
                for end_marker in end_markers:
                    end_match = re.search(end_marker, code_text_after, re.IGNORECASE)
                    if end_match:
                        code_end_pos = para_start + end_match.start()
                        break
                
                # Если не нашли маркер, ищем параграф, который НЕ похож на код
                if code_end_pos == len(text):
                    para_matches = list(re.finditer(r'<p>', code_text_after))
                    for i, para_match in enumerate(para_matches[1:], 1):  # Пропускаем первый (начало кода)
                        para_start_local = para_match.start()
                        para_content = code_text_after[para_start_local:para_start_local + 200]  # Первые 200 символов параграфа
                        
                        # Проверяем, похож ли параграф на код
                        is_code = False
                        for keyword_pattern in python_keywords:
                            if re.search(keyword_pattern, para_content, re.IGNORECASE):
                                is_code = True
                                break
                        
                        # Также проверяем на признаки обычного текста
                        is_normal_text = bool(re.search(r'[🟢📸🧠🌚😰🗂🆓♎️#]', para_content))  # Эмодзи, хештеги
                        
                        if not is_code and is_normal_text:
                            # Нашли конец блока кода
                            code_end_pos = para_start + para_start_local
                            break
                
                # Извлекаем блок кода
                code_block_html = text[para_start:code_end_pos]
                
                # Проверяем, что это действительно код (содержит ключевые слова)
                has_code_keywords = any(re.search(pattern, code_block_html, re.IGNORECASE) for pattern in python_keywords)
                
                if has_code_keywords and len(code_block_html) > 50:  # Минимум 50 символов
                    # Извлекаем код
                    code_text = code_block_html.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
                    code_text = code_text.replace('&nbsp;', ' ')
                    from django.utils.html import strip_tags
                    code_text = strip_tags(code_text)
                    
                    # Убираем маркер в начале, если он есть
                    code_text = re.sub(r'^[^<]*Пример использования[:\s]*', '', code_text, flags=re.IGNORECASE)
                    code_text = re.sub(r'^[^<]*Пример[:\s]*', '', code_text, flags=re.IGNORECASE)
                    code_text = code_text.strip()
                    
                    # Убираем лишние пустые строки
                    code_text = re.sub(r'^\n+', '', code_text)
                    code_text = re.sub(r'\n+$', '', code_text)
                    
                    if code_text and len(code_text) > 50:
                        from django.utils.html import escape
                        code_text = escape(code_text)
                        
                        # Определяем язык по ключевым словам
                        language = 'python'  # По умолчанию Python
                        if re.search(r'\b(function|const|let|var|=>)\b', code_text):
                            language = 'javascript'
                        elif re.search(r'\b(def|class|import|from)\b', code_text):
                            language = 'python'
                        
                        logger.info(f"Найден код блок по контексту, язык: {language}, длина: {len(code_text)}")
                        
                        replacement = f'<pre><code class="language-{language}">{code_text}</code></pre>'
                        
                        # Заменяем блок
                        return text[:para_start] + replacement + text[code_end_pos:]
        
        return text
    
    # Обрабатываем код по контексту (повторяем несколько раз)
    for _ in range(2):
        new_text = detect_code_blocks_by_context(html_content)
        if new_text == html_content:
            break
        html_content = new_text
    
    # 2. Обрабатываем существующие <pre> блоки (с <code> внутри или без)
    # TinyMCE может создавать <pre> без <code>, или <pre><code> без классов
    
    # 2.1. Обрабатываем <pre><code>...</code></pre>
    def add_language_class_to_pre_code(match):
        pre_attrs = match.group(1) or ''
        code_attrs = match.group(2) or ''
        code_content = match.group(3)
        
        # Проверяем, есть ли уже класс языка
        if 'class=' in code_attrs and 'language-' in code_attrs:
            return match.group(0)  # Уже есть класс, не трогаем
        
        # Пытаемся определить язык из содержимого или добавляем общий класс
        if 'language-' not in code_attrs:
            # Добавляем класс для подсветки
            if 'class=' in code_attrs:
                code_attrs = code_attrs.replace('class="', 'class="hljs ')
                code_attrs = code_attrs.replace("class='", "class='hljs ")
            else:
                code_attrs = 'class="hljs"'
        
        logger.debug(f"Обработан <pre><code> блок, добавлен класс: {code_attrs}")
        return f'<pre{pre_attrs}><code{code_attrs}>{code_content}</code></pre>'
    
    html_content = re.sub(
        r'<pre([^>]*)><code([^>]*)>(.*?)</code></pre>',
        add_language_class_to_pre_code,
        html_content,
        flags=re.DOTALL
    )
    
    # 2.2. Обрабатываем <pre>...</pre> без <code> внутри (TinyMCE может так создавать)
    def wrap_pre_in_code(match):
        pre_attrs = match.group(1) or ''
        pre_content = match.group(2)
        
        # Если внутри уже есть <code>, не трогаем
        if '<code' in pre_content.lower():
            return match.group(0)
        
        # Оборачиваем содержимое в <code> с классом для highlight.js
        from django.utils.html import escape
        # Контент уже может быть экранирован, но на всякий случай
        logger.debug(f"Обработан <pre> без <code>, обернуто в <code>")
        return f'<pre{pre_attrs}><code class="hljs">{pre_content}</code></pre>'
    
    html_content = re.sub(
        r'<pre([^>]*)>(.*?)</pre>',
        wrap_pre_in_code,
        html_content,
        flags=re.DOTALL
    )
    
    # 3. Обрабатываем однострочный (inline) код: `код`
    # Важно: обрабатываем ПОСЛЕ многострочных блоков, чтобы не конфликтовать с тройными кавычками
    # И исключаем обработку кавычек внутри уже обработанных <pre><code> блоков
    def process_inline_code(text):
        """
        Обрабатывает однострочный код в формате `код`.
        Исключает обработку внутри <pre><code> блоков.
        """
        # Сначала защищаем уже обработанные блоки кода
        code_blocks = []
        placeholder_pattern = '__CODE_BLOCK_{}__'
        
        def protect_code_blocks(match):
            block_id = len(code_blocks)
            code_blocks.append(match.group(0))
            return placeholder_pattern.format(block_id)
        
        # Защищаем все <pre><code> блоки
        protected_text = re.sub(
            r'<pre[^>]*>.*?</pre>',
            protect_code_blocks,
            text,
            flags=re.DOTALL | re.IGNORECASE
        )
        
        # Теперь обрабатываем inline код: `код`
        # Паттерн: `код` где код не содержит обратные кавычки и не начинается/заканчивается пробелом
        def replace_inline_code(match):
            code = match.group(1)
            # Экранируем HTML в коде
            from django.utils.html import escape
            code = escape(code)
            # Убираем лишние пробелы в начале и конце
            code = code.strip()
            return f'<code>{code}</code>'
        
        # Обрабатываем inline код: `код` (но не внутри уже обработанных блоков)
        # Исключаем случаи, когда кавычки идут подряд (это многострочный блок)
        # Паттерн: `код` где код не содержит обратные кавычки, переносы строк и не пустой
        # Также обрабатываем двойные кавычки ``код`` (на случай, если пользователь их использует)
        
        # Сначала обрабатываем одинарные кавычки `код`
        protected_text = re.sub(
            r'(?<!`)`([^`\n\r]+?)`(?!`)',  # `код` но не ``` или ``код`` или `\n`
            replace_inline_code,
            protected_text
        )
        
        # Затем обрабатываем двойные кавычки ``код`` (если они не были обработаны как часть тройных)
        # Это нужно для случаев, когда пользователь использует ``код`` вместо `код`
        protected_text = re.sub(
            r'(?<!`)``([^`\n\r]+?)``(?!`)',  # ``код`` но не ``` или ```код```
            replace_inline_code,
            protected_text
        )
        
        # Восстанавливаем защищенные блоки
        for i, block in enumerate(code_blocks):
            protected_text = protected_text.replace(placeholder_pattern.format(i), block)
        
        return protected_text
    
    html_content = process_inline_code(html_content)
    
    logger.info(f"Обработка завершена. Длина результата: {len(html_content)}")
    
    return html_content


def markdown_to_html_with_code_blocks(markdown_text):
    """
    Конвертирует Markdown текст в HTML с обработкой кодовых блоков.
    Используется для обработки контента постов перед сохранением.
    
    Args:
        markdown_text (str): Markdown текст
        
    Returns:
        str: HTML с обработанными кодовыми блоками
    """
    if not markdown_text:
        return markdown_text
    
    # Сначала обрабатываем кодовые блоки
    html = process_code_blocks_for_web(markdown_text)
    
    # Затем можно добавить обработку других Markdown элементов
    # (заголовки, списки, ссылки и т.д.)
    # Но для начала достаточно кодовых блоков
    
    return html


def html_to_telegram_text(html_content, post_url=None):
    """
    Конвертирует HTML контент поста в формат Telegram.
    
    ВАЖНО: Функция работает с уже обработанным HTML контентом (после process_code_blocks_for_web()).
    Блоки кода уже в формате <pre><code class="language-xxx">код</code></pre>.
    
    Args:
        html_content (str): HTML контент поста (уже обработанный process_code_blocks_for_web)
        post_url (str, optional): URL поста для добавления ссылки при обрезке
        
    Returns:
        str: Текст с HTML разметкой для Telegram
    """
    if not html_content:
        return html_content
    
    import logging
    from html import unescape
    logger = logging.getLogger(__name__)
    
    logger.info(f"Конвертация HTML → Telegram. Исходная длина: {len(html_content)} символов")
    
    # Создаем копию для работы
    text = html_content
    
    # 1. Сначала защищаем блоки кода <pre><code>...</code></pre> от дальнейшей обработки
    code_block_placeholders = {}
    placeholder_counter = 0
    
    def protect_code_block(match):
        nonlocal placeholder_counter
        full_block = match.group(0)
        pre_attrs = match.group(1) or ''
        code_attrs = match.group(2) or ''
        code_content = match.group(3)
        
        # Логируем исходное содержимое для отладки
        original_length = len(code_content)
        logger.info(f"Обработка блока кода: исходная длина {original_length} символов")
        logger.debug(f"Первые 200 символов исходного кода: {code_content[:200]}")
        
        # ВАЖНО: Извлекаем все текстовое содержимое из HTML, включая содержимое между тегами
        # Это гарантирует, что мы не потеряем части кода при удалении HTML тегов
        
        # Сначала декодируем HTML-сущности
        from html import unescape
        code_content = unescape(code_content)
        
        # Извлекаем текстовое содержимое, заменяя блочные теги на переносы строк
        # Это сохраняет структуру кода, но убирает HTML разметку
        
        # Заменяем блочные теги на переносы строк (сохраняем содержимое между тегами)
        # <p>текст</p> -> текст\n
        code_content = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n', code_content, flags=re.DOTALL | re.IGNORECASE)
        code_content = re.sub(r'<div[^>]*>(.*?)</div>', r'\1\n', code_content, flags=re.DOTALL | re.IGNORECASE)
        code_content = re.sub(r'<br[^>]*/?>', '\n', code_content, flags=re.IGNORECASE)
        
        # Удаляем оставшиеся HTML теги (но сохраняем их содержимое, если оно есть)
        # Используем более умный подход - извлекаем содержимое из тегов перед удалением
        def extract_text_from_tags(text):
            """Извлекает текстовое содержимое из HTML, сохраняя структуру"""
            result = []
            i = 0
            while i < len(text):
                if text[i] == '<':
                    # Найден тег, пропускаем его
                    tag_end = text.find('>', i)
                    if tag_end == -1:
                        # Незакрытый тег, добавляем как есть
                        result.append(text[i])
                        i += 1
                    else:
                        # Пропускаем весь тег
                        i = tag_end + 1
                else:
                    # Обычный символ, добавляем
                    result.append(text[i])
                    i += 1
            return ''.join(result)
        
        code_content = extract_text_from_tags(code_content)
        
        # Очищаем код от лишних пустых строк (более 2 подряд заменяем на 1)
        # Это убирает большие отступы между строками кода
        code_content = re.sub(r'\n{3,}', '\n', code_content)
        
        # Убираем пробелы в начале и конце, но сохраняем структуру
        code_content = code_content.strip()
        
        # Экранируем HTML символы в коде (теперь безопасно, т.к. HTML теги уже удалены)
        # Важно: экранируем в правильном порядке - сначала &, потом < и >
        code_content = code_content.replace('&', '&amp;')
        code_content = code_content.replace('<', '&lt;')
        code_content = code_content.replace('>', '&gt;')
        
        # Создаем правильный блок для Telegram
        protected_block = f'<pre><code>{code_content}</code></pre>'
        
        placeholder = f'__CODE_BLOCK_{placeholder_counter}__'
        code_block_placeholders[placeholder] = protected_block
        placeholder_counter += 1
        
        logger.info(f"Защищен блок кода: исходная длина {original_length}, финальная длина {len(code_content)} символов")
        if original_length > len(code_content) + 50:  # Если потеряно более 50 символов
            logger.warning(f"Возможна потеря данных: потеряно {original_length - len(code_content)} символов")
            logger.debug(f"Первые 200 символов финального кода: {code_content[:200]}")
        return placeholder
    
    # Обрабатываем <pre><code> блоки (с любыми атрибутами) и защищаем их
    # Сначала объединяем соседние блоки кода, которые могли быть разбиты редактором
    def merge_adjacent_code_blocks(text):
        """Объединяет соседние блоки <pre><code>...</code></pre> в один"""
        original_length = len(text)
        merge_count = 0
        
        # Ищем паттерн: </code></pre>...<pre><code> (возможно с пробелами/переносами между ними)
        # Это означает, что код был разбит на части
        pattern = r'</code></pre>\s*<pre[^>]*><code[^>]*>'
        
        def merge_blocks(match):
            nonlocal merge_count
            merge_count += 1
            # Найден разрыв между блоками, убираем закрывающие/открывающие теги
            return ''
        
        # Заменяем </code></pre>...<pre><code> на пустую строку (объединяем блоки)
        text = re.sub(pattern, merge_blocks, text, flags=re.IGNORECASE | re.DOTALL)
        
        # Также обрабатываем случаи, когда есть только </pre>...<pre> без <code>
        pattern2 = r'</pre>\s*<pre[^>]*>'
        text = re.sub(pattern2, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        if merge_count > 0:
            logger.info(f"Объединено {merge_count} соседних блоков кода. Длина до: {original_length}, после: {len(text)}")
        
        return text
    
    # Объединяем соседние блоки кода перед обработкой
    text = merge_adjacent_code_blocks(text)
    
    # Используем более надежный метод: находим блоки вручную, учитывая вложенность
    def find_and_protect_code_blocks(text):
        """Находит и защищает все блоки <pre><code>...</code></pre> используя protect_code_block"""
        nonlocal placeholder_counter, code_block_placeholders
        result = []
        i = 0
        while i < len(text):
            # Ищем начало блока <pre> (регистронезависимо)
            pre_start = text.lower().find('<pre', i)
            if pre_start == -1:
                # Больше нет блоков, добавляем остаток текста
                result.append(text[i:])
                break
            
            # Добавляем текст до блока
            result.append(text[i:pre_start])
            
            # Ищем закрывающий тег > для <pre>
            pre_tag_end = text.find('>', pre_start)
            if pre_tag_end == -1:
                # Незакрытый тег, пропускаем
                result.append(text[pre_start])
                i = pre_start + 1
                continue
            
            # Ищем соответствующий закрывающий </pre>, учитывая возможную вложенность
            # Считаем открывающие и закрывающие теги <pre>
            pre_close_start = -1
            depth = 1
            search_pos = pre_tag_end + 1
            
            while depth > 0 and search_pos < len(text):
                next_pre_open = text.lower().find('<pre', search_pos)
                next_pre_close = text.lower().find('</pre>', search_pos)
                
                if next_pre_close == -1:
                    # Нет закрывающего тега, пропускаем
                    break
                
                if next_pre_open != -1 and next_pre_open < next_pre_close:
                    # Найден вложенный <pre>
                    depth += 1
                    search_pos = next_pre_open + 4
                else:
                    # Найден закрывающий </pre>
                    depth -= 1
                    if depth == 0:
                        pre_close_start = next_pre_close
                        break
                    search_pos = next_pre_close + 6
            
            if pre_close_start == -1:
                # Нет закрывающего тега, пропускаем
                result.append(text[pre_start:pre_tag_end + 1])
                i = pre_tag_end + 1
                continue
            
            # Теперь ищем <code> внутри найденного блока <pre>...</pre>
            # Ищем первый <code> после <pre>
            code_start = text.lower().find('<code', pre_tag_end, pre_close_start)
            if code_start == -1:
                # Нет <code>, обрабатываем весь блок <pre>...</pre> как код
                code_start = pre_tag_end + 1
                code_tag_end = pre_tag_end
                code_close_start = pre_close_start
            else:
                # Ищем закрывающий тег > для <code>
                code_tag_end = text.find('>', code_start)
                if code_tag_end == -1 or code_tag_end >= pre_close_start:
                    # Незакрытый тег или он за пределами блока, обрабатываем весь <pre>
                    code_start = pre_tag_end + 1
                    code_tag_end = pre_tag_end
                    code_close_start = pre_close_start
                else:
                    # Ищем закрывающий </code>, учитывая возможные вложенные теги
                    code_close_start = -1
                    code_depth = 1
                    code_search_pos = code_tag_end + 1
                    
                    while code_depth > 0 and code_search_pos < pre_close_start:
                        next_code_open = text.lower().find('<code', code_search_pos, pre_close_start)
                        next_code_close = text.lower().find('</code>', code_search_pos, pre_close_start)
                        
                        if next_code_close == -1:
                            # Нет закрывающего тега, используем конец <pre>
                            code_close_start = pre_close_start
                            break
                        
                        if next_code_open != -1 and next_code_open < next_code_close:
                            # Найден вложенный <code>
                            code_depth += 1
                            code_search_pos = next_code_open + 5
                        else:
                            # Найден закрывающий </code>
                            code_depth -= 1
                            if code_depth == 0:
                                code_close_start = next_code_close
                                break
                            code_search_pos = next_code_close + 7
                    
                    if code_close_start == -1:
                        code_close_start = pre_close_start
            
            # Извлекаем полный блок для обработки через protect_code_block
            full_block = text[pre_start:pre_close_start + 6]
            pre_attrs = text[pre_start + 4:pre_tag_end]
            
            if code_start > pre_tag_end:
                code_attrs = text[code_start + 5:code_tag_end] if code_tag_end > code_start else ''
                code_content = text[code_tag_end + 1:code_close_start]
            else:
                # Нет отдельного <code>, весь контент <pre> - это код
                code_attrs = ''
                code_content = text[pre_tag_end + 1:pre_close_start]
            
            # Создаем объект match для передачи в protect_code_block
            class MatchObj:
                def __init__(self, full, pre_attr, code_attr, content):
                    self.group = lambda n: {
                        0: full,
                        1: pre_attr,
                        2: code_attr,
                        3: content
                    }.get(n, '')
            
            match_obj = MatchObj(full_block, pre_attrs, code_attrs, code_content)
            placeholder = protect_code_block(match_obj)
            result.append(placeholder)
            
            # Переходим к позиции после </pre>
            i = pre_close_start + 6
        
        return ''.join(result)
    
    # Используем новый метод для обработки блоков кода
    text = find_and_protect_code_blocks(text)
    
    # 2. Обрабатываем inline код <code>код</code> (только те, что не внутри <pre>)
    # Пропускаем плейсхолдеры блоков кода
    def replace_inline_code(match):
        code = match.group(1)
        # Пропускаем, если это плейсхолдер блока кода
        if '__CODE_BLOCK_' in code:
            return match.group(0)
        # Убираем вложенные теги из inline кода (они не должны быть там)
        code = re.sub(r'<[^>]+>', '', code)
        # Экранируем HTML в коде
        code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return f'<code>{code}</code>'
    
    # Обрабатываем inline код, но не внутри <pre><code> блоков (они уже защищены)
    # И не внутри плейсхолдеров
    text = re.sub(r'<code>((?:(?!</code>).)*?)</code>', replace_inline_code, text, flags=re.DOTALL)
    
    # 3. Заголовки <h1>-<h6> → <b>текст</b>
    text = re.sub(r'<h[1-6][^>]*>(.*?)</h[1-6]>', r'<b>\1</b>', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 4. Жирный текст <strong>, <b> → <b>текст</b>
    text = re.sub(r'<(strong|b)[^>]*>(.*?)</(strong|b)>', r'<b>\2</b>', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 5. Курсив <em>, <i> → <i>текст</i>
    text = re.sub(r'<(em|i)[^>]*>(.*?)</(em|i)>', r'<i>\2</i>', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 6. Ссылки <a href="...">текст</a> → <a href="...">текст</a> (уже в правильном формате)
    # Но нужно убедиться, что href экранирован правильно
    def fix_link(match):
        href = match.group(1)
        link_text = match.group(2)
        # Экранируем href если нужно (но не двойное экранирование)
        if '&amp;' not in href:
            href = href.replace('&', '&amp;')
        # Убираем HTML теги из текста ссылки (Telegram не поддерживает вложенные теги в ссылках)
        link_text = re.sub(r'<[^>]+>', '', link_text)
        return f'<a href="{href}">{link_text}</a>'
    
    text = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', fix_link, text, flags=re.DOTALL | re.IGNORECASE)
    
    # 7. Списки <ul>, <ol>, <li> → текстовый формат с эмодзи
    def replace_list_item(match):
        item_text = match.group(1)
        # Убираем вложенные теги из текста элемента списка
        item_text = re.sub(r'<[^>]+>', '', item_text)
        return f'• {item_text}\n'
    
    # Обрабатываем элементы списка
    text = re.sub(r'<li[^>]*>(.*?)</li>', replace_list_item, text, flags=re.DOTALL | re.IGNORECASE)
    
    # Удаляем теги списков, оставляя только содержимое
    text = re.sub(r'</?(ul|ol)[^>]*>', '\n', text, flags=re.IGNORECASE)
    
    # 8. Переносы строк <p>, <br>, <div> → перенос строки
    # Оптимизируем параграфы: <p>текст</p> → текст (один перенос между параграфами)
    # Сначала обрабатываем полные параграфы <p>...</p>
    def replace_paragraph(match):
        para_text = match.group(1)
        # Убираем лишние пробелы и переносы в начале и конце
        para_text = para_text.strip()
        # Если параграф пустой, не добавляем перенос
        if not para_text:
            return ''
        return para_text + '\n'
    
    # Заменяем <p>текст</p> на текст с одним переносом в конце
    text = re.sub(r'<p[^>]*>(.*?)</p>', replace_paragraph, text, flags=re.DOTALL | re.IGNORECASE)
    
    # Обрабатываем оставшиеся одиночные теги <p> и </p>
    text = re.sub(r'<p[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    
    # <br> заменяем на одинарный перенос
    text = re.sub(r'<br[^>]*/?>', '\n', text, flags=re.IGNORECASE)
    
    # <div> заменяем на одинарный перенос
    text = re.sub(r'</?div[^>]*>', '\n', text, flags=re.IGNORECASE)
    
    # Убираем множественные переносы строк (более 2 подряд) сразу после обработки параграфов
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Убираем пустые строки между обычным текстом (оставляем только один перенос)
    # Но не трогаем блоки кода (они уже защищены плейсхолдерами)
    # Убираем множественные переносы между непустыми строками
    text = re.sub(r'([^\n])\n\n+([^\n])', r'\1\n\2', text)
    
    # 9. Восстанавливаем защищенные блоки кода ПЕРЕД удалением остальных тегов
    for placeholder, protected_block in code_block_placeholders.items():
        text = text.replace(placeholder, protected_block)
    
    # 10. Удаляем остальные HTML теги (таблицы, iframe и т.д.)
    # Но сохраняем уже обработанные теги Telegram (<b>, <i>, <a>, <code>, <pre>)
    # Сначала защищаем Telegram теги (включая уже восстановленные блоки кода)
    telegram_tags_pattern = r'(<(/)?(b|i|u|s|a|code|pre)[^>]*>)'
    protected_placeholders = {}
    placeholder_counter = 0
    
    def protect_telegram_tag(match):
        nonlocal placeholder_counter
        placeholder = f'__TELEGRAM_TAG_{placeholder_counter}__'
        protected_placeholders[placeholder] = match.group(0)
        placeholder_counter += 1
        return placeholder
    
    text = re.sub(telegram_tags_pattern, protect_telegram_tag, text, flags=re.IGNORECASE)
    
    # Удаляем все оставшиеся HTML теги
    text = re.sub(r'<[^>]+>', '', text)
    
    # Восстанавливаем защищенные Telegram теги
    for placeholder, tag in protected_placeholders.items():
        text = text.replace(placeholder, tag)
    
    # 11. Очищаем множественные переносы строк
    # Убираем более 2 переносов подряд (оставляем максимум 2 для разделения блоков)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Уменьшаем двойные переносы между обычными строками до одинарных
    # Но сохраняем двойные переносы перед и после блоков кода для лучшей читаемости
    # Заменяем двойные переносы на одинарные, но не вокруг блоков кода
    # Сначала защищаем блоки кода
    protected_blocks = {}
    block_num = 0
    
    def protect_code_blocks_for_newline_reduction(match):
        nonlocal block_num
        full_block = match.group(0)
        placeholder = f'__CODE_BLOCK_NL_{block_num}__'
        protected_blocks[placeholder] = full_block
        block_num += 1
        return placeholder
    
    # Защищаем блоки кода с контекстом (включая переносы вокруг них)
    text = re.sub(r'\n*<pre><code>.*?</code></pre>\n*', protect_code_blocks_for_newline_reduction, text, flags=re.DOTALL | re.IGNORECASE)
    
    # Теперь убираем двойные переносы между обычными строками
    text = re.sub(r'\n\n+', '\n', text)
    
    # Восстанавливаем защищенные блоки кода (с двойными переносами для читаемости)
    for placeholder, block in protected_blocks.items():
        # Убираем лишние переносы из блока, оставляя по одному с каждой стороны
        clean_block = block.strip()
        text = text.replace(placeholder, '\n\n' + clean_block + '\n\n')
    
    # Финальная очистка - убираем более 2 переносов подряд
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 11. Декодируем HTML-сущности, которые могли остаться
    text = unescape(text)
    
    # 12. Убираем пробелы в начале и конце
    text = text.strip()
    
    # 13. Валидация HTML тегов - проверяем, что все теги правильно закрыты
    text = validate_telegram_html(text)
    
    logger.info(f"Конвертация завершена. Telegram HTML длина: {len(text)} символов")
    
    return text


def validate_telegram_html(text):
    """
    Валидирует и исправляет HTML разметку для Telegram.
    Удаляет незакрытые теги и исправляет неправильную структуру.
    
    Args:
        text (str): Текст с HTML разметкой
        
    Returns:
        str: Валидированный текст
    """
    if not text:
        return text
    
    import logging
    logger = logging.getLogger(__name__)
    
    # Разрешенные теги Telegram
    allowed_tags = {'b', 'i', 'u', 's', 'a', 'code', 'pre'}
    
    # Сначала защищаем блоки <pre><code>...</code></pre> от разрыва
    pre_code_blocks = []
    block_counter = 0
    
    def protect_pre_code_block(match):
        nonlocal block_counter
        full_block = match.group(0)
        placeholder = f'__PRE_CODE_BLOCK_{block_counter}__'
        pre_code_blocks.append((placeholder, full_block))
        block_counter += 1
        return placeholder
    
    # Защищаем блоки <pre><code>...</code></pre>
    text = re.sub(r'<pre><code>.*?</code></pre>', protect_pre_code_block, text, flags=re.DOTALL | re.IGNORECASE)
    
    # Стек для отслеживания открытых тегов
    tag_stack = []
    result = []
    i = 0
    
    while i < len(text):
        if text[i] == '<':
            # Найден тег
            tag_end = text.find('>', i)
            if tag_end == -1:
                # Незакрытый тег, пропускаем
                logger.warning(f"Найден незакрытый тег на позиции {i}, пропускаем")
                i += 1
                continue
            
            tag_content = text[i:tag_end + 1]
            
            # Проверяем, это открывающий или закрывающий тег
            if tag_content.startswith('</'):
                # Закрывающий тег
                tag_name = tag_content[2:-1].strip().lower()
                if tag_name in allowed_tags:
                    # Ищем соответствующий открывающий тег
                    found = False
                    for j in range(len(tag_stack) - 1, -1, -1):
                        if tag_stack[j] == tag_name:
                            # Найден соответствующий тег
                            tag_stack.pop(j)
                            result.append(tag_content)
                            found = True
                            break
                    if not found:
                        # Нет соответствующего открывающего тега, пропускаем закрывающий
                        logger.warning(f"Найден закрывающий тег </{tag_name}> без открывающего, пропускаем")
                else:
                    # Неразрешенный тег, пропускаем
                    logger.warning(f"Найден неразрешенный закрывающий тег </{tag_name}>, пропускаем")
            else:
                # Открывающий тег или самозакрывающийся
                if tag_content.endswith('/>'):
                    # Самозакрывающийся тег (например, <br/>)
                    result.append(tag_content)
                else:
                    # Открывающий тег
                    # Извлекаем имя тега (до пробела или >)
                    tag_name = tag_content[1:].split()[0].split('>')[0].lower()
                    # Для тега <a> проверяем наличие href
                    if tag_name == 'a':
                        if 'href=' in tag_content.lower():
                            tag_stack.append(tag_name)
                            result.append(tag_content)
                        else:
                            logger.warning(f"Найден тег <a> без href, пропускаем")
                    elif tag_name in allowed_tags:
                        tag_stack.append(tag_name)
                        result.append(tag_content)
                    else:
                        # Неразрешенный тег, пропускаем
                        logger.warning(f"Найден неразрешенный тег <{tag_name}>, пропускаем")
            
            i = tag_end + 1
        else:
            # Обычный символ
            result.append(text[i])
            i += 1
    
    # Закрываем все незакрытые теги
    while tag_stack:
        tag = tag_stack.pop()
        result.append(f'</{tag}>')
        logger.warning(f"Добавлен закрывающий тег </{tag}> для незакрытого открывающего")
    
    validated_text = ''.join(result)
    
    # Восстанавливаем защищенные блоки <pre><code>
    for placeholder, block in pre_code_blocks:
        validated_text = validated_text.replace(placeholder, block)
    
    # Финальная проверка - убираем пустые теги типа <code></code>
    validated_text = re.sub(r'<code>\s*</code>', '', validated_text)
    validated_text = re.sub(r'<pre>\s*</pre>', '', validated_text)
    
    return validated_text


def truncate_telegram_text(text, max_length=4096, post_url=None, is_caption=False):
    """
    Умная обрезка текста для Telegram с сохранением форматирования.
    
    Args:
        text (str): Текст с HTML разметкой для Telegram
        max_length (int): Максимальная длина (4096 для сообщения, 1024 для caption)
        post_url (str, optional): URL поста для добавления ссылки в текст
        is_caption (bool): True если это caption для медиа (лимит 1024)
        
    Returns:
        str: Обрезанный текст с ссылкой на полную версию
    """
    if not text:
        return text
    
    import logging
    logger = logging.getLogger(__name__)
    
    # Для caption лимит 1024
    if is_caption:
        max_length = 1024
    
    # Текст для ссылки "Читать полностью"
    read_more_text = '\n\n📖 <a href="{}">Читать полностью на сайте</a>'
    if post_url:
        read_more_link = read_more_text.format(post_url)
    else:
        read_more_link = '\n\n📖 Читать полностью на сайте'
    
    # Если текст уже в пределах лимита, просто добавляем ссылку
    if len(text) <= max_length:
        # Проверяем, не превысит ли добавление ссылки лимит
        if len(text) + len(read_more_link) <= max_length:
            return text + read_more_link
        else:
            # Если ссылка не влезает, возвращаем текст как есть
            return text
    
    logger.info(f"Текст превышает лимит: {len(text)} > {max_length}, начинаем обрезку")
    
    # Текст для ссылки "Читать полностью"
    read_more_text = '\n\n📖 <a href="{}">Читать полностью на сайте</a>'
    if post_url:
        read_more_link = read_more_text.format(post_url)
    else:
        read_more_link = '\n\n📖 Читать полностью на сайте'
    
    # Резервируем место для ссылки
    reserved_length = len(read_more_link)
    available_length = max_length - reserved_length
    
    if available_length < 100:  # Минимум 100 символов для текста
        available_length = max_length - 50  # Уменьшаем резерв
        read_more_link = '\n\n📖 <a href="{}">Читать далее</a>'.format(post_url) if post_url else '\n\n📖 Читать далее'
        reserved_length = len(read_more_link)
        available_length = max_length - reserved_length
    
    # Ищем место для обрезки, не разрывая блоки кода, заголовки, списки
    # Ищем последний полный блок/элемент до лимита
    
    # 1. Проверяем, есть ли блоки кода <pre><code>...</code></pre>
    code_block_pattern = r'<pre><code>.*?</code></pre>'
    code_blocks = list(re.finditer(code_block_pattern, text, flags=re.DOTALL))
    
    # Находим позицию обрезки
    cut_position = available_length
    
    # Если есть блоки кода, проверяем, не разрываем ли мы их
    for block in code_blocks:
        block_start = block.start()
        block_end = block.end()
        
        # Если блок кода пересекается с зоной обрезки
        if block_start < cut_position < block_end:
            # Обрезаем до начала блока кода
            cut_position = block_start
            logger.info(f"Обрезка перед блоком кода на позиции {cut_position}")
            break
        # Если блок кода полностью после зоны обрезки, но близко к ней
        elif block_start > cut_position and block_start < available_length + 200:
            # Если блок кода начинается близко к зоне обрезки, обрезаем до него
            if block_start - cut_position < 100:
                cut_position = block_start
                logger.info(f"Обрезка перед блоком кода на позиции {cut_position} (близко к лимиту)")
                break
    
    # Ищем последний полный элемент (заголовок, абзац, элемент списка)
    # Ищем последний перенос строки перед cut_position
    last_newline = text.rfind('\n', 0, cut_position)
    if last_newline > available_length * 0.7:  # Если перенос строки не слишком далеко от начала
        cut_position = last_newline
        logger.info(f"Обрезка на последнем переносе строки: {cut_position}")
    
    # Обрезаем текст
    truncated = text[:cut_position].rstrip()
    
    # Проверяем, не разорвали ли мы блок кода
    # Ищем незакрытые блоки <pre><code>
    unclosed_pre = truncated.count('<pre>') - truncated.count('</pre>')
    unclosed_code = truncated.count('<code>') - truncated.count('</code>')
    
    # Если есть незакрытые блоки, обрезаем до последнего полного блока
    if unclosed_pre > 0 or unclosed_code > 0:
        # Ищем последний полный блок <pre><code>...</code></pre>
        last_complete_block = truncated.rfind('</pre>')
        if last_complete_block != -1:
            # Находим начало этого блока
            block_start = truncated.rfind('<pre>', 0, last_complete_block)
            if block_start != -1:
                # Обрезаем до начала незавершенного блока
                truncated = truncated[:block_start].rstrip()
                logger.info(f"Обрезка до последнего полного блока кода на позиции {block_start}")
    
    # Убираем незакрытые теги в конце (если обрезали посередине тега)
    # Используем более надежный метод - находим все открытые теги и закрываем их
    open_tags = []
    i = 0
    while i < len(truncated):
        if truncated[i] == '<':
            tag_end = truncated.find('>', i)
            if tag_end == -1:
                # Незакрытый тег, обрезаем до него
                truncated = truncated[:i].rstrip()
                logger.info(f"Удален незакрытый тег на позиции {i}, новая длина: {len(truncated)}")
                break
            
            tag_content = truncated[i:tag_end + 1]
            
            if tag_content.startswith('</'):
                # Закрывающий тег
                tag_name = tag_content[2:-1].strip().lower()
                if tag_name in open_tags:
                    open_tags.remove(tag_name)
            elif not tag_content.endswith('/>'):
                # Открывающий тег
                tag_name = tag_content[1:].split()[0].split('>')[0].lower()
                if tag_name in ['b', 'i', 'u', 's', 'a', 'code', 'pre']:
                    open_tags.append(tag_name)
            
            i = tag_end + 1
        else:
            i += 1
    
    # Закрываем все незакрытые теги перед добавлением ссылки
    if open_tags:
        closing_tags = ''.join([f'</{tag}>' for tag in reversed(open_tags)])
        truncated = truncated + closing_tags
        logger.info(f"Закрыты незакрытые теги: {', '.join(open_tags)}")
    
    # Добавляем ссылку
    result = truncated + read_more_link
    
    # Проверяем финальную длину
    if len(result) > max_length:
        # Если все еще превышает, обрезаем более агрессивно
        excess = len(result) - max_length
        truncated = truncated[:-excess].rstrip()
        result = truncated + read_more_link
        
        # Если все еще не влезает, укорачиваем ссылку
        if len(result) > max_length:
            read_more_link_short = '\n\n📖 <a href="{}">Далее</a>'.format(post_url) if post_url else '\n\n📖 Далее'
            result = truncated + read_more_link_short
    
    # Валидируем результат перед возвратом
    result = validate_telegram_html(result)
    
    logger.info(f"Обрезка завершена. Итоговая длина: {len(result)} символов")
    
    return result 