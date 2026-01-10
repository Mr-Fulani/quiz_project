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
        
        # Получаем медиафайлы поста по приоритету:
        # 1. Главное медиа (is_main=True)
        # 2. Если главного нет - первое фото
        # 3. Если фото нет - первое GIF
        # 4. Если GIF нет - первое видео
        photos_list = []
        gifs_list = []
        videos_list = []
        
        # Сначала проверяем главное медиа
        main_image = instance.images.filter(is_main=True).first()
        main_media_added = False
        
        logger.info(f"Поиск медиа для поста '{instance.title}'. Всего медиа: {instance.images.count()}")
        
        if main_image:
            logger.info(f"Найдено главное медиа: photo={bool(main_image.photo)}, gif={bool(main_image.gif)}, video={bool(main_image.video)}")
            try:
                if main_image.photo and main_image.photo.name:
                    main_image.photo.open('rb')
                    photos_list.append(main_image.photo)
                    main_media_added = True
                    logger.info(f"Добавлено главное фото: {main_image.photo.name}")
                elif main_image.gif and main_image.gif.name:
                    main_image.gif.open('rb')
                    gifs_list.append(main_image.gif)
                    main_media_added = True
                    logger.info(f"Добавлен главный GIF: {main_image.gif.name}")
                elif main_image.video and main_image.video.name:
                    main_image.video.open('rb')
                    videos_list.append(main_image.video)
                    main_media_added = True
                    logger.info(f"Добавлено главное видео: {main_image.video.name}")
                else:
                    # Главное медиа найдено, но файла нет - ищем по приоритету
                    logger.info(f"Главное медиа найдено, но файл отсутствует (photo.name={bool(main_image.photo and main_image.photo.name)}, gif.name={bool(main_image.gif and main_image.gif.name)}, video.name={bool(main_image.video and main_image.video.name)}), ищем по приоритету")
            except Exception as e:
                logger.warning(f"Не удалось получить главное медиа для поста '{instance.title}': {e}")
        else:
            logger.info(f"Главное медиа не найдено (is_main=True), ищем по приоритету")
        
        # Если главного медиа нет или файл не был добавлен, ищем по приоритету: фото > GIF > видео
        if not main_media_added:
            logger.info(f"Поиск медиа по приоритету для поста '{instance.title}'")
            
            # Ищем первое фото: сначала не-дефолтные, потом дефолтные
            all_images = instance.images.all()
            non_default_photo = None
            default_photo = None
            
            for photo_image in all_images:
                try:
                    if photo_image.photo and photo_image.photo.name:
                        try:
                            if photo_image.photo.storage.exists(photo_image.photo.name):
                                if 'default-og-image' in photo_image.photo.name:
                                    if not default_photo:
                                        default_photo = photo_image
                                else:
                                    if not non_default_photo:
                                        non_default_photo = photo_image
                                        break  # Нашли не-дефолтное, выходим
                        except Exception:
                            continue
                except Exception:
                    continue
            
            # Используем не-дефолтное фото, если есть, иначе дефолтное
            selected_photo = non_default_photo or default_photo
            if selected_photo:
                try:
                    selected_photo.photo.open('rb')
                    photos_list.append(selected_photo.photo)
                    logger.info(f"Добавлено фото по приоритету: {selected_photo.photo.name}")
                except Exception as e:
                    logger.warning(f"Ошибка при открытии фото ID {selected_photo.id}: {e}", exc_info=True)
            
            # Если фото нет, ищем первое GIF
            if not photos_list:
                logger.info(f"Фото не найдено, ищем GIF")
                for gif_image in all_images:
                    try:
                        if gif_image.gif and gif_image.gif.name:
                            try:
                                if gif_image.gif.storage.exists(gif_image.gif.name):
                                    gif_image.gif.open('rb')
                                    gifs_list.append(gif_image.gif)
                                    logger.info(f"Добавлен GIF по приоритету: {gif_image.gif.name}")
                                    break
                            except Exception:
                                continue
                    except Exception:
                        continue
            
            # Если фото и GIF нет, ищем первое видео
            if not photos_list and not gifs_list:
                logger.info(f"Фото и GIF не найдены, ищем видео")
                for video_image in all_images:
                    try:
                        if video_image.video and video_image.video.name:
                            try:
                                if video_image.video.storage.exists(video_image.video.name):
                                    video_image.video.open('rb')
                                    videos_list.append(video_image.video)
                                    logger.info(f"Добавлено видео по приоритету: {video_image.video.name}")
                                    break
                            except Exception:
                                continue
                    except Exception:
                        continue
            
            if not photos_list and not gifs_list and not videos_list:
                logger.warning(f"Не найдено медиа для поста '{instance.title}' по приоритету")
        
        # Отправляем в каждый выбранный канал
        # Ссылка на полную версию добавляется в текст через truncate_telegram_text
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
                        buttons=None  # Кнопки не используем, ссылка в тексте
                    )
                else:
                    # Только текст
                    success = send_telegram_post_sync(
                        channel=channel,
                        text=telegram_text,
                        photos=None,
                        gifs=None,
                        videos=None,
                        buttons=None  # Кнопки не используем, ссылка в тексте
                    )
                
                if success:
                    success_count += 1
                    logger.info(f"Пост '{instance.title}' успешно отправлен в канал {channel.group_name}")
                else:
                    logger.warning(f"Не удалось отправить пост '{instance.title}' в канал {channel.group_name}")
                    
            except Exception as e:
                logger.error(f"Ошибка при отправке поста '{instance.title}' в канал {channel.group_name}: {e}")
            finally:
                # Закрываем файлы после отправки
                for f in photos_list + gifs_list + videos_list:
                    if hasattr(f, 'close'):
                        try:
                            f.close()
                        except:
                            pass
        
        if success_count > 0:
            logger.info(f"Пост '{instance.title}' отправлен в {success_count} из {telegram_channels.count()} каналов")
        
    except Exception as e:
        logger.error(f"Ошибка при автоматической отправке поста '{instance.title}' в Telegram: {e}")

