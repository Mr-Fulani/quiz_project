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
        photo: Optional[Any] = None,
        gif: Optional[Any] = None,
        video: Optional[Any] = None,
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
            if photo:
                return await self._send_photo(channel, photo, text, reply_markup)
            elif gif:
                return await self._send_animation(channel, gif, text, reply_markup)
            elif video:
                return await self._send_video(channel, video, text, reply_markup)
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
        Создает inline клавиатуру из списка кнопок.
        
        Args:
            buttons (List[Dict]): Список кнопок [{'text': '...', 'url': '...'}]
            
        Returns:
            InlineKeyboardMarkup: Объект клавиатуры
        """
        keyboard = []
        for button in buttons:
            if button.get('text') and button.get('url'):
                keyboard.append([
                    InlineKeyboardButton(
                        text=button['text'],
                        url=button['url']
                    )
                ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
    
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
    photo=None,
    gif=None,
    video=None,
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
        result = await service.send_post(channel, text, photo, gif, video, buttons)
        return result
    finally:
        await service.close()


def send_telegram_post_sync(
    channel: TelegramGroup,
    text: Optional[str] = None,
    photo=None,
    gif=None,
    video=None,
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
            send_telegram_post_async(channel, text, photo, gif, video, buttons)
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка при синхронной отправке поста: {e}")
        return False
    finally:
        loop.close()
