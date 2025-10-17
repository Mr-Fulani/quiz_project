"""
Сервис для работы с AWS S3.
Адаптирован из bot/services/s3_services.py для синхронного использования в Django.
"""
import io
import logging
from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError
from PIL import Image
from django.conf import settings

logger = logging.getLogger(__name__)


def extract_s3_key_from_url(url: str) -> Optional[str]:
    """
    Извлекает ключ S3 из URL изображения.
    
    Args:
        url: URL изображения в S3
        
    Returns:
        Ключ S3 или None при ошибке
        
    Examples:
        >>> extract_s3_key_from_url('https://bucket.s3.region.amazonaws.com/path/to/image.png')
        'path/to/image.png'
    """
    if not url:
        return None
        
    try:
        parsed = urlparse(url)
        # Убираем ведущий слэш из пути
        s3_key = parsed.path.lstrip('/')
        
        if not s3_key:
            logger.warning(f"Не удалось извлечь ключ S3 из URL: {url}")
            return None
            
        logger.debug(f"Извлечен ключ S3: {s3_key} из URL: {url}")
        return s3_key
        
    except Exception as e:
        logger.error(f"Ошибка при извлечении ключа S3 из URL {url}: {e}")
        return None


def upload_image_to_s3(image: Image.Image, image_name: str) -> Optional[str]:
    """
    Загружает изображение в S3 и возвращает публичный URL.
    
    Args:
        image: Объект изображения PIL
        image_name: Имя файла для сохранения в S3
        
    Returns:
        URL загруженного изображения или None при ошибке
    """
    if not isinstance(image, Image.Image):
        logger.error(f"Ожидался объект Image, получен тип {type(image)}")
        return None
        
    if not all([settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, 
                settings.AWS_STORAGE_BUCKET_NAME]):
        logger.error("AWS S3 настройки не сконфигурированы")
        return None
    
    try:
        # Преобразуем изображение в байты
        image_bytes = io.BytesIO()
        image.save(image_bytes, format='PNG')
        image_bytes.seek(0)
        
        # Создаем S3 клиент
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        try:
            # Попытка загрузить с ACL
            s3_client.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=image_name,
                Body=image_bytes,
                ContentType='image/png',
                ACL='public-read'
            )
        except ClientError as e:
            # Проверка на ошибку с ACL
            if e.response['Error']['Code'] == 'AccessControlListNotSupported':
                logger.warning(
                    f"Бакет {settings.AWS_STORAGE_BUCKET_NAME} не поддерживает ACL. "
                    f"Повторная загрузка без ACL."
                )
                # Перезагружаем изображение в байты
                image_bytes = io.BytesIO()
                image.save(image_bytes, format='PNG')
                image_bytes.seek(0)
                
                s3_client.put_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=image_name,
                    Body=image_bytes,
                    ContentType='image/png'
                )
            else:
                raise e
        
        # Формируем URL
        image_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{image_name}"
        logger.info(f"✅ Изображение успешно загружено в S3: {image_url}")
        
        return image_url
        
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке изображения в S3: {e}")
        return None


def delete_image_from_s3(image_url: str) -> bool:
    """
    Удаляет изображение из S3 по указанному URL.
    
    Args:
        image_url: URL изображения в S3
        
    Returns:
        True если удаление успешно, иначе False
    """
    if not image_url:
        return True
        
    if not all([settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, 
                settings.AWS_STORAGE_BUCKET_NAME]):
        logger.error("AWS S3 настройки не сконфигурированы")
        return False
    
    try:
        s3_key = extract_s3_key_from_url(image_url)
        if not s3_key:
            logger.warning("Не удалось извлечь ключ S3 из URL")
            return False
        
        # Создаем S3 клиент
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        # Удаляем объект
        s3_client.delete_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=s3_key
        )
        
        logger.info(f"✅ Изображение успешно удалено из S3: {s3_key}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении изображения из S3: {e}")
        return False

