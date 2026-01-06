from PIL import Image, ImageDraw, ImageFont
import os
import re
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