"""
Единый сервис для публикации задач в социальные сети.
Поддерживает как прямую интеграцию через API, так и webhook.
"""
import json
import logging
import requests
from typing import Dict, List, Optional
from django.conf import settings
from django.utils import timezone

from tenants.scoping import for_tenant_or_shared
from webhooks.models import SocialMediaCredentials, Webhook
from ..models import Task, TaskTranslation, SocialMediaPost


def _active_credentials(platform: str, tenant) -> Optional[SocialMediaCredentials]:
    """Активные credentials платформы: сначала тенанта задачи, затем общие (без тенанта)."""
    queryset = SocialMediaCredentials.objects.filter(platform=platform, is_active=True)
    if tenant is not None:
        own = queryset.filter(tenant=tenant).first()
        if own:
            return own
    return queryset.filter(tenant__isnull=True).first()
from .platforms.pinterest_api import PinterestAPI
from .platforms.facebook_api import FacebookAPI
# Яндекс Дзен API недоступен, используется только webhook
# from .platforms.yandex_dzen_api import YandexDzenAPI

logger = logging.getLogger(__name__)

# Платформы с прямой интеграцией через API
API_PLATFORMS = ['pinterest', 'facebook']

# Платформы через webhook
WEBHOOK_PLATFORMS = ['yandex_dzen', 'instagram', 'tiktok', 'youtube_shorts']


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
        # Проверяем наличие credentials (только тенанта задачи или общие)
        creds = _active_credentials(platform, task.tenant)

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
        elif platform == 'facebook':
            result = _publish_to_facebook(task, translation, creds, social_post)
        else:
            result = {'platform': platform, 'success': False, 'error': 'Unknown platform or platform uses webhook'}
        
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
        # Ищем активные webhook для этой платформы (только тенанта задачи или общие)
        webhooks = for_tenant_or_shared(Webhook.objects.filter(
            is_active=True,
            webhook_type='social_media',
            target_platforms__contains=[platform]
        ), task.tenant)
        
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
            # Проверяем наличие credentials (только тенанта задачи или общие)
            creds = _active_credentials(platform, task.tenant)

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
    
    webhooks = for_tenant_or_shared(Webhook.objects.filter(
        is_active=True,
        webhook_type='social_media'
    ), task.tenant)

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
    # Проверяем, что токен не истек
    from django.utils import timezone
    if creds.token_expires_at and creds.token_expires_at < timezone.now():
        raise Exception(
            f"Pinterest токен истек (истек: {creds.token_expires_at}). "
            f"Получите новый токен через OAuth: /auth/pinterest/authorize/"
        )
    
    # Проверяем наличие токена
    if not creds.access_token:
        raise Exception(
            "Pinterest access token не установлен. "
            "Получите токен через OAuth: /auth/pinterest/authorize/"
        )
    
    api = PinterestAPI(creds.access_token)
    
    # Получаем название темы
    topic_name = task.topic.name if task.topic else "code"
    
    # Выбираем доску динамически по названию темы
    board_id = _get_pinterest_board_by_topic(api, topic_name, creds)
    if not board_id:
        raise ValueError(f"Не найдена доска для темы '{topic_name}' и доска по умолчанию 'code'")
    
    # Формируем заголовок: "Что вернет этот код {название темы}?"
    title = f"Что вернет этот код {topic_name}?"
    if len(title) > 100:
        title = title[:97] + "..."
    
    # Описание всегда "Выбери правильный ответ"
    description = "Выбери правильный ответ"
    
    # Добавляем варианты ответов, каждый с новой строки
    try:
        # Парсим answers (может быть строкой JSON или списком)
        if isinstance(translation.answers, str):
            answers = json.loads(translation.answers)
        else:
            answers = translation.answers
        
        if answers and isinstance(answers, list) and len(answers) > 0:
            answers_text = "\n\n"  # Добавляем отступ перед вариантами
            answer_lines = [f"• {ans}" for ans in answers]
            answers_text += "\n".join(answer_lines)
            
            # Проверяем, поместится ли description + варианты ответов в 500 символов
            if len(description) + len(answers_text) <= 500:
                description += answers_text
            else:
                # Если не помещается, обрезаем description, чтобы поместились варианты
                max_desc_length = 500 - len(answers_text)
                if max_desc_length > 50:  # Минимум 50 символов для description
                    description = description[:max_desc_length] + answers_text
                else:
                    # Если варианты ответов слишком длинные, обрезаем их
                    description += "\n\n"
                    remaining = 500 - len(description)
                    for ans in answers:
                        answer_line = f"• {ans}\n"
                        if len(description) + len(answer_line) <= 500:
                            description += answer_line
                        else:
                            break
                    description = description.rstrip()  # Убираем последний \n
    except (json.JSONDecodeError, TypeError, AttributeError) as e:
        logger.warning(f"Ошибка парсинга answers для задачи {task.id}: {e}")
    
    # Финальная проверка длины (на всякий случай)
    if len(description) > 500:
        description = description[:500]
    elif not description:
        description = ""
    
    # Ссылка всегда на mini.quiz-code.com
    link = "https://mini.quiz-code.com"
    
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


# Яндекс Дзен API недоступен, используется только webhook
# def _publish_to_yandex_dzen(task, translation, creds, social_post) -> Dict:
#     """Публикация в Яндекс Дзен через API (недоступно)."""
#     api = YandexDzenAPI(creds.access_token)
#     
#     channel_id = creds.extra_data.get('channel_id')
#     if not channel_id:
#         raise ValueError("channel_id не указан в credentials.extra_data")
#     
#     # Формируем контент
#     title = translation.question[:150]
#     content = _format_dzen_content(translation)
#     link = task.external_link or f"{getattr(settings, 'SITE_URL', 'https://your-site.com')}/task/{task.id}"
#     
#     # Создаем статью
#     article_data = api.create_article(
#         channel_id=channel_id,
#         title=title,
#         content=content,
#         image_url=task.image_url,
#         link=link
#     )
#     
#     # Обновляем запись
#     social_post.status = 'published'
#     social_post.post_id = article_data.get('id')
#     social_post.post_url = article_data.get('url') or f"https://dzen.ru/id/{channel_id}/post/{article_data.get('id')}"
#     social_post.published_at = timezone.now()
#     social_post.save()
#     
#     logger.info(f"✅ Яндекс Дзен: статья создана {social_post.post_url}")
#     
#     return {
#         'platform': 'yandex_dzen',
#         'success': True,
#         'post_id': article_data.get('id'),
#         'post_url': social_post.post_url
#     }


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


def _get_pinterest_board_by_topic(api: PinterestAPI, topic_name: str, creds) -> Optional[str]:
    """
    Получает board_id для доски по названию темы.
    Ищет доску с названием, совпадающим с названием темы.
    Если не найдена, использует доску "code" по умолчанию.
    
    Args:
        api: Экземпляр PinterestAPI
        topic_name: Название темы (например, "Python", "Golang")
        creds: SocialMediaCredentials объект
        
    Returns:
        board_id (str) или None, если доска не найдена
    """
    from django.utils import timezone
    from datetime import timedelta, datetime
    
    # Инициализируем extra_data, если его нет
    if not creds.extra_data:
        creds.extra_data = {}
    
    # Проверяем кэш досок
    boards_cache = creds.extra_data.get('boards_cache')
    boards_cache_time = creds.extra_data.get('boards_cache_time')
    
    # Проверяем, нужно ли обновить кэш:
    # 1. Кэш пустой или отсутствует
    # 2. Кэш старше 1 часа
    # 3. Кэш не является словарем
    should_refresh = False
    
    if not boards_cache or not isinstance(boards_cache, dict) or len(boards_cache) == 0:
        logger.info("Кэш досок пустой или отсутствует, обновляем...")
        should_refresh = True
    elif boards_cache_time:
        # Парсим время из ISO формата
        try:
            if isinstance(boards_cache_time, str):
                cache_time = datetime.fromisoformat(boards_cache_time.replace('Z', '+00:00'))
                if cache_time.tzinfo is None:
                    cache_time = timezone.make_aware(cache_time)
            else:
                cache_time = boards_cache_time
            
            if timezone.now() - cache_time > timedelta(hours=1):
                logger.info("Кэш досок устарел (старше 1 часа), обновляем...")
                should_refresh = True
        except (ValueError, TypeError) as e:
            logger.warning(f"Ошибка парсинга времени кэша: {e}, обновляем кэш...")
            should_refresh = True
    
    # Получаем список досок, если нужно обновить
    if should_refresh:
        logger.info("Получение списка досок Pinterest...")
        boards_data = api.get_boards()
        if boards_data:
            items = boards_data.get('items', [])
            if items:
                boards_cache = {}
                for board in items:
                    board_name = board.get('name')
                    board_id = board.get('id')
                    if board_name and board_id:
                        boards_cache[board_name] = str(board_id)
                
                logger.info(f"Получено досок: {len(boards_cache)}")
                if boards_cache:
                    # Сохраняем в кэш
                    creds.extra_data['boards_cache'] = boards_cache
                    creds.extra_data['boards_cache_time'] = timezone.now().isoformat()
                    creds.save(update_fields=['extra_data'])
                    logger.info(f"✅ Кэш досок обновлен. Доски: {list(boards_cache.keys())}")
                else:
                    logger.warning("⚠️ Не удалось извлечь доски из ответа API (нет name или id)")
            else:
                logger.warning(f"⚠️ Список досок пустой в ответе API. Полный ответ: {boards_data}")
        else:
            logger.error("❌ Не удалось получить список досок от Pinterest API")
    
    if not boards_cache or len(boards_cache) == 0:
        logger.warning("Не удалось получить список досок Pinterest через API")
        # Проверяем, есть ли сохраненный кэш досок (вручную указанный или через скрипт)
        # Сначала проверяем boards_cache (может быть сохранен через скрипт)
        saved_boards_cache = creds.extra_data.get('boards_cache')
        if saved_boards_cache and isinstance(saved_boards_cache, dict) and len(saved_boards_cache) > 0:
            logger.info(f"Используется сохраненный кэш досок: {list(saved_boards_cache.keys())}")
            boards_cache = saved_boards_cache
        else:
            # Проверяем manual_boards_cache (старый способ)
            manual_boards = creds.extra_data.get('manual_boards_cache')
            if manual_boards and isinstance(manual_boards, dict) and len(manual_boards) > 0:
                logger.info(f"Используется вручную указанный список досок: {list(manual_boards.keys())}")
                boards_cache = manual_boards
            else:
                # Используем доску по умолчанию из настроек
                default_board = creds.extra_data.get('board_id')
                if default_board:
                    logger.warning(f"Используется доска по умолчанию из настроек: {default_board}")
                    return default_board
                return None
    
    # Ищем доску по названию темы (регистронезависимо)
    topic_name_lower = topic_name.lower().strip()
    logger.debug(f"Поиск доски для темы '{topic_name}' (нормализовано: '{topic_name_lower}')")
    logger.debug(f"Доступные доски: {list(boards_cache.keys())}")
    
    for board_name, board_id in boards_cache.items():
        if board_name.lower().strip() == topic_name_lower:
            logger.info(f"✅ Найдена доска '{board_name}' для темы '{topic_name}': {board_id}")
            return board_id
    
    # Если не найдена, ищем доску "code"
    for board_name, board_id in boards_cache.items():
        if board_name.lower().strip() == "code":
            logger.info(f"✅ Используется доска по умолчанию 'code': {board_id}")
            return board_id
    
    # Если ничего не найдено, используем доску из настроек
    default_board = creds.extra_data.get('board_id')
    if default_board:
        logger.warning(f"⚠️ Доска для темы '{topic_name}' не найдена, используется доска из настроек: {default_board}")
        return default_board
    
    logger.error(f"❌ Доска для темы '{topic_name}' не найдена, и доска по умолчанию не настроена")
    return None


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
            "topic": task.topic.name if task.topic and hasattr(task.topic, 'name') else "programming",
            "difficulty": task.difficulty
        },
        "metadata": {
            "language": translation.language,
            "translation_group_id": str(task.translation_group_id),
            "publish_date": timezone.now().isoformat()
        }
    }
    
    return payload

