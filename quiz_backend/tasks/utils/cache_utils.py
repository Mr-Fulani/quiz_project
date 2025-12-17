"""
Утилиты для кэширования URL изображений и видео задач.
Использует Redis для кэширования сформированных URL (для производительности, не для экономии трафика).
"""
from django.core.cache import cache
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# TTL для кэша URL изображений (24 часа)
IMAGE_URL_CACHE_TTL = 60 * 60 * 24  # 24 часа
VIDEO_URL_CACHE_TTL = 60 * 60 * 24  # 24 часа


def get_cached_image_url(task_id: int) -> Optional[str]:
    """
    Получает URL изображения задачи из кэша.
    
    Args:
        task_id: ID задачи
        
    Returns:
        URL изображения или None если не найдено в кэше
    """
    cache_key = f'task_image_url:{task_id}'
    return cache.get(cache_key)


def set_cached_image_url(task_id: int, image_url: str) -> None:
    """
    Сохраняет URL изображения задачи в кэш.
    
    Args:
        task_id: ID задачи
        image_url: URL изображения
    """
    cache_key = f'task_image_url:{task_id}'
    cache.set(cache_key, image_url, IMAGE_URL_CACHE_TTL)
    logger.debug(f"URL изображения для задачи {task_id} сохранен в кэш")


def get_cached_video_url(task_id: int) -> Optional[str]:
    """
    Получает URL видео задачи из кэша.
    
    Args:
        task_id: ID задачи
        
    Returns:
        URL видео или None если не найдено в кэше
    """
    cache_key = f'task_video_url:{task_id}'
    return cache.get(cache_key)


def set_cached_video_url(task_id: int, video_url: str) -> None:
    """
    Сохраняет URL видео задачи в кэш.
    
    Args:
        task_id: ID задачи
        video_url: URL видео
    """
    cache_key = f'task_video_url:{task_id}'
    cache.set(cache_key, video_url, VIDEO_URL_CACHE_TTL)
    logger.debug(f"URL видео для задачи {task_id} сохранен в кэш")


def invalidate_task_urls_cache(task_id: int) -> None:
    """
    Инвалидирует кэш URL изображения и видео для задачи.
    
    Args:
        task_id: ID задачи
    """
    cache_key_image = f'task_image_url:{task_id}'
    cache_key_video = f'task_video_url:{task_id}'
    cache.delete(cache_key_image)
    cache.delete(cache_key_video)
    logger.debug(f"Кэш URL для задачи {task_id} инвалидирован")

