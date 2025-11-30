"""
Единый сервис для публикации задач в социальные сети.
Поддерживает как прямую интеграцию через API, так и webhook.
"""
import json
import logging
import requests
from typing import Dict, List
from django.conf import settings
from django.utils import timezone

from webhooks.models import SocialMediaCredentials, Webhook
from ..models import Task, TaskTranslation, SocialMediaPost
from .platforms.pinterest_api import PinterestAPI
from .platforms.yandex_dzen_api import YandexDzenAPI
from .platforms.facebook_api import FacebookAPI

logger = logging.getLogger(__name__)

# Платформы с прямой интеграцией через API
API_PLATFORMS = ['pinterest', 'yandex_dzen', 'facebook']

# Платформы через webhook
WEBHOOK_PLATFORMS = ['instagram', 'tiktok', 'youtube_shorts']


def publish_to_social_media(task: Task, translation: TaskTranslation) -> Dict:
    """
    Публикует задачу во все активные социальные сети.
    
    Args:
        task: Объект задачи
        translation: Объект перевода задачи
        
    Returns:
        Dict: {'total': 6, 'success': 4, 'failed': 2, 'results': [...]}
    """
    results = []
    
    logger.info(f"🌐 Начинаем публикацию задачи {task.id} в социальные сети")
    
    # 1. Публикация через API (Pinterest, Дзен, Facebook)
    api_results = _publish_via_api(task, translation)
    results.extend(api_results)
    
    # 2. Публикация через webhook (Instagram, TikTok, YouTube)
    webhook_results = _publish_via_webhook(task, translation)
    results.extend(webhook_results)
    
    success_count = sum(1 for r in results if r.get('success'))
    failed_count = len(results) - success_count
    
    logger.info(f"✅ Публикация завершена: {success_count}/{len(results)} успешно")
    
    return {
        'total': len(results),
        'success': success_count,
        'failed': failed_count,
        'results': results
    }


def publish_to_platform(task: Task, translation: TaskTranslation, platform: str) -> Dict:
    """
    Публикует задачу в конкретную социальную сеть.
    
    Args:
        task: Объект задачи
        translation: Объект перевода задачи
        platform: Название платформы ('pinterest', 'facebook', 'yandex_dzen', 'instagram', 'tiktok', 'youtube_shorts')
        
    Returns:
        Dict: {'platform': 'pinterest', 'success': True/False, 'post_id': '...', 'error': '...'}
    """
    logger.info(f"🌐 Публикация задачи {task.id} в {platform}")
    
    # Проверяем наличие изображения
    if not task.image_url:
        error_msg = "Нет изображения"
        logger.warning(f"⚠️ Задача {task.id}: {error_msg}")
        return {
            'platform': platform,
            'success': False,
            'error': error_msg
        }
    
    # Публикация через API
    if platform in API_PLATFORMS:
        return _publish_single_platform_api(task, translation, platform)
    
    # Публикация через webhook
    elif platform in WEBHOOK_PLATFORMS:
        return _publish_single_platform_webhook(task, translation, platform)
    
    else:
        error_msg = f"Неизвестная платформа: {platform}"
        logger.error(f"❌ {error_msg}")
        return {
            'platform': platform,
            'success': False,
            'error': error_msg
        }


def _publish_single_platform_api(task: Task, translation: TaskTranslation, platform: str) -> Dict:
    """Публикация в конкретную платформу через API."""
    try:
        # Проверяем наличие credentials
        creds = SocialMediaCredentials.objects.filter(
            platform=platform,
            is_active=True
        ).first()
        
        if not creds:
            error_msg = f"Нет активных credentials для {platform}"
            logger.warning(f"⚠️ {error_msg}")
            return {
                'platform': platform,
                'success': False,
                'error': error_msg
            }
        
        # Получаем или создаем запись о публикации
        social_post, created = SocialMediaPost.objects.get_or_create(
            task=task,
            platform=platform,
            defaults={
                'method': 'api',
                'status': 'pending'
            }
        )
        
        # Если уже опубликована, пропускаем
        if not created and social_post.status == 'published':
            logger.info(f"ℹ️ Задача {task.id} уже опубликована в {platform}, пропускаем")
            return {
                'platform': platform,
                'success': True,
                'status': 'already_published',
                'post_id': social_post.post_id,
                'post_url': social_post.post_url
            }
        
        # Если в обработке, пропускаем
        if not created and social_post.status == 'processing':
            logger.info(f"ℹ️ Задача {task.id} уже обрабатывается для {platform}, пропускаем")
            return {
                'platform': platform,
                'success': False,
                'error': 'Уже обрабатывается'
            }
        
        # Сохраняем старый статус
        old_status = social_post.status if not created else None
        
        # Обновляем статус
        social_post.status = 'processing'
        social_post.method = 'api'
        
        if not created and old_status == 'failed':
            social_post.retry_count += 1
            logger.info(f"🔄 Повторная попытка публикации задачи {task.id} в {platform} (попытка #{social_post.retry_count})")
        
        social_post.save()
        
        # Публикуем в зависимости от платформы
        if platform == 'pinterest':
            result = _publish_to_pinterest(task, translation, creds, social_post)
        elif platform == 'yandex_dzen':
            result = _publish_to_yandex_dzen(task, translation, creds, social_post)
        elif platform == 'facebook':
            result = _publish_to_facebook(task, translation, creds, social_post)
        else:
            result = {'platform': platform, 'success': False, 'error': 'Unknown platform'}
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка публикации в {platform}: {e}", exc_info=True)
        # Обновляем статус на failed
        if 'social_post' in locals():
            social_post.status = 'failed'
            social_post.error_message = str(e)
            social_post.save()
        return {
            'platform': platform,
            'success': False,
            'error': str(e)
        }


def _publish_single_platform_webhook(task: Task, translation: TaskTranslation, platform: str) -> Dict:
    """Публикация в конкретную платформу через webhook."""
    try:
        # Ищем активные webhook для этой платформы
        webhooks = Webhook.objects.filter(
            is_active=True,
            webhook_type='social_media',
            target_platforms__contains=[platform]
        )
        
        if not webhooks.exists():
            error_msg = f"Нет активных webhook для {platform}"
            logger.warning(f"⚠️ {error_msg}")
            return {
                'platform': platform,
                'success': False,
                'error': error_msg
            }
        
        # Используем первый доступный webhook
        webhook = webhooks.first()
        
        # Получаем или создаем запись о публикации
        social_post, created = SocialMediaPost.objects.get_or_create(
            task=task,
            platform=platform,
            defaults={
                'method': 'webhook',
                'status': 'pending'
            }
        )
        
        # Если уже опубликована, пропускаем
        if not created and social_post.status == 'published':
            logger.info(f"ℹ️ Задача {task.id} уже опубликована в {platform}, пропускаем")
            return {
                'platform': platform,
                'success': True,
                'status': 'already_published',
                'post_id': social_post.post_id,
                'post_url': social_post.post_url
            }
        
        # Если в обработке, пропускаем
        if not created and social_post.status == 'processing':
            logger.info(f"ℹ️ Задача {task.id} уже обрабатывается для {platform}, пропускаем")
            return {
                'platform': platform,
                'success': False,
                'error': 'Уже обрабатывается'
            }
        
        # Сохраняем старый статус
        old_status = social_post.status if not created else None
        
        # Обновляем статус
        social_post.status = 'processing'
        social_post.method = 'webhook'
        
        if not created and old_status == 'failed':
            social_post.retry_count += 1
            logger.info(f"🔄 Повторная попытка публикации задачи {task.id} в {platform} через webhook (попытка #{social_post.retry_count})")
        
        social_post.save()
        
        # Подготавливаем payload
        payload = _prepare_webhook_payload(task, translation, platform)
        
        logger.info(f"📤 Отправка в webhook для {platform}: {webhook.url[:50]}...")
        
        response = requests.post(webhook.url, json=payload, timeout=30)
        
        if response.status_code in [200, 201, 202]:
            social_post.status = 'sent'  # Отправлено в webhook, ждем callback
            social_post.save()
            return {
                'platform': platform,
                'success': True,
                'status': 'sent_to_webhook'
            }
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            social_post.status = 'failed'
            social_post.error_message = error_msg
            social_post.save()
            return {
                'platform': platform,
                'success': False,
                'error': error_msg
            }
            
    except requests.exceptions.Timeout:
        error_msg = "Webhook: Превышено время ожидания запроса"
        logger.error(f"❌ {error_msg} для {platform}")
        if 'social_post' in locals():
            social_post.status = 'failed'
            social_post.error_message = error_msg
            social_post.save()
        return {
            'platform': platform,
            'success': False,
            'error': error_msg
        }
    except requests.exceptions.ConnectionError:
        error_msg = "Webhook: Ошибка соединения с сервером"
        logger.error(f"❌ {error_msg} для {platform}")
        if 'social_post' in locals():
            social_post.status = 'failed'
            social_post.error_message = error_msg
            social_post.save()
        return {
            'platform': platform,
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        logger.error(f"❌ Ошибка webhook для {platform}: {e}", exc_info=True)
        if 'social_post' in locals():
            social_post.status = 'failed'
            social_post.error_message = str(e)
            social_post.save()
        return {
            'platform': platform,
            'success': False,
            'error': str(e)
        }


def _publish_via_api(task: Task, translation: TaskTranslation) -> List[Dict]:
    """
    Публикация через прямое API.
    
    Returns:
        List[Dict]: Список результатов публикации
    """
    results = []
    
    for platform in API_PLATFORMS:
        try:
            # Проверяем наличие credentials
            creds = SocialMediaCredentials.objects.filter(
                platform=platform,
                is_active=True
            ).first()
            
            if not creds:
                logger.warning(f"⚠️ Нет credentials для {platform}, пропускаем")
                continue
            
            # Получаем или создаем запись о публикации (избегаем дубликатов)
            social_post, created = SocialMediaPost.objects.get_or_create(
                task=task,
                platform=platform,
                defaults={
                    'method': 'api',
                    'status': 'processing'
                }
            )
            
            # Если запись уже существует и успешно опубликована, пропускаем
            if not created and social_post.status == 'published':
                logger.info(f"ℹ️ Задача {task.id} уже успешно опубликована в {platform}, пропускаем")
                continue
            
            # Если запись в статусе processing, пропускаем (избегаем параллельных запросов)
            if not created and social_post.status == 'processing':
                logger.info(f"ℹ️ Задача {task.id} уже обрабатывается для {platform}, пропускаем")
                continue
            
            # Если запись failed или pending - разрешаем повторную попытку
            # Сохраняем старый статус для проверки
            old_status = social_post.status if not created else None
            
            # Обновляем статус на processing
            social_post.status = 'processing'
            social_post.method = 'api'
            
            # Увеличиваем счетчик попыток для failed записей
            if not created and old_status == 'failed':
                social_post.retry_count += 1
                logger.info(f"🔄 Повторная попытка публикации задачи {task.id} в {platform} (попытка #{social_post.retry_count})")
            
            social_post.save()
            
            # Публикуем в зависимости от платформы
            try:
                if platform == 'pinterest':
                    result = _publish_to_pinterest(task, translation, creds, social_post)
                elif platform == 'yandex_dzen':
                    result = _publish_to_yandex_dzen(task, translation, creds, social_post)
                elif platform == 'facebook':
                    result = _publish_to_facebook(task, translation, creds, social_post)
                else:
                    result = {'platform': platform, 'success': False, 'error': 'Unknown platform'}
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"❌ Ошибка публикации в {platform}: {e}", exc_info=True)
                social_post.status = 'failed'
                social_post.error_message = str(e)
                social_post.save()
                results.append({
                    'platform': platform,
                    'success': False,
                    'error': str(e)
                })
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка для {platform}: {e}", exc_info=True)
            results.append({
                'platform': platform,
                'success': False,
                'error': str(e)
            })
    
    return results


def _publish_via_webhook(task: Task, translation: TaskTranslation) -> List[Dict]:
    """
    Публикация через webhook (Make.com).
    
    Returns:
        List[Dict]: Список результатов публикации
    """
    results = []
    
    webhooks = Webhook.objects.filter(
        is_active=True,
        webhook_type='social_media'
    )
    
    if not webhooks.exists():
        logger.info("ℹ️ Нет активных webhook для социальных сетей")
        return results
    
    for webhook in webhooks:
        platforms = webhook.target_platforms or []
        
        for platform in platforms:
            if platform not in WEBHOOK_PLATFORMS:
                logger.warning(f"⚠️ Платформа {platform} не поддерживается через webhook")
                continue
            
            try:
                payload = _prepare_webhook_payload(task, translation, platform)
                
                # Получаем или создаем запись о публикации (избегаем дубликатов)
                social_post, created = SocialMediaPost.objects.get_or_create(
                    task=task,
                    platform=platform,
                    defaults={
                        'method': 'webhook',
                        'status': 'processing'
                    }
                )
                
                # Если запись уже существует и успешно опубликована, пропускаем
                if not created and social_post.status == 'published':
                    logger.info(f"ℹ️ Задача {task.id} уже успешно опубликована в {platform} через webhook, пропускаем")
                    continue
                
                # Если запись в статусе processing, пропускаем (избегаем параллельных запросов)
                if not created and social_post.status == 'processing':
                    logger.info(f"ℹ️ Задача {task.id} уже обрабатывается для {platform} через webhook, пропускаем")
                    continue
                
                # Если запись failed или pending - разрешаем повторную попытку
                # Сохраняем старый статус для проверки
                old_status = social_post.status if not created else None
                
                # Обновляем статус на processing
                social_post.status = 'processing'
                social_post.method = 'webhook'
                
                # Увеличиваем счетчик попыток для failed записей
                if not created and old_status == 'failed':
                    social_post.retry_count += 1
                    logger.info(f"🔄 Повторная попытка публикации задачи {task.id} в {platform} через webhook (попытка #{social_post.retry_count})")
                
                social_post.save()
                
                logger.info(f"📤 Отправка в webhook для {platform}: {webhook.url[:50]}...")
                
                response = requests.post(webhook.url, json=payload, timeout=30)
                
                if response.status_code in [200, 201, 202]:
                    social_post.status = 'published'
                    social_post.published_at = timezone.now()
                    social_post.save()
                    
                    logger.info(f"✅ Webhook успешно принят для {platform}")
                    results.append({'platform': platform, 'success': True, 'method': 'webhook'})
                else:
                    social_post.status = 'failed'
                    social_post.error_message = f"HTTP {response.status_code}: {response.text[:200]}"
                    social_post.save()
                    
                    logger.error(f"❌ Webhook ошибка для {platform}: {response.status_code}")
                    results.append({
                        'platform': platform,
                        'success': False,
                        'error': f"HTTP {response.status_code}"
                    })
                    
            except Exception as e:
                logger.error(f"❌ Ошибка webhook для {platform}: {e}")
                if 'social_post' in locals():
                    social_post.status = 'failed'
                    social_post.error_message = str(e)
                    social_post.save()
                results.append({'platform': platform, 'success': False, 'error': str(e)})
    
    return results


def _publish_to_pinterest(task, translation, creds, social_post) -> Dict:
    """Публикация в Pinterest."""
    api = PinterestAPI(creds.access_token)
    
    board_id = creds.extra_data.get('board_id')
    if not board_id:
        raise ValueError("board_id не указан в credentials.extra_data")
    
    # Формируем контент
    title = translation.question[:100]
    description = _format_pinterest_description(translation)
    link = task.external_link or f"{getattr(settings, 'SITE_URL', 'https://your-site.com')}/task/{task.id}"
    
    # Создаем пин
    pin_data = api.create_pin(
        board_id=board_id,
        image_url=task.image_url,
        title=title,
        description=description,
        link=link
    )
    
    # Обновляем запись
    social_post.status = 'published'
    social_post.post_id = pin_data.get('id')
    social_post.post_url = f"https://pinterest.com/pin/{pin_data.get('id')}"
    social_post.published_at = timezone.now()
    social_post.save()
    
    logger.info(f"✅ Pinterest: пин создан {social_post.post_url}")
    
    return {
        'platform': 'pinterest',
        'success': True,
        'post_id': pin_data.get('id'),
        'post_url': social_post.post_url
    }


def _publish_to_yandex_dzen(task, translation, creds, social_post) -> Dict:
    """Публикация в Яндекс Дзен."""
    api = YandexDzenAPI(creds.access_token)
    
    channel_id = creds.extra_data.get('channel_id')
    if not channel_id:
        raise ValueError("channel_id не указан в credentials.extra_data")
    
    # Формируем контент
    title = translation.question[:150]
    content = _format_dzen_content(translation)
    link = task.external_link or f"{getattr(settings, 'SITE_URL', 'https://your-site.com')}/task/{task.id}"
    
    # Создаем статью
    article_data = api.create_article(
        channel_id=channel_id,
        title=title,
        content=content,
        image_url=task.image_url,
        link=link
    )
    
    # Обновляем запись
    social_post.status = 'published'
    social_post.post_id = article_data.get('id')
    social_post.post_url = article_data.get('url') or f"https://dzen.ru/id/{channel_id}/post/{article_data.get('id')}"
    social_post.published_at = timezone.now()
    social_post.save()
    
    logger.info(f"✅ Яндекс Дзен: статья создана {social_post.post_url}")
    
    return {
        'platform': 'yandex_dzen',
        'success': True,
        'post_id': article_data.get('id'),
        'post_url': social_post.post_url
    }


def _publish_to_facebook(task, translation, creds, social_post) -> Dict:
    """Публикация в Facebook."""
    page_id = creds.extra_data.get('page_id')
    if not page_id:
        raise ValueError("page_id не указан в credentials.extra_data")
    
    api = FacebookAPI(creds.access_token, page_id)
    
    # Формируем контент
    message = _format_facebook_message(translation)
    link = task.external_link or f"{getattr(settings, 'SITE_URL', 'https://your-site.com')}/task/{task.id}"
    
    # Создаем пост
    post_data = api.create_photo_post(
        image_url=task.image_url,
        message=message,
        link=link
    )
    
    # Обновляем запись
    social_post.status = 'published'
    social_post.post_id = post_data.get('id')
    social_post.post_url = post_data.get('post_url') or f"https://facebook.com/{post_data.get('id')}"
    social_post.published_at = timezone.now()
    social_post.save()
    
    logger.info(f"✅ Facebook: пост создан {social_post.post_url}")
    
    return {
        'platform': 'facebook',
        'success': True,
        'post_id': post_data.get('id'),
        'post_url': social_post.post_url
    }


def _format_pinterest_description(translation: TaskTranslation) -> str:
    """Форматирует описание для Pinterest."""
    # Парсим ответы
    answers = translation.answers if isinstance(translation.answers, list) else json.loads(translation.answers)
    
    # Форматируем варианты ответов
    answer_lines = [f"• {ans}" for ans in answers[:4]]
    answer_text = "\n".join(answer_lines)
    
    description = f"{translation.question}\n\n{answer_text}\n\n💡 Правильный ответ: {translation.correct_answer}"
    
    # Добавляем хештеги
    description += "\n\n#programming #coding #quiz"
    
    return description[:500]


def _format_dzen_content(translation: TaskTranslation) -> str:
    """Форматирует контент для Яндекс Дзен."""
    answers = translation.answers if isinstance(translation.answers, list) else json.loads(translation.answers)
    
    answer_lines = [f"<li>{ans}</li>" for ans in answers[:4]]
    answers_html = "<ul>" + "".join(answer_lines) + "</ul>"
    
    content = f"""
    <p><strong>{translation.question}</strong></p>
    
    <p>Варианты ответов:</p>
    {answers_html}
    
    <p><strong>💡 Ответ:</strong> {translation.correct_answer}</p>
    
    <p><strong>Объяснение:</strong></p>
    <p>{translation.explanation or 'Проверьте свои знания!'}</p>
    """
    
    return content.strip()


def _format_facebook_message(translation: TaskTranslation) -> str:
    """Форматирует сообщение для Facebook."""
    answers = translation.answers if isinstance(translation.answers, list) else json.loads(translation.answers)
    
    answer_lines = [f"{i+1}. {ans}" for i, ans in enumerate(answers[:4])]
    answers_text = "\n".join(answer_lines)
    
    message = f"""🧠 Проверьте свои знания!

{translation.question}

{answers_text}

💡 Правильный ответ будет в комментариях!

#programming #coding #quiz #learntocode"""
    
    return message


def _prepare_webhook_payload(task: Task, translation: TaskTranslation, platform: str) -> Dict:
    """
    Подготавливает payload для отправки в webhook.
    
    Args:
        task: Объект задачи
        translation: Объект перевода
        platform: Название платформы (instagram, tiktok, youtube_shorts)
        
    Returns:
        Dict с данными для webhook
    """
    # Парсим ответы
    answers = translation.answers if isinstance(translation.answers, list) else json.loads(translation.answers)
    
    payload = {
        "task_id": task.id,
        "platform": platform,
        "content": {
            "image_url": task.image_url,
            "title": translation.question[:100],
            "description": f"{translation.question}\n\nВарианты: {', '.join(answers[:4])}",
            "explanation": translation.explanation or "",
            "link": task.external_link or f"{getattr(settings, 'SITE_URL', 'https://your-site.com')}/task/{task.id}",
            "hashtags": ["#programming", "#coding", "#quiz"],
            "topic": task.topic.name if task.topic else "programming",
            "difficulty": task.difficulty
        },
        "metadata": {
            "language": translation.language,
            "translation_group_id": str(task.translation_group_id),
            "publish_date": timezone.now().isoformat()
        }
    }
    
    return payload

