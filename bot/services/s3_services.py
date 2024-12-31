# bot/services/s3_services.py

from typing import Optional
from urllib.parse import urlparse

import aioboto3
import io
import logging
from PIL import Image
from botocore.exceptions import ClientError

import bot
from bot.config import S3_BUCKET_NAME, S3_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY



# Настройка логгера
logger = logging.getLogger(__name__)





async def save_image_to_storage(image: Image.Image, image_name: str, user_chat_id: int) -> Optional[str]:
    """
    Асинхронная загрузка изображения в S3 и возврат URL.
    В случае ошибки отправляется сообщение пользователю.

    Args:
        image (Image.Image): Объект изображения PIL.
        image_name (str): Имя изображения для сохранения в S3.
        user_chat_id (int): ID чата пользователя для уведомления.

    Returns:
        Optional[str]: URL загруженного изображения или None при ошибке.
    """
    try:
        if not isinstance(image, Image.Image):
            logger.error(f"Ожидался объект Image, получен тип {type(image)}")
            await bot.send_message(
                chat_id=user_chat_id,
                text=f"⚠️ Ошибка: Ожидался объект Image, получен тип {type(image)}"
            )
            return None

        # Преобразуем изображение в байты
        image_bytes = io.BytesIO()
        image.save(image_bytes, format='PNG')
        image_bytes.seek(0)

        # Асинхронная загрузка в S3
        session = aioboto3.Session()
        async with session.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=S3_REGION
        ) as s3:
            try:
                # Попытка загрузить с ACL
                await s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=image_name,
                    Body=image_bytes,
                    ContentType='image/png',
                    ACL='public-read'
                )
            except ClientError as e:
                # Проверка на ошибку с ACL
                if e.response['Error']['Code'] == 'AccessControlListNotSupported':
                    logger.warning(f"Бакет {S3_BUCKET_NAME} не поддерживает ACL. Повторная загрузка без ACL.")
                    await s3.put_object(
                        Bucket=S3_BUCKET_NAME,
                        Key=image_name,
                        Body=image_bytes,
                        ContentType='image/png'
                    )
                else:
                    raise e

            # Формируем URL для изображения
            image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{image_name}"
            logger.info(f"✅ Изображение успешно загружено по URL: {image_url}")
            return image_url

    except Exception as e:
        # Логирование ошибки
        logger.error(f"❌ Ошибка при загрузке изображения в S3: {e}")

        # Уведомление пользователя
        if user_chat_id:
            try:
                await bot.send_message(
                    chat_id=user_chat_id,
                    text=f"⚠️ Ошибка при загрузке изображения в S3: {e}"
                )
                logger.info(f"Уведомление об ошибке отправлено пользователю в чат {user_chat_id}.")
            except Exception as notify_error:
                logger.error(f"❌ Ошибка при отправке уведомления пользователю: {notify_error}")

        return None






def extract_s3_key_from_url(image_url: str) -> str:
    """
    Извлекает ключ объекта S3 из полного URL.

    Args:
        image_url (str): Полный URL изображения в S3.

    Returns:
        str: Ключ объекта S3.
    """
    if not image_url:
        return ""

    parsed_url = urlparse(image_url)
    s3_key = parsed_url.path.lstrip('/')
    return s3_key





# # Пример использования
# if __name__ == "__main__":
#     # Генерация тестового изображения
#     test_image = Image.new('RGB', (100, 100), color='red')
#     task_id = 123
#
#     # Сохранение изображения в S3
#     url = save_image_to_storage(test_image, task_id)
#     if url:
#         logger.info(f"Изображение сохранено успешно: {url}")
#     else:
#         logger.error("Ошибка при сохранении изображения")