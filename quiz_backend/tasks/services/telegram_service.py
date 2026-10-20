"""
Сервис для публикации задач в Telegram через Bot API.
Адаптирован из bot/services/publication_service.py и bot/services/task_service.py.
"""
import html
import json
import logging
import os
import random
import time
from typing import Dict, List, Optional

import requests
from django.conf import settings
from django.utils.text import slugify

from tenants.scoping import bot_token_for

logger = logging.getLogger(__name__)

# Максимальная длина текста сообщения Telegram
TELEGRAM_MESSAGE_LIMIT = 4096


# Словарь переводов для разных языков (синхронизирован с ботом)
LANGUAGE_TRANSLATIONS = {
    'ru': {
        'programming_language': 'Язык',
        'topic': 'Тема',
        'subtopic': 'Подтема',
        'no_subtopic': 'Без подтемы',
        'difficulty': 'Сложность',
        'quiz_question': "Какой будет вывод?",
        'dont_know': "Я не знаю, но хочу узнать",
        'explanation': "💡 Объяснение",
        'learn_more': "Узнать подробнее",
        'learn_more_about_task': "Узнать больше о задаче:"
    },
    'en': {
        'programming_language': 'Language',
        'topic': 'Topic',
        'subtopic': 'Subtopic',
        'no_subtopic': 'No subtopic',
        'difficulty': 'Difficulty',
        'quiz_question': "What will be the output?",
        'dont_know': "I don't know, but I want to learn",
        'explanation': "💡 Explanation",
        'learn_more': "Learn more",
        'learn_more_about_task': "Learn more about the task:"
    },
    'es': {
        'programming_language': 'Idioma',
        'topic': 'Tema',
        'subtopic': 'Subtema',
        'no_subtopic': 'Sin subtema',
        'difficulty': 'Dificultad',
        'quiz_question': "¿Cuál será el resultado?",
        'dont_know': "No lo sé, pero quiero aprender",
        'explanation': "💡 Explicación",
        'learn_more': "Saber más",
        'learn_more_about_task': "Saber más sobre la tarea:"
    },
    'tr': {
        'programming_language': 'Dil',
        'topic': 'Konu',
        'subtopic': 'Alt konu',
        'no_subtopic': 'Alt konu yok',
        'difficulty': 'Zorluk',
        'quiz_question': "Çıktı ne olacak?",
        'dont_know': "Bilmiyorum, ama öğrenmek istiyorum",
        'explanation': "💡 Açıklama",
        'learn_more': "Daha fazla öğren",
        'learn_more_about_task': "Görev hakkında daha fazla öğren:"
    },
    'ar': {
        'programming_language': 'اللغة',
        'topic': 'الموضوع',
        'subtopic': 'الموضوع الفرعي',
        'no_subtopic': 'بدون موضوع فرعي',
        'difficulty': 'الصعوبة',
        'quiz_question': "ما هي النتيجة؟",
        'dont_know': "لا أعرف، ولكن أريد أن أتعلم",
        'explanation': "💡 التفسير",
        'learn_more': "تعلم المزيد",
        'learn_more_about_task': "تعرف على المزيد حول المهمة:"
    },
    'fr': {
        'programming_language': 'Langue',
        'topic': 'Sujet',
        'subtopic': 'Sous-sujet',
        'no_subtopic': 'Pas de sous-sujet',
        'difficulty': 'Difficulté',
        'quiz_question': "Quel sera le résultat?",
        'dont_know': "Je ne sais pas, mais je veux apprendre",
        'explanation': "💡 Explication",
        'learn_more': "En savoir plus",
        'learn_more_about_task': "En savoir plus sur la tâche :"
    },
    'de': {
        'programming_language': 'Sprache',
        'topic': 'Thema',
        'subtopic': 'Unterthema',
        'no_subtopic': 'Kein Unterthema',
        'difficulty': 'Schwierigkeit',
        'quiz_question': "Was wird die Ausgabe sein?",
        'dont_know': "Ich weiß es nicht, aber ich möchte lernen",
        'explanation': "💡 Erklärung",
        'learn_more': "Mehr erfahren",
        'learn_more_about_task': "Erfahren Sie mehr über die Aufgabe:"
    },
    'hi': {
        'programming_language': 'भाषा',
        'topic': 'विषय',
        'subtopic': 'उप-विषय',
        'no_subtopic': 'कोई उप-विषय नहीं',
        'difficulty': 'कठिनाई',
        'quiz_question': "आउटपुट क्या होगा?",
        'dont_know': "मुझे नहीं पता, लेकिन मैं सीखना चाहता हूँ",
        'explanation': "💡 व्याख्या",
        'learn_more': "अधिक जानें",
        'learn_more_about_task': "कार्य के बारे में अधिक जानें:"
    },
    'fa': {
        'programming_language': 'زبان',
        'topic': 'موضوع',
        'subtopic': 'زیرموضوع',
        'no_subtopic': 'بدون زیرموضوع',
        'difficulty': 'سختی',
        'quiz_question': "خروجی چه خواهد بود؟",
        'dont_know': "نمی‌دانم، اما می‌خواهم یاد بگیرم",
        'explanation': "💡 توضیح",
        'learn_more': "بیشتر بدانید",
        'learn_more_about_task': "بیشتر درباره وظیفه بدانید:"
    },
    'tj': {
        'programming_language': 'Забон',
        'topic': 'Мавзӯъ',
        'subtopic': 'Зермавзӯъ',
        'no_subtopic': 'Бидуни зермавзӯъ',
        'difficulty': 'Душворӣ',
        'quiz_question': "Натиҷа чӣ хоҳад буд?",
        'dont_know': "Ман намедонам, аммо мехоҳам омӯзам",
        'explanation': "💡 Шарҳ",
        'learn_more': "Дарастар бигӯед",
        'learn_more_about_task': "Дар бораи вазифа бештар маълумот гиред:"
    },
    'uz': {
        'programming_language': 'Til',
        'topic': 'Mavzu',
        'subtopic': 'Kichik mavzu',
        'no_subtopic': 'Kichik mavzu yoʻq',
        'difficulty': 'Qiyinlik',
        'quiz_question': "Natija nima boʻladi?",
        'dont_know': "Bilmayman, lekin o'rganmoqchiman",
        'explanation': "💡 Tushuntirish",
        'learn_more': "Batafsil bilish",
        'learn_more_about_task': "Vazifa haqida ko'proq bilish:"
    },
    'kz': {
        'programming_language': 'Тіл',
        'topic': 'Тақырып',
        'subtopic': 'Қосымша тақырып',
        'no_subtopic': 'Қосымша тақырып жоқ',
        'difficulty': 'Қиындық',
        'quiz_question': "Нәтиже не болады?",
        'dont_know': "Білмеймін, бірақ үйренгім келеді",
        'explanation': "💡 Түсіндірме",
        'learn_more': "Толығырақ білу",
        'learn_more_about_task': "Тапсырма туралы көбірек біліңіз:"
    },
}


def escape_markdown_v2(text: str) -> str:
    """
    Экранирует специальные символы для MarkdownV2.
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def send_photo(chat_id: str, photo_url: str, caption: str = None, bot_token: Optional[str] = None) -> Optional[Dict]:
    """
    Отправляет фото в Telegram канал.
    
    Args:
        chat_id: ID канала или чата
        photo_url: URL изображения
        caption: Подпись к фото
        
    Returns:
        Результат отправки или None при ошибке
    """
    token = bot_token or settings.TELEGRAM_BOT_TOKEN  # токен бота тенанта или глобальный
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return None
    
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    
    data = {
        'chat_id': chat_id,
        'photo': photo_url,
    }
    
    if caption:
        data['caption'] = caption
    
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, data=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                logger.info(f"✅ Фото успешно отправлено в {chat_id}")
                return result['result']
            else:
                logger.error(f"❌ Ошибка отправки фото: {result.get('description')}")
                if attempt < max_retries:
                    time.sleep(1 + attempt * 0.3)
                    continue
                return None
                
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"🔌 Ошибка подключения при отправке фото (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(1 + attempt * 0.5)
                continue
            logger.error(f"❌ Ошибка подключения при отправке фото: {e}")
            logger.error(f"   Это сетевая ошибка - возможно, Telegram API недоступен или проблемы с интернетом")
            return None
        except requests.exceptions.Timeout as e:
            logger.warning(f"⏱️ Таймаут при отправке фото (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(3)
                continue
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка при отправке фото: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.error(f"   Response: {error_data}")
                except:
                    logger.error(f"   Response text: {e.response.text[:500]}")
            return None
        except Exception as e:
            logger.error(f"❌ Исключение при отправке фото: {e}")
            return None


def send_video(chat_id: str, video_url: str, caption: str = None, bot_token: Optional[str] = None) -> Optional[Dict]:
    """
    Отправляет видео в Telegram чат по URL.
    
    Args:
        chat_id: ID чата или канала
        video_url: URL видео
        caption: Подпись к видео
        
    Returns:
        Результат отправки или None при ошибке
    """
    token = bot_token or settings.TELEGRAM_BOT_TOKEN  # токен бота тенанта или глобальный
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return None
    
    url = f"https://api.telegram.org/bot{token}/sendVideo"
    
    data = {
        'chat_id': chat_id,
        'video': video_url,
    }
    
    if caption:
        data['caption'] = caption
    
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, data=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                logger.info(f"✅ Видео успешно отправлено в {chat_id}")
                return result['result']
            else:
                logger.error(f"❌ Ошибка отправки видео: {result.get('description')}")
                if attempt < max_retries:
                    time.sleep(1 + attempt * 0.3)
                    continue
                return None
                
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"🔌 Ошибка подключения при отправке видео (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(1 + attempt * 0.5)
                continue
            logger.error(f"❌ Ошибка подключения при отправке видео: {e}")
            return None
        except requests.exceptions.Timeout as e:
            logger.warning(f"⏱️ Таймаут при отправке видео (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(3)
                continue
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка при отправке видео: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.error(f"   Response: {error_data}")
                except:
                    logger.error(f"   Response text: {e.response.text[:500]}")
            return None
        except Exception as e:
            logger.error(f"❌ Исключение при отправке видео (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(1 + attempt * 0.3)
                continue
            return None


def send_video_file(chat_id: str, video_path: str, caption: str = None, bot_token: Optional[str] = None) -> Optional[Dict]:
    """
    Отправляет видео файл напрямую в Telegram чат.
    
    Args:
        chat_id: ID чата или канала
        video_path: Путь к файлу видео на диске
        caption: Подпись к видео
        
    Returns:
        Результат отправки или None при ошибке
    """
    token = bot_token or settings.TELEGRAM_BOT_TOKEN  # токен бота тенанта или глобальный
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return None
    
    if not os.path.exists(video_path):
        logger.error(f"❌ Файл видео не найден: {video_path}")
        return None
    
    url = f"https://api.telegram.org/bot{token}/sendVideo"
    
    data = {
        'chat_id': chat_id,
    }
    
    if caption:
        data['caption'] = caption
    
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            with open(video_path, 'rb') as video_file:
                files = {'video': video_file}
                response = requests.post(url, data=data, files=files, timeout=120)  # Увеличен таймаут для загрузки файла
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                logger.info(f"✅ Видео файл успешно отправлен в {chat_id}")
                return result['result']
            else:
                logger.error(f"❌ Ошибка отправки видео файла: {result.get('description')}")
                logger.error(f"   Детали ответа: {result}")
                if attempt < max_retries:
                    time.sleep(1 + attempt * 0.3)
                    continue
                return None
                
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"🔌 Ошибка подключения при отправке видео файла (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(1 + attempt * 0.5)
                continue
            logger.error(f"❌ Ошибка подключения при отправке видео файла: {e}")
            return None
        except requests.exceptions.Timeout as e:
            logger.warning(f"⏱️ Таймаут при отправке видео файла (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(3)
                continue
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка при отправке видео файла: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.error(f"   Response: {error_data}")
                except:
                    logger.error(f"   Response text: {e.response.text[:500]}")
            return None
        except Exception as e:
            logger.error(f"❌ Исключение при отправке видео файла (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(1 + attempt * 0.3)
                continue
            return None


def send_message(chat_id: str, text: str, parse_mode: str = "MarkdownV2", bot_token: Optional[str] = None) -> Optional[Dict]:
    """
    Отправляет текстовое сообщение в Telegram канал.
    
    Args:
        chat_id: ID канала или чата
        text: Текст сообщения
        parse_mode: Режим парсинга (MarkdownV2, HTML, None)
        
    Returns:
        Результат отправки или None при ошибке
    """
    token = bot_token or settings.TELEGRAM_BOT_TOKEN  # токен бота тенанта или глобальный
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return None
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    data = {
        'chat_id': chat_id,
        'text': text,
    }
    
    if parse_mode:
        data['parse_mode'] = parse_mode
    
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, data=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                logger.info(f"✅ Сообщение успешно отправлено в {chat_id}")
                return result['result']
            else:
                logger.error(f"❌ Ошибка отправки сообщения: {result.get('description')}")
                if attempt < max_retries:
                    time.sleep(1 + attempt * 0.3)
                    continue
                return None
                
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"🔌 Ошибка подключения при отправке сообщения (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(1 + attempt * 0.5)
                continue
            logger.error(f"   Это сетевая ошибка - возможно, Telegram API недоступен или проблемы с интернетом")
            return None
        except requests.exceptions.Timeout as e:
            logger.warning(f"⏱️ Таймаут при отправке сообщения (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(3)
                continue
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка при отправке сообщения: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.error(f"   Response: {error_data}")
                except:
                    logger.error(f"   Response text: {e.response.text[:500]}")
            return None
        except Exception as e:
            logger.error(f"❌ Исключение при отправке сообщения: {e}")
            return None


def send_poll(chat_id: str, question: str, options: List[str], 
              correct_option_id: int, explanation: str = None,
              is_anonymous: bool = True, bot_token: Optional[str] = None) -> Optional[Dict]:
    """
    Отправляет опрос (quiz) в Telegram канал.
    
    Args:
        chat_id: ID канала или чата
        question: Текст вопроса (макс 300 символов)
        options: Список вариантов ответа
        correct_option_id: Индекс правильного ответа
        explanation: Объяснение правильного ответа (макс 200 символов)
        is_anonymous: Анонимный ли опрос
        
    Returns:
        Результат отправки или None при ошибке
    """
    token = bot_token or settings.TELEGRAM_BOT_TOKEN  # токен бота тенанта или глобальный
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return None
    
    # Telegram API ограничения
    MAX_QUESTION_LENGTH = 300
    MAX_EXPLANATION_LENGTH = 200
    
    # Обрезаем вопрос если слишком длинный
    if len(question) > MAX_QUESTION_LENGTH:
        logger.warning(f"Вопрос слишком длинный ({len(question)} символов), обрезаем до {MAX_QUESTION_LENGTH}")
        question = question[:MAX_QUESTION_LENGTH - 3] + '...'
    
    # Обрезаем объяснение если слишком длинное
    if explanation and len(explanation) > MAX_EXPLANATION_LENGTH:
        logger.warning(f"Объяснение слишком длинное ({len(explanation)} символов), обрезаем до {MAX_EXPLANATION_LENGTH}")
        explanation = explanation[:MAX_EXPLANATION_LENGTH - 3] + '...'
    
    url = f"https://api.telegram.org/bot{token}/sendPoll"
    
    # Telegram API требует JSON payload, а не form data для опросов
    payload = {
        'chat_id': chat_id,
        'question': question,
        'options': options,  # Передаем как list, не как JSON string
        'type': 'quiz',
        'correct_option_id': correct_option_id,
        'is_anonymous': is_anonymous,
    }
    
    if explanation:
        payload['explanation'] = explanation
    
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            # Отправляем как JSON
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                logger.info(f"✅ Опрос успешно отправлен в {chat_id}")
                return result['result']
            else:
                error_desc = result.get('description', 'Unknown error')
                logger.error(f"❌ Ошибка отправки опроса: {error_desc}")
                logger.error(f"   Детали: question length={len(question)}, question={question[:100]}..., options={options}, correct={correct_option_id}")
                # Если ошибка связана с длиной вопроса, логируем это явно
                if 'question' in error_desc.lower() or 'length' in error_desc.lower() or '300' in error_desc:
                    logger.error(f"   ⚠️ Проблема с длиной вопроса: {len(question)} символов (макс: 300)")
                if attempt < max_retries:
                    time.sleep(1 + attempt * 0.3)
                    continue
                return None
                
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"🔌 Ошибка подключения при отправке опроса (попытка {attempt}/{max_retries}): {e}")
            logger.error(f"   Question length: {len(question)}, Question preview: {question[:100]}")
            if attempt < max_retries:
                time.sleep(1 + attempt * 0.5)
                continue
            logger.error(f"❌ Ошибка подключения при отправке опроса: {e}")
            return None
        except requests.exceptions.Timeout as e:
            logger.warning(f"⏱️ Таймаут при отправке опроса (попытка {attempt}/{max_retries}): {e}")
            logger.error(f"   Question length: {len(question)}, Question preview: {question[:100]}")
            if attempt < max_retries:
                time.sleep(1 + attempt * 0.5)
                continue
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка при отправке опроса: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.error(f"   Response: {error_data}")
                except:
                    logger.error(f"   Response text: {e.response.text[:500]}")
            else:
                logger.error(f"   Response: N/A")
            logger.error(f"   Question length: {len(question)}, Question preview: {question[:100]}")
            if attempt < max_retries:
                time.sleep(1 + attempt * 0.3)
                continue
            return None
        except Exception as e:
            logger.error(f"❌ Исключение при отправке опроса: {e}")
            logger.error(f"   Question length: {len(question)}, Question preview: {question[:100]}")
            return None


def delete_message(chat_id: str, message_id: int, bot_token: Optional[str] = None) -> bool:
    """
    Удаляет сообщение из Telegram канала/чата.
    
    Args:
        chat_id: ID канала или чата
        message_id: ID сообщения для удаления
        
    Returns:
        True если удаление успешно, False при ошибке
    """
    token = bot_token or settings.TELEGRAM_BOT_TOKEN  # токен бота тенанта или глобальный
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return False
    
    url = f"https://api.telegram.org/bot{token}/deleteMessage"
    
    data = {
        'chat_id': chat_id,
        'message_id': message_id,
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get('ok'):
            logger.info(f"✅ Сообщение {message_id} успешно удалено из канала {chat_id}")
            return True
        else:
            error_description = result.get('description', 'Unknown error')
            # Не логируем как ошибку, если сообщение уже удалено или нет прав
            if 'message to delete not found' in error_description.lower() or \
               'not enough rights' in error_description.lower() or \
               'message can\'t be deleted' in error_description.lower():
                logger.warning(f"⚠️ Не удалось удалить сообщение {message_id} из {chat_id}: {error_description}")
            else:
                logger.error(f"❌ Ошибка удаления сообщения {message_id} из {chat_id}: {error_description}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Исключение при удалении сообщения {message_id} из {chat_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при удалении сообщения {message_id} из {chat_id}: {e}")
        return False


def send_message_with_button(chat_id: str, text: str, button_text: str, 
                             button_url: str, parse_mode: str = "MarkdownV2", bot_token: Optional[str] = None) -> Optional[Dict]:
    """
    Отправляет сообщение с inline кнопкой.
    
    Args:
        chat_id: ID канала или чата
        text: Текст сообщения
        button_text: Текст кнопки
        button_url: URL кнопки
        parse_mode: Режим парсинга
        
    Returns:
        Результат отправки или None при ошибке
    """
    token = bot_token or settings.TELEGRAM_BOT_TOKEN  # токен бота тенанта или глобальный
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return None
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Формируем inline keyboard
    inline_keyboard = {
        'inline_keyboard': [[
            {'text': button_text, 'url': button_url}
        ]]
    }
    
    data = {
        'chat_id': chat_id,
        'text': text,
        'reply_markup': json.dumps(inline_keyboard),
    }
    
    if parse_mode:
        data['parse_mode'] = parse_mode
    
    # Retry механизм: 3 попытки с увеличенным timeout
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"🔄 Попытка {attempt}/{max_retries} отправки кнопки...")
            response = requests.post(url, data=data, timeout=60)  # Увеличен timeout до 60 сек
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                logger.info(f"✅ Сообщение с кнопкой успешно отправлено в {chat_id}")
                return result['result']
            else:
                logger.error(f"❌ Ошибка отправки сообщения с кнопкой: {result.get('description')}")
                if attempt < max_retries:
                    time.sleep(2)  # Задержка перед повтором
                    continue
                return None
                
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"🔌 Ошибка подключения на попытке {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                time.sleep(3)  # Задержка перед повтором
                continue
            logger.error(f"❌ Исключение при отправке сообщения с кнопкой (попытка {attempt}): {e}")
            return None
        except requests.exceptions.Timeout as e:
            logger.warning(f"⏱️ Timeout на попытке {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                time.sleep(3)  # Увеличенная задержка после timeout
                continue
            logger.error(f"❌ Все попытки отправки кнопки исчерпаны (timeout)")
            return None
        except Exception as e:
            logger.error(f"❌ Исключение при отправке сообщения с кнопкой (попытка {attempt}): {e}")
            if attempt < max_retries:
                time.sleep(2)
                continue
            return None
    
    return None


def _task_link(task, translation):
    """Ссылка для кнопки «Узнать подробнее» и её источник; (None, причина), если ссылки нет."""
    final_link = None
    link_source = ""
    if task.external_link:
        final_link = task.external_link
        link_source = "специфичная (выбрана вручную)"
    else:
        try:
            # Определяем базовый URL сайта (приоритет: Тенант задачи -> настройки -> дефолт)
            site_url = None
            if hasattr(task, 'tenant') and task.tenant:
                # У модели Tenant есть свойство .site_url, которое возвращает https://domain
                site_url = task.tenant.site_url

            if not site_url:
                site_url = getattr(settings, 'SITE_URL', '')

            if site_url and not site_url.startswith('http'):
                site_url = f'https://{site_url}'

            topic_name = 'python'
            if task.topic:
                try:
                    topic_name = task.topic.name.lower()
                except Exception:
                    logger.warning(f"Не удалось получить topic.name для задачи {task.id}")

            subtopic_name = 'general'
            if task.subtopic:
                try:
                    subtopic_name = task.subtopic.name.lower()
                except Exception:
                    logger.warning(f"Не удалось получить subtopic.name для задачи {task.id}")

            subtopic_slug = slugify(subtopic_name)
            difficulty = task.difficulty.lower() if task.difficulty else 'easy'

            supported_languages = [
                lang_code for lang_code, _ in getattr(settings, 'LANGUAGES', [('en', 'English'), ('ru', 'Russian')])
            ]
            language_code = (translation.language or '').lower() or 'en'
            if language_code not in supported_languages:
                language_code = getattr(settings, 'LANGUAGE_CODE', 'en').split('-')[0].lower() or 'en'
                if language_code not in supported_languages:
                    language_code = 'en'

            if site_url:  # без домена сайта ссылку на задачу не построить
                task_url = f"{site_url}/{language_code}/quiz/{topic_name}/{subtopic_slug}/{difficulty}/"
                final_link = f"{task_url}#task-{task.id}"
                link_source = "ссылка на задачу на сайте"
        except Exception as e:
            logger.warning(f"Ошибка формирования URL задачи на сайте: {e}", exc_info=True)
            final_link = None

    if not final_link:
        from .default_link_service import DefaultLinkService

        final_link, link_source = DefaultLinkService.get_final_link(task, translation)
    return final_link, link_source


def publish_task_to_telegram(task, translation, telegram_group) -> Dict:
    """
    Публикует задачу в Telegram-канал без картинки.

    Сообщения поста:
      1. Шапка (язык/тема/сложность) и вопрос: код — блоком с подсветкой, текст — жирным;
         кнопка «Узнать подробнее», если есть ссылка на задачу.
      2. Опрос-викторина. Для кода вопрос короткий («Какой будет вывод?» или подпись из задачи),
         для текстовой задачи — сам вопрос.
    ID всех сообщений сохраняются в task.telegram_message_ids — по ним пост удаляется.
    """
    from tasks.question_format import question_display

    language = translation.language
    chat_id = telegram_group.group_id
    # Публикуем ботом тенанта задачи (канал тенанта администрирует его бот)
    bot_token = bot_token_for(getattr(task, 'tenant', None) or getattr(telegram_group, 'tenant', None))
    lang_trans = LANGUAGE_TRANSLATIONS.get(language, LANGUAGE_TRANSLATIONS['en'])
    esc = html.escape

    result = {
        'success': False,
        'text_sent': False,
        'poll_sent': False,
        'button_sent': False,
        'message_ids': [],
        'errors': [],
        'detailed_logs': [],  # Детальные логи для админки
    }

    try:
        result['detailed_logs'].append(f"🚀 Начинаем публикацию задачи {task.id} в канал {telegram_group.group_name}")
        view = question_display(task, translation.question)

        topic_name = task.topic.name if task.topic_id else "Unknown"
        subtopic_name = task.subtopic.name if task.subtopic_id else lang_trans['no_subtopic']
        difficulty = task.difficulty.capitalize() if task.difficulty else "Unknown"

        # 1. Шапка и вопрос
        if view['theme'] == 'code':
            header = (
                f"<b>🖥️ {esc(lang_trans['programming_language'])}:</b> {esc(topic_name)}\n"
                f"<b>📂 {esc(lang_trans['topic'])}:</b> {esc(subtopic_name)}\n"
                f"<b>🎯 {esc(lang_trans['difficulty'])}:</b> {esc(difficulty)}"
            )
        else:
            header = (
                f"<b>📚 {esc(lang_trans['topic'])}:</b> {esc(topic_name)}\n"
                f"<b>📂 {esc(lang_trans['subtopic'])}:</b> {esc(subtopic_name)}\n"
                f"<b>🎯 {esc(lang_trans['difficulty'])}:</b> {esc(difficulty)}"
            )

        if view['kind'] == 'code':
            code_class = f' class="language-{view["language"]}"' if view['language'] else ''
            text = f"{header}\n\n<pre><code{code_class}>{esc(view['body'])}</code></pre>"
            poll_question = view['prompt'] or lang_trans['quiz_question']
        else:
            text = header
            poll_question = view['body']
            if len(poll_question) > 300:
                # Длинный вопрос — целиком в сообщении, в опросе — начало
                text = f"{header}\n\n<b>{esc(view['body'])}</b>"

        if len(text) > TELEGRAM_MESSAGE_LIMIT:
            message = f"Текст поста длиннее {TELEGRAM_MESSAGE_LIMIT} символов ({len(text)}) — сократите код задачи"
            result['errors'].append(message)
            result['detailed_logs'].append(f"❌ {message}")
            return result

        final_link, link_source = _task_link(task, translation)
        if final_link:
            result['detailed_logs'].append(f"🔗 Ссылка для кнопки ({link_source}): {final_link}")
            message_result = send_message_with_button(
                chat_id, text, lang_trans['learn_more'], final_link, parse_mode='HTML', bot_token=bot_token,
            )
            result['button_sent'] = bool(message_result)
        else:
            result['detailed_logs'].append(f"ℹ️ Кнопка не добавлена: {link_source or 'нет ссылки на задачу'}")
            message_result = send_message(chat_id, text, 'HTML', bot_token=bot_token)

        if message_result:
            result['text_sent'] = True
            result['message_ids'].append(message_result.get('message_id'))
            result['detailed_logs'].append(f"✅ Вопрос отправлен (message_id: {message_result.get('message_id')})")
        else:
            result['errors'].append("Не удалось отправить вопрос")
            result['detailed_logs'].append("❌ Не удалось отправить вопрос")
            return result
        time.sleep(0.2)

        # 2. Опрос
        if isinstance(translation.answers, str):
            try:
                wrong_answers = json.loads(translation.answers)
            except json.JSONDecodeError:
                logger.error("Ошибка парсинга answers")
                result['errors'].append("Ошибка парсинга вариантов ответа")
                return result
        else:
            wrong_answers = list(translation.answers)

        correct_answer = translation.correct_answer
        # Правильный ответ может быть и в списке вариантов — убираем дубли
        wrong_answers = [x for x in wrong_answers if x != correct_answer]
        options = wrong_answers + [correct_answer]
        random.shuffle(options)
        correct_option_id = options.index(correct_answer)
        options.append(lang_trans['dont_know'])

        # Telegram сам подписывает объяснение «Объяснение» — без своего префикса
        poll_explanation = f"💡 {translation.explanation}" if translation.explanation else None

        result['detailed_logs'].append(f"📊 Отправка опроса (вопрос: '{poll_question[:60]}', вариантов: {len(options)})")
        poll_result = send_poll(
            chat_id=chat_id,
            question=poll_question,
            options=options,
            correct_option_id=correct_option_id,
            explanation=poll_explanation,
            bot_token=bot_token,
        )
        if poll_result:
            result['poll_sent'] = True
            result['message_ids'].append(poll_result.get('message_id'))
            result['detailed_logs'].append(f"✅ Опрос отправлен (message_id: {poll_result.get('message_id')})")
        else:
            result['errors'].append("Не удалось отправить опрос")
            result['detailed_logs'].append("❌ Не удалось отправить опрос")

        # ID сообщений поста — для удаления; message_id — ID опроса (как раньше)
        task.telegram_message_ids = [mid for mid in result['message_ids'] if mid]
        task.message_id = poll_result.get('message_id') if poll_result else task.message_id
        task.group = telegram_group
        task.save(update_fields=['telegram_message_ids', 'message_id', 'group'])

        if result['text_sent'] and result['poll_sent']:
            result['success'] = True
            logger.info(f"✅ Задача {task.id} опубликована в {chat_id}")
            result['detailed_logs'].append(f"🎉 Задача {task.id} опубликована")

    except Exception as e:
        logger.error(f"❌ Ошибка при публикации задачи {task.id}: {e}", exc_info=True)
        result['errors'].append(str(e))
        result['detailed_logs'].append(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")

    return result
