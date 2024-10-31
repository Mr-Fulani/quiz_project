import aiohttp
from aiogram import Router, F
from aiogram.types import Message
from config import WEBHOOK_URL  # Убедитесь, что URL вебхука добавлен в config.py

router = Router()


@router.message(F.photo & F.caption)
async def handle_image_with_caption(message: Message):
    # Получаем фото (последний элемент в массиве - самое большое разрешение)
    photo = message.photo[-1]
    caption = message.caption

    # Получаем URL файла изображения
    file_info = await message.bot.get_file(photo.file_id)
    file_url = f"{message.bot.session.api.server}/file/bot{message.bot.token}/{file_info.file_path}"

    # Данные для отправки на вебхук
    data = {
        "caption": caption,
        "file_url": file_url
    }

    # Отправляем данные через вебхук
    async with aiohttp.ClientSession() as session:
        async with session.post(WEBHOOK_URL, json=data) as response:
            if response.status == 200:
                await message.answer("Изображение и текст успешно отправлены!")
            else:
                await message.answer("Ошибка при отправке данных на вебхук.")