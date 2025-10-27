import logging
import requests
from django.conf import settings
from django.utils import timezone
from .models import FeedbackReply

logger = logging.getLogger(__name__)


class TelegramService:
    """
    Сервис для работы с Telegram Bot API
    """
    
    def __init__(self):
        self.bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not self.bot_token:
            logger.error("TELEGRAM_BOT_TOKEN не настроен в settings")
            raise ValueError("TELEGRAM_BOT_TOKEN не настроен")
        
        self.api_base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def send_message(self, chat_id, text, parse_mode='HTML'):
        """
        Отправляет сообщение пользователю через Telegram Bot API
        
        Args:
            chat_id (int): Telegram ID пользователя
            text (str): Текст сообщения
            parse_mode (str): Режим парсинга (HTML, Markdown)
            
        Returns:
            dict: Ответ от Telegram API или None в случае ошибки
        """
        try:
            url = f"{self.api_base_url}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('ok'):
                logger.info(f"Сообщение успешно отправлено пользователю {chat_id}")
                return result
            else:
                logger.error(f"Ошибка отправки сообщения пользователю {chat_id}: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при отправке сообщения пользователю {chat_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке сообщения пользователю {chat_id}: {e}")
            return None
    
    def send_photo(self, chat_id, photo_url, caption=None, parse_mode='HTML'):
        """
        Отправляет фото пользователю через Telegram Bot API
        
        Args:
            chat_id (int): Telegram ID пользователя
            photo_url (str): URL или file_id фотографии
            caption (str): Подпись к фото
            parse_mode (str): Режим парсинга подписи
            
        Returns:
            dict: Ответ от Telegram API или None в случае ошибки
        """
        try:
            url = f"{self.api_base_url}/sendPhoto"
            data = {
                'chat_id': chat_id,
                'photo': photo_url,
            }
            
            if caption:
                data['caption'] = caption
                data['parse_mode'] = parse_mode
            
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get('ok'):
                logger.info(f"Фото успешно отправлено пользователю {chat_id}")
                return result
            else:
                logger.error(f"Ошибка отправки фото пользователю {chat_id}: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при отправке фото пользователю {chat_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке фото пользователю {chat_id}: {e}")
            return None
    
    def send_photo_file(self, chat_id, photo_path, caption=None, parse_mode='HTML'):
        """
        Отправляет фото из файловой системы пользователю
        
        Args:
            chat_id (int): Telegram ID пользователя
            photo_path (str): Путь к файлу фотографии
            caption (str): Подпись к фото
            parse_mode (str): Режим парсинга подписи
            
        Returns:
            dict: Ответ от Telegram API или None в случае ошибки
        """
        try:
            url = f"{self.api_base_url}/sendPhoto"
            data = {
                'chat_id': chat_id,
            }
            
            if caption:
                data['caption'] = caption
                data['parse_mode'] = parse_mode
            
            with open(photo_path, 'rb') as photo_file:
                files = {'photo': photo_file}
                response = requests.post(url, data=data, files=files, timeout=30)
                response.raise_for_status()
            
            result = response.json()
            if result.get('ok'):
                logger.info(f"Фото из файла успешно отправлено пользователю {chat_id}")
                return result
            else:
                logger.error(f"Ошибка отправки фото из файла пользователю {chat_id}: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при отправке фото из файла пользователю {chat_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке фото из файла пользователю {chat_id}: {e}")
            return None
    
    def send_feedback_reply(self, feedback_reply):
        """
        Отправляет ответ на сообщение поддержки пользователю.
        Если есть изображения - отправляет их вместе с текстом.
        
        Args:
            feedback_reply (FeedbackReply): Объект ответа
            
        Returns:
            bool: True если сообщение отправлено успешно, False в противном случае
        """
        try:
            # Формируем текст ответа
            original_message = feedback_reply.feedback.message
            reply_text = feedback_reply.reply_text
            admin_username = feedback_reply.admin.username or feedback_reply.admin.first_name or "Администратор"
            
            message_text = f"""
<b>Ответ от службы поддержки</b>

<i>Ваше сообщение:</i>
{original_message}

<i>Ответ от {admin_username}:</i>
{reply_text}

<i>Спасибо за обращение!</i>
            """.strip()
            
            # Проверяем наличие изображений
            images = feedback_reply.images.all()
            
            if images.exists():
                # Отправляем изображения с текстом
                logger.info(f"📷 Найдено {images.count()} изображений для отправки")
                
                # Берем первое изображение
                first_image = images.first()
                
                # Получаем полный путь к файлу
                if first_image.image:
                    image_path = first_image.image.path
                    logger.info(f"📷 Отправляем изображение: {image_path}")
                    
                    # Отправляем фото с подписью
                    result = self.send_photo_file(
                        chat_id=feedback_reply.feedback.user_id,
                        photo_path=image_path,
                        caption=message_text
                    )
                    
                    if not result:
                        logger.error("Ошибка отправки фото, отправляем только текст")
                        result = self.send_message(
                            chat_id=feedback_reply.feedback.user_id,
                            text=message_text
                        )
                else:
                    # Если нет файла, отправляем только текст
                    result = self.send_message(
                        chat_id=feedback_reply.feedback.user_id,
                        text=message_text
                    )
            else:
                # Нет изображений - отправляем только текст
                result = self.send_message(
                    chat_id=feedback_reply.feedback.user_id,
                    text=message_text
                )
            
            if result:
                # Отмечаем как отправленное
                feedback_reply.mark_as_sent()
                # Отмечаем сообщение как обработанное
                if not feedback_reply.feedback.is_processed:
                    feedback_reply.feedback.is_processed = True
                    feedback_reply.feedback.save(update_fields=['is_processed'])
                logger.info(f"Ответ #{feedback_reply.id} успешно отправлен пользователю {feedback_reply.feedback.user_id}")
                return True
            else:
                # Отмечаем ошибку
                feedback_reply.mark_send_error("Ошибка отправки через Telegram API")
                logger.error(f"Не удалось отправить ответ #{feedback_reply.id} пользователю {feedback_reply.feedback.user_id}")
                return False
                
        except Exception as e:
            error_msg = f"Ошибка при отправке ответа: {str(e)}"
            feedback_reply.mark_send_error(error_msg)
            logger.error(f"Ошибка при отправке ответа #{feedback_reply.id}: {e}")
            return False


def send_feedback_reply_to_telegram(feedback_reply_id):
    """
    Функция для отправки ответа на сообщение поддержки
    
    Args:
        feedback_reply_id (int): ID ответа для отправки
        
    Returns:
        bool: True если отправка успешна, False в противном случае
    """
    try:
        feedback_reply = FeedbackReply.objects.get(id=feedback_reply_id)
        telegram_service = TelegramService()
        return telegram_service.send_feedback_reply(feedback_reply)
    except FeedbackReply.DoesNotExist:
        logger.error(f"Ответ с ID {feedback_reply_id} не найден")
        return False
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа {feedback_reply_id}: {e}")
        return False 