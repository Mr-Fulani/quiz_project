# platforms/services.py

import asyncio
import logging
import tempfile
import os
import re
from typing import Optional, List, Dict, Any
from django.conf import settings
from django.db.models import Count
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from .models import TelegramGroup
from accounts.models import TelegramUser

logger = logging.getLogger(__name__)


def markdown_to_telegram_html(text: str) -> str:
    """
    Конвертирует Markdown разметку в HTML для Telegram.
    
    Поддерживает:
    - Заголовки: ## текст → <b>текст</b>
    - Inline код: `код` → <code>код</code>
    - Блоки кода: ```python\nкод\n``` → <pre>код</pre>
    - Жирный текст: **текст** → <b>текст</b>
    - Курсив: *текст* → <i>текст</i>
    - Ссылки: [текст](url) → <a href="url">текст</a>
    
    Args:
        text (str): Текст с Markdown разметкой
        
    Returns:
        str: Текст с HTML разметкой для Telegram
    """
    if not text:
        return text
    
    logger.info(f"Конвертация Markdown → HTML. Исходная длина: {len(text)} символов")
    original_text = text
    
    # 1. Обрабатываем блоки кода: ```language\nкод\n```
    # Паттерн должен быть гибким: ```python или ``` затем любой текст до ```
    def replace_code_block(match):
        language = match.group(1) or ''
        code = match.group(2).strip()
        # Экранируем HTML в коде
        code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        logger.info(f"Найден блок кода (язык: {language or 'не указан'}), длина: {len(code)} символов")
        # Сохраняем информацию о языке в атрибуте data-lang для возможного использования
        # Telegram HTML не поддерживает data-атрибуты напрямую, но можно добавить в комментарий или использовать другой способ
        if language:
            # Добавляем язык как часть структуры (можно использовать <code> внутри <pre>)
            return f'<pre><code class="language-{language}">{code}</code></pre>'
        else:
            return f'<pre><code>{code}</code></pre>'
    
    # Ищем ```язык или просто ``` , затем любой текст (включая переносы), затем ```
    text = re.sub(r'```(\w+)?[\r\n]+(.*?)[\r\n]+```', replace_code_block, text, flags=re.DOTALL)
    
    # 1.5. Обрабатываем существующие HTML блоки кода <pre><code>
    # Если в тексте уже есть HTML теги, конвертируем их в формат Telegram
    def replace_html_code_block(match):
        pre_attrs = match.group(1) or ''
        code_attrs = match.group(2) or ''
        code_content = match.group(3)
        # Извлекаем язык из класса если есть
        lang_match = re.search(r'language-(\w+)', code_attrs)
        language = lang_match.group(1) if lang_match else ''
        # Экранируем HTML в коде
        code_content = code_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        if language:
            return f'<pre><code class="language-{language}">{code_content}</code></pre>'
        else:
            return f'<pre><code>{code_content}</code></pre>'
    
    # Обрабатываем <pre><code> блоки
    text = re.sub(
        r'<pre([^>]*)><code([^>]*)>(.*?)</code></pre>',
        replace_html_code_block,
        text,
        flags=re.DOTALL
    )
    
    # 2. Inline код: `код`
    def replace_inline_code(match):
        code = match.group(1)
        # Экранируем HTML в коде
        code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return f'<code>{code}</code>'
    
    inline_code_count = len(re.findall(r'`([^`]+)`', text))
    if inline_code_count > 0:
        logger.info(f"Найдено inline кода: {inline_code_count}")
    text = re.sub(r'`([^`]+)`', replace_inline_code, text)
    
    # 3. Заголовки: ## текст → жирный текст (Telegram не поддерживает h1-h6)
    headers_count = len(re.findall(r'^#{1,6}\s+(.+)$', text, flags=re.MULTILINE))
    if headers_count > 0:
        logger.info(f"Найдено заголовков: {headers_count}")
    text = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    # 4. Жирный текст: **текст**
    bold_count = len(re.findall(r'\*\*(.*?)\*\*', text, flags=re.DOTALL))
    if bold_count > 0:
        logger.info(f"Найдено жирного текста (**): {bold_count}")
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    
    # 5. Курсив: *текст* (но не **текст**)
    italic_count = len(re.findall(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', text))
    if italic_count > 0:
        logger.info(f"Найдено курсива (*): {italic_count}")
    text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<i>\1</i>', text)
    
    # 6. Ссылки: [текст](url)
    links_count = len(re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text))
    if links_count > 0:
        logger.info(f"Найдено ссылок: {links_count}")
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    
    logger.info(f"Конвертация завершена. HTML длина: {len(text)} символов (было {len(original_text)})")
    logger.debug(f"Первые 200 символов HTML: {text[:200]}")
    
    return text


class TelegramPostService:
    """
    Сервис для отправки постов в Telegram каналы/группы.
    """
    
    def __init__(self, bot_token: str):
        """
        Инициализация сервиса с токеном бота.
        
        Args:
            bot_token (str): Токен Telegram бота
        """
        self.bot = Bot(token=bot_token)
    
    async def send_post(
        self,
        channel: TelegramGroup,
        text: Optional[str] = None,
        photos: Optional[Any] = None,
        gifs: Optional[Any] = None,
        videos: Optional[Any] = None,
        buttons: Optional[List[Dict[str, str]]] = None
    ) -> bool:
        """
        Отправляет пост в Telegram канал/группу.
        
        Args:
            channel (TelegramGroup): Канал/группа для отправки
            text (str, optional): Текст поста
            photo: Файл изображения
            gif: Файл GIF
            video: Файл видео
            buttons (List[Dict], optional): Список кнопок [{'text': '...', 'url': '...'}]
            
        Returns:
            bool: True если отправка успешна, False в противном случае
        """
        try:
            # Создаем inline клавиатуру если есть кнопки
            reply_markup = None
            if buttons:
                reply_markup = self._create_inline_keyboard(buttons)
            
            # Определяем тип медиа и отправляем
            logger.info(f"Отправка поста в канал {channel.group_name}")
            logger.info(f"Photos: {photos}, Gifs: {gifs}, Videos: {videos}, Text: {text}")
            
            if photos or gifs or videos:
                return await self._send_media_group(channel, photos, gifs, videos, text, reply_markup)
            elif text:
                return await self._send_text(channel, text, reply_markup)
            else:
                logger.error("Не указан текст или медиафайл для отправки")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при отправке поста в канал {channel.group_name}: {e}")
            return False
    
    def _create_inline_keyboard(self, buttons: List[Dict[str, str]]) -> InlineKeyboardMarkup:
        """
        Создает inline клавиатуру из списка кнопок с красивым оформлением.
        
        Args:
            buttons (List[Dict]): Список кнопок [{'text': '...', 'url': '...'}]
            
        Returns:
            InlineKeyboardMarkup: Объект клавиатуры
        """
        keyboard = []
        for i, button in enumerate(buttons):
            if button.get('text') and button.get('url'):
                # Добавляем эмодзи к кнопкам для красоты
                emoji = "🔗" if i == 0 else "⚡"
                button_text = f"{emoji} {button['text']}"
                
                keyboard.append([
                    InlineKeyboardButton(
                        text=button_text,
                        url=button['url']
                    )
                ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
    
    async def _send_media_group(
        self,
        channel: TelegramGroup,
        photos,
        gifs,
        videos,
        text: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """
        Отправляет одно медиа в канал с текстом и кнопками.
        Приоритет: фото > GIF > видео. Текст и кнопки всегда прикрепляются к медиа.
        Если текст превышает лимит Telegram (1024 символа), он обрезается или отправляется отдельно.
        """
        try:
            logger.info(f"Начинаем отправку медиа в канал {channel.group_name}")
            logger.info(f"Photos count: {len(photos) if photos else 0}")
            logger.info(f"Gifs count: {len(gifs) if gifs else 0}")
            logger.info(f"Videos count: {len(videos) if videos else 0}")
            
            # Telegram ограничение на длину caption: 1024 символа
            MAX_CAPTION_LENGTH = 1024
            
            # Конвертируем Markdown в HTML для Telegram
            caption = markdown_to_telegram_html(text) if text else None
            
            if caption:
                logger.debug(f"HTML для отправки (первые 300 символов): {caption[:300]}")
                if len(caption) > 1024:
                    logger.warning(f"Текст превышает лимит caption: {len(caption)} символов")
                else:
                    logger.info(f"Длина caption: {len(caption)} символов (в пределах лимита)")
            
            temp_file_path = None
            
            try:
                # Отправляем только первое фото (если есть)
                if photos and len(photos) > 0:
                    photo = photos[0]
                    logger.info(f"Обрабатываем фото: {photo.name}, размер: {photo.size}")
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                        for chunk in photo.chunks():
                            temp_file.write(chunk)
                        temp_file_path = temp_file.name
                        logger.info(f"Создан временный файл: {temp_file_path}")
                    
                    await self.bot.send_photo(
                        chat_id=channel.group_id,
                        photo=FSInputFile(path=temp_file_path),
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                    logger.info("Фото успешно отправлено с текстом и кнопками")
                    return True
                
                # Отправляем только первый GIF (если нет фото)
                if gifs and len(gifs) > 0:
                    gif = gifs[0]
                    logger.info(f"Обрабатываем GIF: {gif.name}")
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.gif') as temp_file:
                        for chunk in gif.chunks():
                            temp_file.write(chunk)
                        temp_file_path = temp_file.name
                    
                    await self.bot.send_animation(
                        chat_id=channel.group_id,
                        animation=FSInputFile(path=temp_file_path),
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                    logger.info("GIF успешно отправлен с текстом и кнопками")
                    return True
                
                # Отправляем только первое видео (если нет фото и GIF)
                if videos and len(videos) > 0:
                    video = videos[0]
                    logger.info(f"Обрабатываем видео: {video.name}")
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                        for chunk in video.chunks():
                            temp_file.write(chunk)
                        temp_file_path = temp_file.name
                    
                    await self.bot.send_video(
                        chat_id=channel.group_id,
                        video=FSInputFile(path=temp_file_path),
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                    logger.info("Видео успешно отправлено с текстом и кнопками")
                    return True
                
                # Если нет медиа, но есть текст - отправляем только текст с кнопками
                if caption:
                    await self.bot.send_message(
                        chat_id=channel.group_id,
                        text=caption,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                    logger.info("Текст успешно отправлен с кнопками")
                    return True
                
                logger.error("Не указан текст или медиафайл для отправки")
                return False
                
            finally:
                # Удаляем временный файл
                if temp_file_path:
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass
            
        except Exception as e:
            logger.error(f"Ошибка при отправке медиафайлов в канал {channel.group_name}: {e}")
            # Удаляем временный файл в случае ошибки
            if temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            return False

    async def _send_photo(
        self,
        channel: TelegramGroup,
        photo,
        text: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """
        Отправляет фото в канал.
        """
        try:
            # Сохраняем временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                for chunk in photo.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            # Создаем FSInputFile для aiogram 3.x
            input_file = FSInputFile(path=temp_file_path)
            
            # Отправляем фото
            await self.bot.send_photo(
                chat_id=channel.group_id,
                photo=input_file,
                caption=text,
                reply_markup=reply_markup
            )
            
            # Удаляем временный файл
            os.unlink(temp_file_path)
            
            logger.info(f"Фото успешно отправлено в канал {channel.group_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отправке фото в канал {channel.group_name}: {e}")
            return False
    
    async def _send_animation(
        self,
        channel: TelegramGroup,
        gif,
        text: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """
        Отправляет GIF анимацию в канал.
        """
        try:
            # Сохраняем временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix='.gif') as temp_file:
                for chunk in gif.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            # Создаем FSInputFile для aiogram 3.x
            input_file = FSInputFile(path=temp_file_path)
            
            # Отправляем анимацию
            await self.bot.send_animation(
                chat_id=channel.group_id,
                animation=input_file,
                caption=text,
                reply_markup=reply_markup
            )
            
            # Удаляем временный файл
            os.unlink(temp_file_path)
            
            logger.info(f"GIF успешно отправлен в канал {channel.group_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отправке GIF в канал {channel.group_name}: {e}")
            return False
    
    async def _send_video(
        self,
        channel: TelegramGroup,
        video,
        text: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """
        Отправляет видео в канал.
        """
        try:
            # Сохраняем временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                for chunk in video.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            # Создаем FSInputFile для aiogram 3.x
            input_file = FSInputFile(path=temp_file_path)
            
            # Отправляем видео
            await self.bot.send_video(
                chat_id=channel.group_id,
                video=input_file,
                caption=text,
                reply_markup=reply_markup
            )
            
            # Удаляем временный файл
            os.unlink(temp_file_path)
            
            logger.info(f"Видео успешно отправлено в канал {channel.group_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отправке видео в канал {channel.group_name}: {e}")
            return False
    
    async def _send_text(
        self,
        channel: TelegramGroup,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """
        Отправляет текстовое сообщение в канал.
        """
        try:
            await self.bot.send_message(
                chat_id=channel.group_id,
                text=text,
                reply_markup=reply_markup
            )
            
            logger.info(f"Текст успешно отправлен в канал {channel.group_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отправке текста в канал {channel.group_name}: {e}")
            return False
    
    async def close(self):
        """
        Закрывает соединение с ботом.
        """
        await self.bot.session.close()


def get_telegram_bot_token() -> str:
    """
    Получает токен Telegram бота из настроек.
    
    Returns:
        str: Токен бота
    """
    # Здесь нужно получить токен из настроек
    # Пока используем заглушку
    return getattr(settings, 'TELEGRAM_BOT_TOKEN', '')


async def send_telegram_post_async(
    channel: TelegramGroup,
    text: Optional[str] = None,
    photos=None,
    gifs=None,
    videos=None,
    buttons: Optional[List[Dict[str, str]]] = None
) -> bool:
    """
    Асинхронная функция для отправки поста в Telegram.
    
    Args:
        channel (TelegramGroup): Канал/группа для отправки
        text (str, optional): Текст поста
        photo: Файл изображения
        gif: Файл GIF
        video: Файл видео
        buttons (List[Dict], optional): Список кнопок
        
    Returns:
        bool: True если отправка успешна, False в противном случае
    """
    bot_token = get_telegram_bot_token()
    if not bot_token:
        logger.error("Токен Telegram бота не настроен")
        return False
    
    service = TelegramPostService(bot_token)
    try:
        result = await service.send_post(channel, text, photos, gifs, videos, buttons)
        return result
    finally:
        await service.close()


def send_telegram_post_sync(
    channel: TelegramGroup,
    text: Optional[str] = None,
    photos=None,
    gifs=None,
    videos=None,
    buttons: Optional[List[Dict[str, str]]] = None
) -> bool:
    """
    Синхронная функция для отправки поста в Telegram.
    
    Args:
        channel (TelegramGroup): Канал/группа для отправки
        text (str, optional): Текст поста
        photo: Файл изображения
        gif: Файл GIF
        video: Файл видео
        buttons (List[Dict], optional): Список кнопок
        
    Returns:
        bool: True если отправка успешна, False в противном случае
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            send_telegram_post_async(channel, text, photos, gifs, videos, buttons)
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка при синхронной отправке поста: {e}")
        return False
    finally:
        loop.close()


async def send_post_to_user_async(
    user_id: int,
    text: Optional[str] = None,
    photos=None,
    gifs=None,
    videos=None,
    buttons: Optional[List[Dict[str, str]]] = None
) -> bool:
    """
    Асинхронная функция для отправки поста пользователю в личные сообщения.
    
    Args:
        user_id (int): Telegram ID пользователя
        text (str, optional): Текст поста
        photos: Список файлов изображений
        gifs: Список файлов GIF
        videos: Список файлов видео
        buttons (List[Dict], optional): Список кнопок
        
    Returns:
        bool: True если отправка успешна, False в противном случае
    """
    bot_token = get_telegram_bot_token()
    if not bot_token:
        logger.error("Токен Telegram бота не настроен")
        return False
    
    bot = Bot(token=bot_token)
    try:
        # Создаем inline клавиатуру если есть кнопки
        reply_markup = None
        if buttons:
            keyboard = []
            for i, button in enumerate(buttons):
                if button.get('text') and button.get('url'):
                    emoji = "🔗" if i == 0 else "⚡"
                    button_text = f"{emoji} {button['text']}"
                    keyboard.append([
                        InlineKeyboardButton(
                            text=button_text,
                            url=button['url']
                        )
                    ])
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
        
        # Telegram ограничение на длину caption: 1024 символа
        MAX_CAPTION_LENGTH = 1024
        # Telegram ограничение на длину текстового сообщения: 4096 символов
        MAX_MESSAGE_LENGTH = 4096
        
        temp_files = []
        text_sent = False
        remaining_text = None
        
        try:
            # Конвертируем Markdown в HTML для Telegram
            caption_text = markdown_to_telegram_html(text) if text else None
            
            # Отправляем медиафайлы
            # Сохраняем файлы во временные файлы перед отправкой
            if photos:
                for i, photo in enumerate(photos):
                    # Сбрасываем позицию файла на начало
                    if hasattr(photo, 'seek'):
                        photo.seek(0)
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                        for chunk in photo.chunks():
                            temp_file.write(chunk)
                        temp_file_path = temp_file.name
                        temp_files.append(temp_file_path)
                    
                    # Отправляем первое фото с текстом, остальные без
                    caption = caption_text if i == 0 and caption_text and not text_sent else None
                    if caption:
                        text_sent = True
                    
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile(path=temp_file_path),
                        caption=caption,
                        reply_markup=reply_markup if i == len(photos) - 1 and not text_sent else None,
                        parse_mode="HTML"
                    )
            
            if gifs:
                for i, gif in enumerate(gifs):
                    # Сбрасываем позицию файла на начало
                    if hasattr(gif, 'seek'):
                        gif.seek(0)
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.gif') as temp_file:
                        for chunk in gif.chunks():
                            temp_file.write(chunk)
                        temp_file_path = temp_file.name
                        temp_files.append(temp_file_path)
                    
                    caption = caption_text if i == 0 and caption_text and not text_sent else None
                    if caption:
                        text_sent = True
                    
                    await bot.send_animation(
                        chat_id=user_id,
                        animation=FSInputFile(path=temp_file_path),
                        caption=caption,
                        reply_markup=reply_markup if i == len(gifs) - 1 and not text_sent else None,
                        parse_mode="HTML"
                    )
            
            if videos:
                for i, video in enumerate(videos):
                    # Сбрасываем позицию файла на начало
                    if hasattr(video, 'seek'):
                        video.seek(0)
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                        for chunk in video.chunks():
                            temp_file.write(chunk)
                        temp_file_path = temp_file.name
                        temp_files.append(temp_file_path)
                    
                    caption = caption_text if i == 0 and caption_text and not text_sent else None
                    if caption:
                        text_sent = True
                    
                    await bot.send_video(
                        chat_id=user_id,
                        video=FSInputFile(path=temp_file_path),
                        caption=caption,
                        reply_markup=reply_markup if i == len(videos) - 1 and not text_sent else None,
                        parse_mode="HTML"
                    )
            
            # Отправляем текст, если он еще не был отправлен
            if caption_text and not text_sent:
                await bot.send_message(
                    chat_id=user_id,
                    text=caption_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
            
            return True
            
        except Exception as e:
            # Игнорируем ошибки типа "bot was blocked" или "user not found"
            error_str = str(e).lower()
            if "bot was blocked" in error_str or "user not found" in error_str or "chat not found" in error_str or "forbidden" in error_str:
                logger.debug(f"Пользователь {user_id} заблокировал бота или не найден: {e}")
            else:
                logger.error(f"Ошибка при отправке поста пользователю {user_id}: {e}")
            return False
        finally:
            # Удаляем временные файлы
            for temp_file_path in temp_files:
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                    
    finally:
        await bot.session.close()


def send_post_to_bot_subscribers(
    text: Optional[str] = None,
    photos=None,
    gifs=None,
    videos=None,
    buttons: Optional[List[Dict[str, str]]] = None
) -> int:
    """
    Отправляет пост всем активным подписчикам бота в личные сообщения.
    
    Args:
        text (str, optional): Текст поста
        photos: Список файлов изображений
        gifs: Список файлов GIF
        videos: Список файлов видео
        buttons (List[Dict], optional): Список кнопок
        
    Returns:
        int: Количество успешно отправленных сообщений
    """
    # Сохраняем все файлы во временные файлы один раз
    temp_photo_files = []
    temp_gif_files = []
    temp_video_files = []
    
    try:
        # Сохраняем фотографии
        if photos:
            for photo in photos:
                if hasattr(photo, 'seek'):
                    photo.seek(0)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    for chunk in photo.chunks():
                        temp_file.write(chunk)
                    temp_photo_files.append(temp_file.name)
        
        # Сохраняем GIF
        if gifs:
            for gif in gifs:
                if hasattr(gif, 'seek'):
                    gif.seek(0)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.gif') as temp_file:
                    for chunk in gif.chunks():
                        temp_file.write(chunk)
                    temp_gif_files.append(temp_file.name)
        
        # Сохраняем видео
        if videos:
            for video in videos:
                if hasattr(video, 'seek'):
                    video.seek(0)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                    for chunk in video.chunks():
                        temp_file.write(chunk)
                    temp_video_files.append(temp_file.name)
        
        # Получаем всех пользователей бота (всех, кто когда-либо взаимодействовал с ботом)
        # Для отправки подписчикам бота используем всех пользователей с telegram_id,
        # так как subscription_status относится к подпискам на каналы, а не к подписке на бота
        subscribers = TelegramUser.objects.filter(telegram_id__isnull=False)
        total_subscribers = subscribers.count()
        
        if total_subscribers == 0:
            logger.warning("Нет пользователей бота в базе данных для отправки поста")
            return 0
        
        # Логируем статистику по статусам для отладки
        status_counts = subscribers.values('subscription_status').annotate(
            count=Count('id')
        )
        logger.info(f"Найдено {total_subscribers} пользователей бота для отправки поста")
        for status_info in status_counts:
            logger.info(f"  - Статус '{status_info['subscription_status']}': {status_info['count']} пользователей")
        
        logger.info(f"Начинаем отправку поста {total_subscribers} подписчикам бота")
        
        # Создаем event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        success_count = 0
        
        try:
            # Отправляем каждому подписчику
            for subscriber in subscribers:
                try:
                    result = loop.run_until_complete(
                        send_post_to_user_with_files(
                            user_id=subscriber.telegram_id,
                            text=text,
                            photo_paths=temp_photo_files,
                            gif_paths=temp_gif_files,
                            video_paths=temp_video_files,
                            buttons=buttons
                        )
                    )
                    if result:
                        success_count += 1
                    
                    # Небольшая задержка между отправками, чтобы не превысить лимиты API
                    if success_count % 10 == 0:
                        logger.info(f"Отправлено {success_count} из {total_subscribers} подписчикам")
                    
                except Exception as e:
                    logger.error(f"Ошибка при отправке подписчику {subscriber.telegram_id}: {e}")
                    continue
            
            logger.info(f"Успешно отправлено {success_count} из {total_subscribers} подписчикам бота")
            return success_count
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Ошибка при отправке поста подписчикам бота: {e}")
        return 0
    finally:
        # Удаляем временные файлы
        for temp_file_path in temp_photo_files + temp_gif_files + temp_video_files:
            try:
                os.unlink(temp_file_path)
            except:
                pass


async def send_post_to_user_with_files(
    user_id: int,
    text: Optional[str] = None,
    photo_paths: Optional[List[str]] = None,
    gif_paths: Optional[List[str]] = None,
    video_paths: Optional[List[str]] = None,
    buttons: Optional[List[Dict[str, str]]] = None
) -> bool:
    """
    Асинхронная функция для отправки поста пользователю в личные сообщения с использованием путей к файлам.
    
    Args:
        user_id (int): Telegram ID пользователя
        text (str, optional): Текст поста
        photo_paths: Список путей к файлам изображений
        gif_paths: Список путей к файлам GIF
        video_paths: Список путей к файлам видео
        buttons (List[Dict], optional): Список кнопок
        
    Returns:
        bool: True если отправка успешна, False в противном случае
    """
    bot_token = get_telegram_bot_token()
    if not bot_token:
        logger.error("Токен Telegram бота не настроен")
        return False
    
    bot = Bot(token=bot_token)
    try:
        # Создаем inline клавиатуру если есть кнопки
        reply_markup = None
        if buttons:
            keyboard = []
            for i, button in enumerate(buttons):
                if button.get('text') and button.get('url'):
                    emoji = "🔗" if i == 0 else "⚡"
                    button_text = f"{emoji} {button['text']}"
                    keyboard.append([
                        InlineKeyboardButton(
                            text=button_text,
                            url=button['url']
                        )
                    ])
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
        
        # Telegram ограничение на длину caption: 1024 символа
        MAX_CAPTION_LENGTH = 1024
        # Telegram ограничение на длину текстового сообщения: 4096 символов
        MAX_MESSAGE_LENGTH = 4096
        
        # Конвертируем Markdown в HTML для Telegram
        caption_text = markdown_to_telegram_html(text) if text else None
        
        text_sent = False
        buttons_sent = False
        
        try:
            # Определяем, есть ли медиафайлы
            has_media = bool(photo_paths or gif_paths or video_paths)
            
            # Отправляем медиафайлы
            if photo_paths:
                for i, photo_path in enumerate(photo_paths):
                    caption = caption_text if i == 0 and caption_text and not text_sent else None
                    if caption:
                        text_sent = True
                    
                    # Кнопки прикрепляем к первому медиа с caption или к последнему, если нет текста
                    should_attach_buttons = (
                        reply_markup and not buttons_sent and (
                            (caption is not None and i == 0) or  # Кнопки с первым медиа, если есть caption
                            (not text and i == len(photo_paths) - 1)  # Кнопки с последним медиа, если нет текста
                        )
                    )
                    
                    if should_attach_buttons:
                        buttons_sent = True
                    
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile(path=photo_path),
                        caption=caption,
                        reply_markup=reply_markup if should_attach_buttons else None,
                        parse_mode="HTML"
                    )
            
            if gif_paths:
                for i, gif_path in enumerate(gif_paths):
                    caption = caption_text if i == 0 and caption_text and not text_sent else None
                    if caption:
                        text_sent = True
                    
                    should_attach_buttons = (
                        reply_markup and not buttons_sent and (
                            (caption is not None and i == 0) or
                            (not text and i == len(gif_paths) - 1)
                        )
                    )
                    
                    if should_attach_buttons:
                        buttons_sent = True
                    
                    await bot.send_animation(
                        chat_id=user_id,
                        animation=FSInputFile(path=gif_path),
                        caption=caption,
                        reply_markup=reply_markup if should_attach_buttons else None,
                        parse_mode="HTML"
                    )
            
            if video_paths:
                for i, video_path in enumerate(video_paths):
                    caption = caption_text if i == 0 and caption_text and not text_sent else None
                    if caption:
                        text_sent = True
                    
                    should_attach_buttons = (
                        reply_markup and not buttons_sent and (
                            (caption is not None and i == 0) or
                            (not text and i == len(video_paths) - 1)
                        )
                    )
                    
                    if should_attach_buttons:
                        buttons_sent = True
                    
                    await bot.send_video(
                        chat_id=user_id,
                        video=FSInputFile(path=video_path),
                        caption=caption,
                        reply_markup=reply_markup if should_attach_buttons else None,
                        parse_mode="HTML"
                    )
            
            # Отправляем текст, если он еще не был отправлен
            if caption_text and not text_sent:
                await bot.send_message(
                    chat_id=user_id,
                    text=caption_text,
                    reply_markup=reply_markup if not buttons_sent else None,
                    parse_mode="HTML"
                )
                if reply_markup and not buttons_sent:
                    buttons_sent = True
            
            return True
            
        except Exception as e:
            # Игнорируем ошибки типа "bot was blocked" или "user not found"
            error_str = str(e).lower()
            if "bot was blocked" in error_str or "user not found" in error_str or "chat not found" in error_str or "forbidden" in error_str:
                logger.debug(f"Пользователь {user_id} заблокировал бота или не найден: {e}")
            else:
                logger.error(f"Ошибка при отправке поста пользователю {user_id}: {e}")
            return False
                    
    finally:
        await bot.session.close()
