# blog/signals.py

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.conf import settings
from .models import Post
from .utils import html_to_telegram_text, truncate_telegram_text

logger = logging.getLogger(__name__)

# Храним предыдущее состояние published для проверки изменений
_previous_published_state = {}


@receiver(pre_save, sender=Post)
def store_previous_published_state(sender, instance, **kwargs):
    """Сохраняет предыдущее состояние published перед сохранением."""
    if instance.pk:
        try:
            old_instance = Post.objects.get(pk=instance.pk)
            _previous_published_state[instance.pk] = old_instance.published
        except Post.DoesNotExist:
            _previous_published_state[instance.pk] = False
    else:
        # Для новых объектов используем временный ключ
        _previous_published_state[id(instance)] = False


@receiver(post_save, sender=Post)
def send_post_to_telegram_on_publish(sender, instance, created, **kwargs):
    """
    Автоматически отправляет пост в выбранные Telegram каналы при публикации.
    
    Отправка происходит только если:
    - Пост опубликован (published=True)
    - published изменился с False на True (или это новое создание с published=True)
    - Выбраны каналы для отправки
    """
    # Отправляем только если пост опубликован
    if not instance.published:
        return
    
    # Проверяем, изменился ли published с False на True
    # Для новых объектов используем id(instance), для существующих - pk
    state_key = instance.pk if instance.pk else id(instance)
    previous_published = _previous_published_state.get(state_key, False)
    
    # Очищаем временный ключ для новых объектов
    if not instance.pk and id(instance) in _previous_published_state:
        del _previous_published_state[id(instance)]
    
    if not created and previous_published:
        # Если пост уже был опубликован, не отправляем повторно
        return
    
    # Проверяем, есть ли выбранные каналы
    telegram_channels = instance.telegram_channels.all()
    if not telegram_channels.exists():
        return
    
    # Импортируем здесь, чтобы избежать циклических импортов
    from platforms.services import send_telegram_post_sync
    
    try:
        # Получаем URL поста
        post_url = instance.get_absolute_url()
        if post_url:
            # Строим полный URL
            from django.contrib.sites.models import Site
            try:
                site = Site.objects.get_current()
                full_url = f"https://{site.domain}{post_url}"
            except:
                # Fallback на настройки
                full_url = f"{getattr(settings, 'PUBLIC_URL', 'https://quiz-code.com')}{post_url}"
        else:
            full_url = None
        
        # Конвертируем HTML контент в формат Telegram
        telegram_text = html_to_telegram_text(instance.content, post_url=full_url)
        
        # Обрезаем текст если нужно (4096 для текстового сообщения)
        telegram_text = truncate_telegram_text(
            telegram_text,
            max_length=4096,
            post_url=full_url,
            is_caption=False
        )
        
        # Получаем медиафайлы поста
        main_image = instance.get_main_image()
        photos_list = []
        gifs_list = []
        videos_list = []
        
        if main_image:
            try:
                if main_image.photo and main_image.photo.name:
                    # Используем сам файл - send_telegram_post_sync ожидает объект с методом chunks()
                    photos_list.append(main_image.photo)
                elif main_image.gif and main_image.gif.name:
                    gifs_list.append(main_image.gif)
                elif main_image.video and main_image.video.name:
                    videos_list.append(main_image.video)
            except Exception as e:
                logger.warning(f"Не удалось получить медиафайл для поста '{instance.title}': {e}")
        
        # Подготавливаем кнопку со ссылкой на пост
        buttons = []
        if full_url:
            buttons.append({
                'text': 'Читать на сайте',
                'url': full_url
            })
        
        # Отправляем в каждый выбранный канал
        success_count = 0
        for channel in telegram_channels:
            try:
                # Если есть медиа, используем caption (лимит 1024)
                if photos_list or gifs_list or videos_list:
                    caption_text = truncate_telegram_text(
                        telegram_text,
                        max_length=1024,
                        post_url=full_url,
                        is_caption=True
                    )
                    success = send_telegram_post_sync(
                        channel=channel,
                        text=caption_text if caption_text else None,
                        photos=photos_list,
                        gifs=gifs_list,
                        videos=videos_list,
                        buttons=buttons if buttons else None
                    )
                else:
                    # Только текст
                    success = send_telegram_post_sync(
                        channel=channel,
                        text=telegram_text,
                        photos=None,
                        gifs=None,
                        videos=None,
                        buttons=buttons if buttons else None
                    )
                
                if success:
                    success_count += 1
                    logger.info(f"Пост '{instance.title}' успешно отправлен в канал {channel.group_name}")
                else:
                    logger.warning(f"Не удалось отправить пост '{instance.title}' в канал {channel.group_name}")
                    
            except Exception as e:
                logger.error(f"Ошибка при отправке поста '{instance.title}' в канал {channel.group_name}: {e}")
        
        if success_count > 0:
            logger.info(f"Пост '{instance.title}' отправлен в {success_count} из {telegram_channels.count()} каналов")
        
    except Exception as e:
        logger.error(f"Ошибка при автоматической отправке поста '{instance.title}' в Telegram: {e}")

