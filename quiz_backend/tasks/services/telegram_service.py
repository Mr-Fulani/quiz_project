"""
Сервис для публикации задач в Telegram через Bot API.
Адаптирован из bot/services/publication_service.py и bot/services/task_service.py.
"""
import json
import logging
import os
import random
import time
from typing import Dict, List, Optional

import requests
from django.conf import settings
from django.utils.text import slugify

logger = logging.getLogger(__name__)


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


def send_photo(chat_id: str, photo_url: str, caption: str = None) -> Optional[Dict]:
    """
    Отправляет фото в Telegram канал.
    
    Args:
        chat_id: ID канала или чата
        photo_url: URL изображения
        caption: Подпись к фото
        
    Returns:
        Результат отправки или None при ошибке
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return None
    
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto"
    
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


def send_video(chat_id: str, video_url: str, caption: str = None) -> Optional[Dict]:
    """
    Отправляет видео в Telegram чат по URL.
    
    Args:
        chat_id: ID чата или канала
        video_url: URL видео
        caption: Подпись к видео
        
    Returns:
        Результат отправки или None при ошибке
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return None
    
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendVideo"
    
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


def send_video_file(chat_id: str, video_path: str, caption: str = None) -> Optional[Dict]:
    """
    Отправляет видео файл напрямую в Telegram чат.
    
    Args:
        chat_id: ID чата или канала
        video_path: Путь к файлу видео на диске
        caption: Подпись к видео
        
    Returns:
        Результат отправки или None при ошибке
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return None
    
    if not os.path.exists(video_path):
        logger.error(f"❌ Файл видео не найден: {video_path}")
        return None
    
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendVideo"
    
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


def send_message(chat_id: str, text: str, parse_mode: str = "MarkdownV2") -> Optional[Dict]:
    """
    Отправляет текстовое сообщение в Telegram канал.
    
    Args:
        chat_id: ID канала или чата
        text: Текст сообщения
        parse_mode: Режим парсинга (MarkdownV2, HTML, None)
        
    Returns:
        Результат отправки или None при ошибке
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return None
    
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    
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
              is_anonymous: bool = True) -> Optional[Dict]:
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
    if not settings.TELEGRAM_BOT_TOKEN:
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
    
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPoll"
    
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


def delete_message(chat_id: str, message_id: int) -> bool:
    """
    Удаляет сообщение из Telegram канала/чата.
    
    Args:
        chat_id: ID канала или чата
        message_id: ID сообщения для удаления
        
    Returns:
        True если удаление успешно, False при ошибке
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return False
    
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/deleteMessage"
    
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
                             button_url: str, parse_mode: str = "MarkdownV2") -> Optional[Dict]:
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
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не настроен")
        return None
    
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    
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


def publish_task_to_telegram(task, translation, telegram_group) -> Dict:
    """
    Публикует задачу в Telegram канал.
    
    Args:
        task: Объект Task из Django ORM
        translation: Объект TaskTranslation из Django ORM
        telegram_group: Объект TelegramGroup из Django ORM
        
    Returns:
        Словарь с результатами публикации
    """
    language = translation.language
    chat_id = telegram_group.group_id
    
    # Получаем переводы для языка
    lang_trans = LANGUAGE_TRANSLATIONS.get(language, LANGUAGE_TRANSLATIONS['en'])
    
    result = {
        'success': False,
        'image_sent': False,
        'text_sent': False,
        'poll_sent': False,
        'button_sent': False,
        'errors': [],
        'detailed_logs': []  # Детальные логи для админки
    }
    
    try:
        result['detailed_logs'].append(f"🚀 Начинаем публикацию задачи {task.id} в канал {telegram_group.group_name}")
        
        # 1. Отправляем изображение БЕЗ подписи (вопрос будет в опросе)
        if task.image_url:
            result['detailed_logs'].append(f"📷 Отправка изображения: {task.image_url[:50]}...")
            photo_result = send_photo(chat_id, task.image_url, caption=None)  # Без caption - вопрос будет в опросе
            time.sleep(1)
            if photo_result:
                result['image_sent'] = True
                result['detailed_logs'].append(f"✅ Изображение отправлено (message_id: {photo_result.get('message_id')})")
            else:
                result['errors'].append("Не удалось отправить изображение")
                result['detailed_logs'].append(f"❌ Не удалось отправить изображение")
        
        # 2. Отправляем детали задачи
        # Безопасный доступ к связанным объектам
        topic_name = "Unknown"
        if task.topic:
            try:
                topic_name = task.topic.name
            except Exception:
                logger.warning(f"Не удалось получить topic.name для задачи {task.id}")
        
        subtopic_name = lang_trans['no_subtopic']
        if task.subtopic:
            try:
                subtopic_name = task.subtopic.name
            except Exception:
                logger.warning(f"Не удалось получить subtopic.name для задачи {task.id}")
        
        difficulty = task.difficulty.capitalize() if task.difficulty else "Unknown"
        
        # Экранируем текст для MarkdownV2
        escaped_topic = escape_markdown_v2(topic_name)
        escaped_subtopic = escape_markdown_v2(subtopic_name)
        escaped_difficulty = escape_markdown_v2(difficulty)
        
        task_details_text = (
            f"🖥️ *{lang_trans['programming_language']}*: {escaped_topic}\n"
            f"📂 *{lang_trans['topic']}*: {escaped_subtopic}\n"
            f"🎯 *{lang_trans['difficulty']}*: {escaped_difficulty}\n"
        )
        
        result['detailed_logs'].append(f"📝 Отправка деталей задачи")
        text_result = send_message(chat_id, task_details_text, "MarkdownV2")
        time.sleep(0.2)
        if text_result:
            result['text_sent'] = True
            result['detailed_logs'].append(f"✅ Детали задачи отправлены")
        else:
            result['errors'].append("Не удалось отправить детали задачи")
            result['detailed_logs'].append(f"❌ Не удалось отправить детали задачи")
        
        # 3. Подготавливаем и отправляем опрос
        # Парсим answers
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
        
        # Удаляем все вхождения правильного ответа из списка неправильных ответов
        initial_count = len(wrong_answers)
        wrong_answers = [x for x in wrong_answers if x != correct_answer]
        removed_count = initial_count - len(wrong_answers)
        if removed_count > 0:
            logger.warning(f"⚠️ Дублирующийся правильный ответ удален ({removed_count} вхождений), обновленные варианты: {wrong_answers}")
        
        # Формируем варианты ответов
        options = wrong_answers + [correct_answer]
        random.shuffle(options)
        correct_option_id = options.index(correct_answer)
        
        # Добавляем "Я не знаю"
        dont_know_option = lang_trans['dont_know']
        options.append(dont_know_option)
        
        # Формируем объяснение
        poll_explanation = None
        if translation.explanation:
            poll_explanation = f"{lang_trans['explanation']}: {translation.explanation}"
        
        # Используем короткий вопрос, так как код уже на изображении
        poll_question = lang_trans['quiz_question']  # "Какой будет вывод?" и т.д.
        
        result['detailed_logs'].append(f"📊 Отправка quiz опроса (вопрос: '{poll_question}', вариантов: {len(options)})")
        
        poll_result = send_poll(
            chat_id=chat_id,
            question=poll_question,  # Короткий вопрос вместо полного translation.question
            options=options,
            correct_option_id=correct_option_id,
            explanation=poll_explanation
        )
        time.sleep(0.2)
        
        if poll_result:
            result['poll_sent'] = True
            poll_message_id = poll_result.get('message_id')
            result['detailed_logs'].append(f"✅ Опрос отправлен (poll_id: {poll_result.get('poll', {}).get('id', 'N/A')}, message_id: {poll_message_id})")
            
            # Сохраняем message_id опроса в задачу для возможности удаления
            if poll_message_id:
                task.message_id = poll_message_id
                task.group = telegram_group
                task.save(update_fields=['message_id', 'group'])
                logger.info(f"💾 Сохранен message_id {poll_message_id} для задачи {task.id}")
        else:
            result['errors'].append("Не удалось отправить опрос")
            # Проверяем длину вопроса для диагностики
            if len(poll_question) > 300:
                result['detailed_logs'].append(f"❌ Не удалось отправить опрос: вопрос слишком длинный ({len(poll_question)} символов, макс: 300)")
            else:
                result['detailed_logs'].append(f"❌ Не удалось отправить опрос (длина вопроса: {len(poll_question)} символов, макс: 300). Проверьте логи выше для деталей ошибки.")
        
        # 4. Определяем итоговую ссылку
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
                    site_url = getattr(settings, 'SITE_URL', 'https://quiz-code.com')

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

                task_url = f"{site_url}/{language_code}/quiz/{topic_name}/{subtopic_slug}/{difficulty}/"
                task_anchor = f"#task-{task.id}"
                final_link = task_url + task_anchor
                link_source = "ссылка на задачу на сайте"
            except Exception as e:
                logger.warning(f"Ошибка формирования URL задачи на сайте: {e}", exc_info=True)
                final_link = None

        if not final_link:
            from .default_link_service import DefaultLinkService

            final_link, link_source = DefaultLinkService.get_final_link(task, translation)
            
            # Проверяем наличие ссылки
            if final_link is None:
                error_msg = f"❌ Нет ссылки для публикации! {link_source}"
                result['errors'].append(error_msg)
                result['detailed_logs'].append(error_msg)
                result['detailed_logs'].append(
                    "💡 Решение: Создайте главную ссылку (MainFallbackLink) для языка "
                    f"{translation.language.upper()} в разделе: Webhooks → Main fallback links"
                )
                logger.error(f"Задача {task.id}: {error_msg}")
                return result
        
        result['detailed_logs'].append(
            f"🔗 Ссылка для кнопки ({link_source}): {final_link}"
        )
        
        # Отправляем кнопку с ссылкой
        button_text = lang_trans['learn_more']  # Текст на кнопке
        button_message_text = lang_trans['learn_more_about_task']  # Текст сообщения с кнопкой
        
        result['detailed_logs'].append(f"🔗 Отправка кнопки '{button_text}'...")
        
        button_result = send_message_with_button(
            chat_id=chat_id,
            text=button_message_text,
            button_text=button_text,
            button_url=final_link,
            parse_mode=None  # Без форматирования
        )
        time.sleep(0.2)
        
        if button_result:
            result['button_sent'] = True
            result['detailed_logs'].append(f"✅ Кнопка отправлена")
        else:
            result['errors'].append("Не удалось отправить кнопку (timeout или ошибка API)")
            result['detailed_logs'].append(f"❌ Не удалось отправить кнопку")
        
        # Проверяем общий успех
        if result['image_sent'] and result['text_sent'] and result['poll_sent']:
            result['success'] = True
            logger.info(f"✅ Задача {task.id} успешно опубликована в {chat_id}")
            result['detailed_logs'].append(f"🎉 Задача {task.id} ПОЛНОСТЬЮ опубликована!")
        else:
            logger.warning(f"⚠️ Задача {task.id} опубликована частично: {result}")
            result['detailed_logs'].append(f"⚠️ Задача {task.id} опубликована ЧАСТИЧНО")
            result['detailed_logs'].append(f"   Изображение: {'✅' if result['image_sent'] else '❌'}")
            result['detailed_logs'].append(f"   Детали: {'✅' if result['text_sent'] else '❌'}")
            result['detailed_logs'].append(f"   Опрос: {'✅' if result['poll_sent'] else '❌'}")
            result['detailed_logs'].append(f"   Кнопка: {'✅' if result['button_sent'] else '❌'}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при публикации задачи {task.id}: {e}")
        result['errors'].append(str(e))
        result['detailed_logs'].append(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
    
    return result

