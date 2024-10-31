from typing import Optional

import aioboto3
import io
import logging
from PIL import Image
from config import S3_BUCKET_NAME, S3_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY



# Настройка логгера
logger = logging.getLogger(__name__)




async def upload_to_s3(image: Image, image_name: str) -> Optional[str]:
    """
    Асинхронная загрузка изображения в S3 и возврат URL.

    :param image: Объект изображения PIL.
    :param image_name: Имя изображения для сохранения в S3.
    :return: URL загруженного изображения или None при ошибке.
    """
    try:
        # Преобразуем изображение в байты
        image_bytes = io.BytesIO()
        image.save(image_bytes, format='PNG')
        image_bytes.seek(0)

        # Асинхронно загружаем изображение в S3
        session = aioboto3.Session()
        async with session.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=S3_REGION
        ) as s3:
            response = await s3.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=image_name,
                Body=image_bytes,
                ContentType='image/png',
                ACL='public-read'  # Обеспечивает публичный доступ к объекту
            )

        # Логируем успешный ответ от S3
        logger.info(f"S3 Response: {response}")

        # Проверяем, успешен ли запрос
        if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
            # Формируем URL загруженного изображения
            image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{image_name}"
            logger.info(f"Изображение успешно загружено в S3: {image_url}")
            return image_url
        else:
            logger.error(f"Ошибка загрузки изображения в S3: {response}")
            return None

    except Exception as e:
        logger.error(f"Ошибка при загрузке изображения в S3: {e}")
        return None






async def save_image_to_storage(image: Image, image_name: str) -> str:
    """
    Асинхронная функция для загрузки изображения в S3.
    :param image: Объект изображения PIL.
    :param image_name: Имя изображения для сохранения в S3.
    :return: URL загруженного изображения.
    """
    try:
        session = aioboto3.Session()  # Создание сессии
        async with session.client('s3',
                                  region_name=S3_REGION,
                                  aws_access_key_id=AWS_ACCESS_KEY_ID,
                                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY) as s3_client:
            # Преобразуем изображение в байты
            image_bytes = io.BytesIO()
            image.save(image_bytes, format='PNG')
            image_bytes.seek(0)

            # Попытка загрузки изображения с ACL (для бакетов, поддерживающих ACL)
            try:
                await s3_client.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=image_name,
                    Body=image_bytes.getvalue(),
                    ContentType='image/png',
                    ACL='public-read'
                )
            except s3_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'AccessControlListNotSupported':
                    logger.warning(f"Бакет {S3_BUCKET_NAME} не поддерживает ACL. Повторная загрузка без ACL.")
                    # Повторная загрузка без параметра ACL
                    await s3_client.put_object(
                        Bucket=S3_BUCKET_NAME,
                        Key=image_name,
                        Body=image_bytes.getvalue(),
                        ContentType='image/png'
                    )
                else:
                    raise e

            # Формируем URL для изображения
            image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{image_name}"
            logger.info(f"Изображение успешно загружено по URL: {image_url}")
            return image_url

    except Exception as e:
        logger.error(f"Ошибка при загрузке изображения в S3: {e}")
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