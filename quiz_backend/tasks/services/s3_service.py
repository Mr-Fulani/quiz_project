"""
Сервис для работы с AWS S3 и Cloudflare R2.
Адаптирован из bot/services/s3_services.py для синхронного использования в Django.
Поддерживает переключение между S3 и R2 через настройки.
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
    Извлекает ключ S3/R2 из URL изображения.
    Поддерживает как S3, так и R2 URL форматы.
    
    Args:
        url: URL изображения в S3 или R2
        
    Returns:
        Ключ S3/R2 или None при ошибке
        
    Examples:
        >>> extract_s3_key_from_url('https://bucket.s3.region.amazonaws.com/path/to/image.png')
        'path/to/image.png'
        >>> extract_s3_key_from_url('https://r2-domain.com/images/task.png')
        'images/task.png'
    """
    if not url:
        return None
        
    try:
        parsed = urlparse(url)
        # Убираем ведущий слэш из пути
        s3_key = parsed.path.lstrip('/')
        
        # Если путь начинается с images/ или videos/, убираем префикс для совместимости
        # или оставляем как есть в зависимости от структуры
        if not s3_key:
            logger.warning(f"Не удалось извлечь ключ из URL: {url}")
            return None
            
        logger.debug(f"Извлечен ключ: {s3_key} из URL: {url}")
        return s3_key
        
    except Exception as e:
        logger.error(f"Ошибка при извлечении ключа из URL {url}: {e}")
        return None


def upload_image_to_s3(image: Image.Image, image_name: str) -> Optional[str]:
    """
    Загружает изображение в S3 или R2 и возвращает публичный URL.
    Автоматически определяет хранилище на основе настроек USE_R2_STORAGE.
    
    Args:
        image: Объект изображения PIL
        image_name: Имя файла для сохранения (может включать путь, например 'images/task.png')
        
    Returns:
        URL загруженного изображения или None при ошибке
    """
    if not isinstance(image, Image.Image):
        logger.error(f"Ожидался объект Image, получен тип {type(image)}")
        return None
    
    # Определяем используемое хранилище
    use_r2 = getattr(settings, 'USE_R2_STORAGE', False)
    storage_name = 'R2' if use_r2 else 'S3'
        
    # Проверяем наличие всех необходимых настроек
    missing_settings = []
    if not settings.AWS_ACCESS_KEY_ID:
        missing_settings.append('AWS_ACCESS_KEY_ID' if not use_r2 else 'R2_ACCESS_KEY_ID')
    if not settings.AWS_SECRET_ACCESS_KEY:
        missing_settings.append('AWS_SECRET_ACCESS_KEY' if not use_r2 else 'R2_SECRET_ACCESS_KEY')
    if not settings.AWS_STORAGE_BUCKET_NAME:
        missing_settings.append('AWS_STORAGE_BUCKET_NAME' if not use_r2 else 'R2_BUCKET_NAME')
    
    if missing_settings:
        error_msg = f"❌ {storage_name} настройки не сконфигурированы. Отсутствуют: {', '.join(missing_settings)}"
        logger.error(error_msg)
        return None
    
    try:
        # Преобразуем изображение в байты с оптимизацией для R2 (экономия хранения)
        image_bytes = io.BytesIO()
        # Используем оптимизацию PNG для уменьшения размера файла
        image.save(image_bytes, format='PNG', optimize=True)
        image_bytes.seek(0)
        
        # Формируем путь с учетом окружения (prod/ или dev/) и типа файла
        use_r2 = getattr(settings, 'USE_R2_STORAGE', False)
        if use_r2:
            # Для R2 используем структуру: {env}/images/ или {env}/videos/
            env_prefix = getattr(settings, 'R2_ENVIRONMENT_PREFIX', 'prod')
            if not image_name.startswith(f'{env_prefix}/') and not image_name.startswith('images/') and not image_name.startswith('videos/'):
                image_key = f'{env_prefix}/images/{image_name}'
            elif image_name.startswith('images/') or image_name.startswith('videos/'):
                # Если уже есть images/ или videos/, добавляем только env_prefix
                image_key = f'{env_prefix}/{image_name}'
            else:
                image_key = image_name
        else:
            # Для S3 используем простую структуру images/
            if not image_name.startswith('images/') and not image_name.startswith('videos/'):
                image_key = f'images/{image_name}'
            else:
                image_key = image_name
        
        # Создаем клиент S3/R2
        client_kwargs = {
            'service_name': 's3',
            'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
            'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY,
        }
        
        # Для R2 добавляем endpoint URL
        if use_r2 and hasattr(settings, 'AWS_S3_ENDPOINT_URL') and settings.AWS_S3_ENDPOINT_URL:
            client_kwargs['endpoint_url'] = settings.AWS_S3_ENDPOINT_URL
        # Для S3 добавляем region
        elif not use_r2:
            client_kwargs['region_name'] = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        
        s3_client = boto3.client(**client_kwargs)
        
        try:
            # Попытка загрузить с ACL (R2 может не поддерживать)
            s3_client.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=image_key,
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
                image.save(image_bytes, format='PNG', optimize=True)
                image_bytes.seek(0)
                
                s3_client.put_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=image_key,
                    Body=image_bytes,
                    ContentType='image/png'
                )
            else:
                raise e
        
        # Конструируем и возвращаем полный URL
        domain = getattr(settings, 'AWS_PUBLIC_MEDIA_DOMAIN', None) or getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', None)
        if not domain:
            logger.error(f"❌ Публичный домен не настроен для {storage_name}")
            return None
        
        full_url = f"https://{domain}/{image_key}"
        logger.info(f"✅ Изображение загружено в {storage_name}. URL: {full_url}")
        return full_url
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        storage_name = 'R2' if getattr(settings, 'USE_R2_STORAGE', False) else 'S3'
        logger.error(
            f"❌ Ошибка при загрузке изображения в {storage_name}: {error_code} - {error_message}. "
            f"Бакет: {settings.AWS_STORAGE_BUCKET_NAME}, "
            f"Ключ: {image_key if 'image_key' in locals() else image_name}"
        )
        return None
    except Exception as e:
        storage_name = 'R2' if getattr(settings, 'USE_R2_STORAGE', False) else 'S3'
        logger.error(
            f"❌ Неожиданная ошибка при загрузке изображения в {storage_name}: {type(e).__name__}: {e}. "
            f"Бакет: {settings.AWS_STORAGE_BUCKET_NAME}, "
            f"Ключ: {image_key if 'image_key' in locals() else image_name}",
            exc_info=True
        )
        return None


def delete_image_from_s3(image_url: str) -> bool:
    """
    Удаляет изображение или видео из S3/R2 по указанному URL.
    Поддерживает как изображения, так и видео файлы.
    
    Args:
        image_url: URL изображения или видео в S3/R2
        
    Returns:
        True если удаление успешно, иначе False
    """
    if not image_url:
        return True
    
    use_r2 = getattr(settings, 'USE_R2_STORAGE', False)
    storage_name = 'R2' if use_r2 else 'S3'
        
    if not all([settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, 
                settings.AWS_STORAGE_BUCKET_NAME]):
        logger.error(f"{storage_name} настройки не сконфигурированы")
        return False
    
    try:
        s3_key = extract_s3_key_from_url(image_url)
        if not s3_key:
            logger.warning("Не удалось извлечь ключ из URL")
            return False
        
        # Создаем клиент S3/R2
        client_kwargs = {
            'service_name': 's3',
            'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
            'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY,
        }
        
        # Для R2 добавляем endpoint URL
        if use_r2 and hasattr(settings, 'AWS_S3_ENDPOINT_URL') and settings.AWS_S3_ENDPOINT_URL:
            client_kwargs['endpoint_url'] = settings.AWS_S3_ENDPOINT_URL
        # Для S3 добавляем region
        elif not use_r2:
            client_kwargs['region_name'] = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        
        s3_client = boto3.client(**client_kwargs)
        
        # Удаляем объект
        s3_client.delete_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=s3_key
        )
        
        logger.info(f"✅ Файл успешно удален из {storage_name}: {s3_key}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении файла из {storage_name}: {e}")
        return False


def upload_video_to_r2(video_bytes: bytes, video_name: str) -> Optional[str]:
    """
    Загружает видео в S3/R2 и возвращает публичный URL.
    Подготовка к будущей генерации видео.
    
    Args:
        video_bytes: Байты видео файла
        video_name: Имя видео для сохранения (может включать путь)
        
    Returns:
        URL загруженного видео или None при ошибке
    """
    use_r2 = getattr(settings, 'USE_R2_STORAGE', False)
    storage_name = 'R2' if use_r2 else 'S3'
    
    # Проверяем наличие всех необходимых настроек
    missing_settings = []
    if not settings.AWS_ACCESS_KEY_ID:
        missing_settings.append('AWS_ACCESS_KEY_ID' if not use_r2 else 'R2_ACCESS_KEY_ID')
    if not settings.AWS_SECRET_ACCESS_KEY:
        missing_settings.append('AWS_SECRET_ACCESS_KEY' if not use_r2 else 'R2_SECRET_ACCESS_KEY')
    if not settings.AWS_STORAGE_BUCKET_NAME:
        missing_settings.append('AWS_STORAGE_BUCKET_NAME' if not use_r2 else 'R2_BUCKET_NAME')
    
    if missing_settings:
        error_msg = f"❌ {storage_name} настройки не сконфигурированы. Отсутствуют: {', '.join(missing_settings)}"
        logger.error(error_msg)
        return None
    
    try:
        # Формируем путь с учетом окружения (prod/ или dev/) и типа файла
        use_r2 = getattr(settings, 'USE_R2_STORAGE', False)
        if use_r2:
            # Для R2 используем структуру: {env}/videos/
            env_prefix = getattr(settings, 'R2_ENVIRONMENT_PREFIX', 'prod')
            if not video_name.startswith(f'{env_prefix}/') and not video_name.startswith('videos/') and not video_name.startswith('images/'):
                video_key = f'{env_prefix}/videos/{video_name}'
            elif video_name.startswith('videos/') or video_name.startswith('images/'):
                # Если уже есть videos/ или images/, добавляем только env_prefix
                video_key = f'{env_prefix}/{video_name}'
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
        
        # Создаем клиент S3/R2
        client_kwargs = {
            'service_name': 's3',
            'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
            'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY,
        }
        
        # Для R2 добавляем endpoint URL
        if use_r2 and hasattr(settings, 'AWS_S3_ENDPOINT_URL') and settings.AWS_S3_ENDPOINT_URL:
            client_kwargs['endpoint_url'] = settings.AWS_S3_ENDPOINT_URL
        # Для S3 добавляем region
        elif not use_r2:
            client_kwargs['region_name'] = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        
        s3_client = boto3.client(**client_kwargs)
        
        try:
            # Попытка загрузить с ACL (R2 может не поддерживать)
            s3_client.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=video_key,
                Body=video_bytes,
                ContentType=content_type,
                ACL='public-read'
            )
        except ClientError as e:
            # Проверка на ошибку с ACL
            if e.response['Error']['Code'] == 'AccessControlListNotSupported':
                logger.warning(
                    f"Бакет {settings.AWS_STORAGE_BUCKET_NAME} не поддерживает ACL. "
                    f"Повторная загрузка без ACL."
                )
                s3_client.put_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=video_key,
                    Body=video_bytes,
                    ContentType=content_type
                )
            else:
                raise e
        
        # Конструируем и возвращаем полный URL
        domain = getattr(settings, 'AWS_PUBLIC_MEDIA_DOMAIN', None) or getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', None)
        if not domain:
            logger.error(f"❌ Публичный домен не настроен для {storage_name}")
            return None
        
        full_url = f"https://{domain}/{video_key}"
        logger.info(f"✅ Видео загружено в {storage_name}. URL: {full_url}")
        return full_url
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error(
            f"❌ Ошибка при загрузке видео в {storage_name}: {error_code} - {error_message}. "
            f"Бакет: {settings.AWS_STORAGE_BUCKET_NAME}, "
            f"Ключ: {video_key if 'video_key' in locals() else video_name}"
        )
        return None
    except Exception as e:
        logger.error(
            f"❌ Неожиданная ошибка при загрузке видео в {storage_name}: {type(e).__name__}: {e}. "
            f"Бакет: {settings.AWS_STORAGE_BUCKET_NAME}, "
            f"Ключ: {video_key if 'video_key' in locals() else video_name}",
            exc_info=True
        )
        return None

