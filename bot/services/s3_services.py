# bot/services/s3_services.py

from typing import Optional
from urllib.parse import urlparse

import aioboto3
import io
import logging
from PIL import Image
from botocore.exceptions import ClientError

import bot
from bot.config import (
    S3_BUCKET_NAME, S3_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
    USE_R2_STORAGE, R2_ENDPOINT_URL, R2_PUBLIC_DOMAIN, R2_ENVIRONMENT_PREFIX
)



# Настройка логгера
logger = logging.getLogger(__name__)





async def save_image_to_storage(image: Image.Image, image_name: str, user_chat_id: int) -> Optional[str]:
    """
    Асинхронная загрузка изображения в S3/R2 и возврат URL.
    Автоматически определяет хранилище на основе настроек USE_R2_STORAGE.
    В случае ошибки отправляется сообщение пользователю.

    Args:
        image (Image.Image): Объект изображения PIL.
        image_name (str): Имя изображения для сохранения (может включать путь).
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

        storage_name = 'R2' if USE_R2_STORAGE else 'S3'
        
        # Преобразуем изображение в байты с оптимизацией для R2 (экономия хранения)
        image_bytes = io.BytesIO()
        image.save(image_bytes, format='PNG', optimize=True)
        image_bytes.seek(0)

        # Формируем путь с учетом окружения (prod/ или dev/) и типа файла
        if USE_R2_STORAGE and R2_ENVIRONMENT_PREFIX:
            # Для R2 используем структуру: {env}/images/
            if not image_name.startswith(f'{R2_ENVIRONMENT_PREFIX}/') and not image_name.startswith('images/') and not image_name.startswith('videos/'):
                image_key = f'{R2_ENVIRONMENT_PREFIX}/images/{image_name}'
            elif image_name.startswith('images/') or image_name.startswith('videos/'):
                # Если уже есть images/ или videos/, добавляем только env_prefix
                image_key = f'{R2_ENVIRONMENT_PREFIX}/{image_name}'
            else:
                image_key = image_name
        else:
            # Для S3 используем простую структуру images/
            if not image_name.startswith('images/') and not image_name.startswith('videos/'):
                image_key = f'images/{image_name}'
            else:
                image_key = image_name

        # Настройки клиента
        client_kwargs = {
            'service_name': 's3',
            'aws_access_key_id': AWS_ACCESS_KEY_ID,
            'aws_secret_access_key': AWS_SECRET_ACCESS_KEY,
        }
        
        # Для R2 добавляем endpoint URL
        if USE_R2_STORAGE and R2_ENDPOINT_URL:
            client_kwargs['endpoint_url'] = R2_ENDPOINT_URL
        # Для S3 добавляем region
        elif not USE_R2_STORAGE:
            client_kwargs['region_name'] = S3_REGION

        # Асинхронная загрузка в S3/R2
        session = aioboto3.Session()
        async with session.client(**client_kwargs) as s3:
            try:
                # Попытка загрузить с ACL (R2 может не поддерживать)
                await s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=image_key,
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
                        Key=image_key,
                        Body=image_bytes,
                        ContentType='image/png'
                    )
                else:
                    raise e

            # Формируем URL для изображения
            if USE_R2_STORAGE and R2_PUBLIC_DOMAIN:
                image_url = f"https://{R2_PUBLIC_DOMAIN}/{image_key}"
            elif USE_R2_STORAGE and R2_ENDPOINT_URL:
                # Fallback на endpoint если кастомный домен не настроен
                image_url = f"https://{S3_BUCKET_NAME}.r2.cloudflarestorage.com/{image_key}"
            else:
                # S3 URL
                image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{image_key}"
            
            logger.info(f"✅ Изображение успешно загружено в {storage_name} по URL: {image_url}")
            return image_url

    except Exception as e:
        # Логирование ошибки
        storage_name = 'R2' if USE_R2_STORAGE else 'S3'
        logger.error(f"❌ Ошибка при загрузке изображения в {storage_name}: {e}")

        # Уведомление пользователя
        if user_chat_id:
            try:
                await bot.send_message(
                    chat_id=user_chat_id,
                    text=f"⚠️ Ошибка при загрузке изображения в {storage_name}: {e}"
                )
                logger.info(f"Уведомление об ошибке отправлено пользователю в чат {user_chat_id}.")
            except Exception as notify_error:
                logger.error(f"❌ Ошибка при отправке уведомления пользователю: {notify_error}")

        return None






def extract_s3_key_from_url(image_url: str) -> str:
    """
    Извлекает ключ объекта S3/R2 из полного URL.
    Поддерживает как S3, так и R2 URL форматы.

    Args:
        image_url (str): Полный URL изображения или видео в S3/R2.

    Returns:
        str: Ключ объекта S3/R2.
    """
    if not image_url:
        return ""

    parsed_url = urlparse(image_url)
    s3_key = parsed_url.path.lstrip('/')
    return s3_key


async def save_video_to_storage(video_bytes: bytes, video_name: str, user_chat_id: int) -> Optional[str]:
    """
    Асинхронная загрузка видео в S3/R2 и возврат URL.
    Подготовка к будущей генерации видео.
    
    Args:
        video_bytes (bytes): Байты видео файла.
        video_name (str): Имя видео для сохранения (может включать путь).
        user_chat_id (int): ID чата пользователя для уведомления.

    Returns:
        Optional[str]: URL загруженного видео или None при ошибке.
    """
    try:
        storage_name = 'R2' if USE_R2_STORAGE else 'S3'
        
        # Формируем путь с учетом окружения (prod/ или dev/) и типа файла
        if USE_R2_STORAGE and R2_ENVIRONMENT_PREFIX:
            # Для R2 используем структуру: {env}/videos/
            if not video_name.startswith(f'{R2_ENVIRONMENT_PREFIX}/') and not video_name.startswith('videos/') and not video_name.startswith('images/'):
                video_key = f'{R2_ENVIRONMENT_PREFIX}/videos/{video_name}'
            elif video_name.startswith('videos/') or video_name.startswith('images/'):
                # Если уже есть videos/ или images/, добавляем только env_prefix
                video_key = f'{R2_ENVIRONMENT_PREFIX}/{video_name}'
            else:
                video_key = video_name
        else:
            # Для S3 используем простую структуру videos/
            if not video_name.startswith('videos/') and not video_name.startswith('images/'):
                video_key = f'videos/{video_name}'
            else:
                video_key = video_name

        # Определяем ContentType по расширению
        if video_name.endswith('.mp4'):
            content_type = 'video/mp4'
        elif video_name.endswith('.webm'):
            content_type = 'video/webm'
        else:
            content_type = 'video/mp4'  # По умолчанию

        # Настройки клиента
        client_kwargs = {
            'service_name': 's3',
            'aws_access_key_id': AWS_ACCESS_KEY_ID,
            'aws_secret_access_key': AWS_SECRET_ACCESS_KEY,
        }
        
        # Для R2 добавляем endpoint URL
        if USE_R2_STORAGE and R2_ENDPOINT_URL:
            client_kwargs['endpoint_url'] = R2_ENDPOINT_URL
        # Для S3 добавляем region
        elif not USE_R2_STORAGE:
            client_kwargs['region_name'] = S3_REGION

        # Асинхронная загрузка в S3/R2
        session = aioboto3.Session()
        async with session.client(**client_kwargs) as s3:
            try:
                # Попытка загрузить с ACL (R2 может не поддерживать)
                await s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=video_key,
                    Body=video_bytes,
                    ContentType=content_type,
                    ACL='public-read'
                )
            except ClientError as e:
                # Проверка на ошибку с ACL
                if e.response['Error']['Code'] == 'AccessControlListNotSupported':
                    logger.warning(f"Бакет {S3_BUCKET_NAME} не поддерживает ACL. Повторная загрузка без ACL.")
                    await s3.put_object(
                        Bucket=S3_BUCKET_NAME,
                        Key=video_key,
                        Body=video_bytes,
                        ContentType=content_type
                    )
                else:
                    raise e

            # Формируем URL для видео
            if USE_R2_STORAGE and R2_PUBLIC_DOMAIN:
                video_url = f"https://{R2_PUBLIC_DOMAIN}/{video_key}"
            elif USE_R2_STORAGE and R2_ENDPOINT_URL:
                # Fallback на endpoint если кастомный домен не настроен
                video_url = f"https://{S3_BUCKET_NAME}.r2.cloudflarestorage.com/{video_key}"
            else:
                # S3 URL
                video_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{video_key}"
            
            logger.info(f"✅ Видео успешно загружено в {storage_name} по URL: {video_url}")
            return video_url

    except Exception as e:
        # Логирование ошибки
        storage_name = 'R2' if USE_R2_STORAGE else 'S3'
        logger.error(f"❌ Ошибка при загрузке видео в {storage_name}: {e}")

        # Уведомление пользователя
        if user_chat_id:
            try:
                await bot.send_message(
                    chat_id=user_chat_id,
                    text=f"⚠️ Ошибка при загрузке видео в {storage_name}: {e}"
                )
                logger.info(f"Уведомление об ошибке отправлено пользователю в чат {user_chat_id}.")
            except Exception as notify_error:
                logger.error(f"❌ Ошибка при отправке уведомления пользователю: {notify_error}")

        return None





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