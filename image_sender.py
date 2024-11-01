import aiohttp
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatType  # Для aiogram 3.x
from config import WEBHOOK_URL




# Настройка логирования
logger = logging.getLogger(__name__)



# Создание Router
router = Router()




# Обработчик для сообщений в личных чатах и группах
@router.message(F.photo & F.caption)
async def handle_image_with_caption(message: Message, bot):
    logger.info(f"Получено сообщение с фото и подписью из чата типа: {message.chat.type}")
    if message.chat.type in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await process_message(message, bot)
    else:
        logger.info("Сообщение не из личного чата или группы. Пропуск.")



# Обработчик для сообщений в канале
@router.channel_post(F.photo & F.caption)
async def handle_channel_post(channel_post: Message, bot):
    logger.info("Получено сообщение с фото и подписью из канала.")
    await process_message(channel_post, bot)




# Универсальный обработчик для всех обновлений (для отладки)
@router.update()
async def catch_all_updates(update: Message, bot):
    logger.debug(f"Получено обновление: {update}")




# Общая функция обработки сообщений
async def process_message(message: Message, bot):
    try:
        photo = message.photo[-1]
        caption = message.caption

        # Получаем информацию о файле
        file_info = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
        logger.info(f"URL файла: {file_url}")

        data = {
            "caption": caption,
            "file_url": file_url
        }

        # Отправляем данные на вебхук
        async with aiohttp.ClientSession() as session:
            logger.debug(f"Отправка данных на вебхук: {data}")
            async with session.post(WEBHOOK_URL, json=data) as response:
                response_text = await response.text()
                if response.status == 200:
                    logger.info(f"Данные успешно отправлены на вебхук. Ответ: {response_text}")
                else:
                    logger.error(f"Ошибка при отправке на вебхук. Статус: {response.status}, Ответ: {response_text}")
    except Exception as e:
        logger.exception("Ошибка при обработке сообщения")
