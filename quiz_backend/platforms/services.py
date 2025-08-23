# platforms/services.py

import asyncio
import logging
import tempfile
import os
from typing import Optional, List, Dict, Any
from django.conf import settings
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from .models import TelegramGroup

logger = logging.getLogger(__name__)


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
        Отправляет медиафайлы в канал (каждый тип отдельно).
        """
        try:
            from aiogram.types import InputMediaPhoto, InputMediaAnimation, InputMediaVideo
            
            logger.info(f"Начинаем отправку медиа в канал {channel.group_name}")
            logger.info(f"Photos count: {len(photos) if photos else 0}")
            logger.info(f"Gifs count: {len(gifs) if gifs else 0}")
            logger.info(f"Videos count: {len(videos) if videos else 0}")
            
            temp_files = []
            text_sent = False
            
            # Отправляем фотографии как медиагруппу
            if photos:
                logger.info(f"Обрабатываем {len(photos)} фотографий")
                photo_group = []
                for i, photo in enumerate(photos):
                    logger.info(f"Обрабатываем фото {i+1}: {photo.name}, размер: {photo.size}")
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                        for chunk in photo.chunks():
                            temp_file.write(chunk)
                        temp_file_path = temp_file.name
                        temp_files.append(temp_file_path)
                        logger.info(f"Создан временный файл: {temp_file_path}")
                    
                    # Медиа отправляем без текста
                    photo_group.append(InputMediaPhoto(
                        media=FSInputFile(path=temp_file_path)
                    ))
                
                logger.info(f"Отправляем группу из {len(photo_group)} фотографий")
                if photo_group:
                    try:
                        await self.bot.send_media_group(
                            chat_id=channel.group_id,
                            media=photo_group
                        )
                        logger.info("Медиагруппа успешно отправлена")
                        text_sent = True
                    except Exception as e:
                        logger.error(f"Ошибка при отправке медиагруппы: {e}")
                        raise
            
            # Отправляем GIF отдельно (не в медиагруппе)
            if gifs:
                for i, gif in enumerate(gifs):
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.gif') as temp_file:
                        for chunk in gif.chunks():
                            temp_file.write(chunk)
                        temp_file_path = temp_file.name
                        temp_files.append(temp_file_path)
                    
                    await self.bot.send_animation(
                        chat_id=channel.group_id,
                        animation=FSInputFile(path=temp_file_path)
                    )
            
            # Отправляем видео как медиагруппу
            if videos:
                video_group = []
                for i, video in enumerate(videos):
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                        for chunk in video.chunks():
                            temp_file.write(chunk)
                        temp_file_path = temp_file.name
                        temp_files.append(temp_file_path)
                    
                    # Создаем обложку для видео (первый кадр)
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as thumb_file:
                        # Для простоты используем тот же файл как обложку
                        # В реальности здесь должна быть генерация thumbnail
                        thumb_file_path = temp_file_path
                        temp_files.append(thumb_file_path)
                    
                    # Медиа отправляем без текста, но с обложкой
                    video_group.append(InputMediaVideo(
                        media=FSInputFile(path=temp_file_path),
                        thumb=FSInputFile(path=thumb_file_path)
                    ))
                
                if video_group:
                    await self.bot.send_media_group(
                        chat_id=channel.group_id,
                        media=video_group
                    )
                    text_sent = True
            
            # Если есть кнопки, отправляем их отдельным сообщением
            if reply_markup:
                if text:
                    # Отправляем текст с кнопками
                    await self.bot.send_message(
                        chat_id=channel.group_id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                else:
                    # Если нет текста, отправляем только кнопки с минимальным символом
                    await self.bot.send_message(
                        chat_id=channel.group_id,
                        text="🔗",
                        reply_markup=reply_markup
                    )
            elif text:
                # Если есть текст, но нет кнопок
                await self.bot.send_message(
                    chat_id=channel.group_id,
                    text=text,
                    parse_mode="HTML"
                )
            
            # Удаляем временные файлы
            for temp_file_path in temp_files:
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            
            logger.info(f"Медиафайлы успешно отправлены в канал {channel.group_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отправке медиафайлов в канал {channel.group_name}: {e}")
            # Удаляем временные файлы в случае ошибки
            for temp_file_path in temp_files:
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
