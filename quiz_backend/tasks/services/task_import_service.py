"""
Сервис импорта задач из JSON файлов.
Портирован из bot/services/task_service.py:import_tasks_from_json.
"""
import json
import logging
import random
import uuid
from typing import Dict, List

from django.db import transaction
from topics.models import Topic, Subtopic
from platforms.models import TelegramGroup
from tasks.models import Task, TaskTranslation
from .s3_service import upload_image_to_s3
from .image_generation_service import generate_image_for_task
from .telegram_service import publish_task_to_telegram

logger = logging.getLogger(__name__)


def import_tasks_from_json(file_path: str, publish: bool = False) -> Dict:
    """
    Импорт задач из JSON файла в базу данных.
    
    Args:
        file_path: Путь к JSON файлу
        publish: Публиковать ли задачи в Telegram сразу после импорта
        
    Returns:
        Словарь с результатами импорта:
        {
            'successfully_loaded': int,
            'failed_tasks': int,
            'successfully_loaded_ids': List[int],
            'error_messages': List[str],
            'published_count': int,
            'publish_errors': List[str],
            'detailed_logs': List[str]  # Детальные логи для админки
        }
    """
    successfully_loaded = 0
    failed_tasks = 0
    successfully_loaded_ids = []
    error_messages = []
    published_count = 0
    publish_errors = []
    detailed_logs = []  # Новый список для детальных логов
    
    try:
        # Читаем JSON файл
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        logger.info(f"📄 Начинаем импорт задач из {file_path}")
        detailed_logs.append(f"📄 Начинаем импорт задач из {file_path}")
        
        tasks_data = data.get('tasks', [])
        detailed_logs.append(f"📊 Найдено задач в JSON: {len(tasks_data)}")
        
        for task_data in tasks_data:
            try:
                topic_name = task_data.get('topic')
                translations = task_data.get('translations', [])
                
                if not translations:
                    error_msg = f"Задача по топику '{topic_name}' не содержит переводов."
                    logger.error(f"❌ {error_msg}")
                    error_messages.append(error_msg)
                    failed_tasks += 1
                    continue
                
                # Получаем или создаём тему
                topic, created = Topic.objects.get_or_create(
                    name=topic_name,
                    defaults={'description': f'Topic for {topic_name}'}
                )
                
                if created:
                    logger.info(f"✅ Создана новая тема: {topic_name}")
                    detailed_logs.append(f"✅ Создана новая тема: {topic_name}")
                else:
                    detailed_logs.append(f"📂 Используется существующая тема: {topic_name}")
                
                # Получаем или создаём подтему
                subtopic_name = task_data.get('subtopic')
                subtopic = None
                
                if subtopic_name:
                    subtopic, created = Subtopic.objects.get_or_create(
                        name=subtopic_name,
                        topic=topic
                    )
                    
                    if created:
                        logger.info(f"✅ Создана новая подтема: {subtopic_name}")
                        detailed_logs.append(f"✅ Создана новая подтема: {subtopic_name}")
                    else:
                        detailed_logs.append(f"📂 Используется существующая подтема: {subtopic_name}")
                
                # Генерируем translation_group_id если его нет
                translation_group_id = task_data.get('translation_group_id')
                if not translation_group_id:
                    translation_group_id = str(uuid.uuid4())
                
                logger.debug(f"📁 Используем translation_group_id: {translation_group_id}")
                
                # Обрабатываем каждый перевод
                for translation_data in translations:
                    language = translation_data.get('language')
                    question = translation_data.get('question')
                    answers = translation_data.get('answers')
                    correct_answer = translation_data.get('correct_answer')
                    explanation = translation_data.get('explanation')
                    external_link = translation_data.get('external_link')
                    difficulty = task_data.get('difficulty', 'medium')
                    
                    # Валидация данных
                    if not all([question, answers, correct_answer]):
                        error_msg = f"Перевод на языке '{language}' неполный для задачи по топику '{topic_name}'."
                        logger.error(f"❌ {error_msg}")
                        error_messages.append(error_msg)
                        failed_tasks += 1
                        continue
                    
                    # Обработка answers
                    if isinstance(answers, str):
                        try:
                            wrong_answers = json.loads(answers)
                            if not isinstance(wrong_answers, list):
                                raise ValueError("Answers должны быть списком.")
                        except json.JSONDecodeError as e:
                            error_msg = f"Ошибка десериализации answers на языке '{language}': {e}"
                            logger.error(f"❌ {error_msg}")
                            error_messages.append(error_msg)
                            failed_tasks += 1
                            continue
                    elif isinstance(answers, list):
                        wrong_answers = answers.copy()
                    else:
                        error_msg = f"Неподдерживаемый тип для answers на языке '{language}': {type(answers)}"
                        logger.error(f"❌ {error_msg}")
                        error_messages.append(error_msg)
                        failed_tasks += 1
                        continue
                    
                    # Удаляем все вхождения правильного ответа из списка неправильных ответов
                    initial_count = len(wrong_answers)
                    wrong_answers = [x for x in wrong_answers if x != correct_answer]
                    removed_count = initial_count - len(wrong_answers)
                    if removed_count > 0:
                        logger.warning(f"⚠️ Дублирующийся правильный ответ удален ({removed_count} вхождений)")
                    
                    # Всегда сериализуем answers как JSON строку
                    serialized_answers = json.dumps(wrong_answers + [correct_answer])
                    
                    # Получаем группу для публикации
                    telegram_group = TelegramGroup.objects.filter(
                        topic_id=topic.id,
                        language=language
                    ).first()
                    
                    if not telegram_group:
                        error_msg = f"⚠️ Группа не найдена для топика '{topic_name}' и языка '{language}'. Задача для этого языка не будет создана."
                        logger.warning(error_msg)
                        error_messages.append(error_msg)
                        detailed_logs.append(error_msg)
                        failed_tasks += 1
                        continue  # Продолжаем с другими переводами
                    
                    # Используем транзакцию для создания задачи и перевода
                    try:
                        with transaction.atomic():
                            # Создаём задачу
                            task = Task.objects.create(
                                topic=topic,
                                subtopic=subtopic,
                                group=telegram_group,
                                difficulty=difficulty,
                                published=False,
                                translation_group_id=translation_group_id,
                                external_link=external_link
                            )
                            
                            logger.info(f"✅ Создана задача с ID {task.id}")
                            detailed_logs.append(f"✅ Создана задача с ID {task.id} (язык: {language}, тема: {topic_name})")
                            
                            # Создаём перевод
                            task_translation = TaskTranslation.objects.create(
                                task=task,
                                language=language,
                                question=question,
                                answers=serialized_answers,
                                correct_answer=correct_answer,
                                explanation=explanation
                            )
                            
                            logger.info(f"✅ Создан перевод для задачи {task.id} на языке {language}")
                            detailed_logs.append(f"✅ Создан перевод для задачи {task.id} на языке {language}")
                            
                            # Генерируем и загружаем изображение если его нет
                            image_url = task_data.get('image_url')
                            
                            if not image_url:
                                logger.info(f"🎨 Генерация изображения для задачи {task.id}")
                                detailed_logs.append(f"🎨 Генерация изображения для задачи {task.id} (язык кода: {topic_name})")
                                
                                try:
                                    # Генерируем изображение
                                    image = generate_image_for_task(question, topic_name)
                                    
                                    if image:
                                        # Формируем имя файла в формате, как в боте
                                        subtopic_name = task.subtopic.name if task.subtopic else 'general'
                                        image_name = f"{task.topic.name}_{subtopic_name}_{language}_{task.id}.png"
                                        image_name = image_name.replace(" ", "_").lower()
                                        
                                        image_url = upload_image_to_s3(image, image_name)
                                        
                                        if image_url:
                                            task.image_url = image_url
                                            task.save(update_fields=['image_url'])
                                            logger.info(f"✅ Изображение загружено: {image_url}")
                                            detailed_logs.append(f"✅ Изображение загружено в S3 для задачи {task.id}")
                                            detailed_logs.append(f"   URL: {image_url}")
                                        else:
                                            error_msg = f"⚠️ Не удалось загрузить изображение в S3 для задачи {task.id}. Проверьте логи Django для деталей."
                                            logger.warning(error_msg)
                                            detailed_logs.append(error_msg)
                                    else:
                                        error_msg = f"⚠️ Не удалось сгенерировать изображение для задачи {task.id}. Проверьте логи Django для деталей."
                                        logger.warning(error_msg)
                                        detailed_logs.append(error_msg)
                                        
                                except Exception as img_error:
                                    error_msg = f"❌ Ошибка генерации/загрузки изображения для задачи {task.id}: {img_error}"
                                    logger.error(error_msg, exc_info=True)
                                    detailed_logs.append(error_msg)
                            else:
                                # Используем предоставленный URL
                                task.image_url = image_url
                                task.save(update_fields=['image_url'])
                                detailed_logs.append(f"📎 Использован существующий URL изображения для задачи {task.id}")
                            
                            successfully_loaded += 1
                            successfully_loaded_ids.append(task.id)
                            
                            # Публикуем в Telegram если требуется
                            if publish and telegram_group and task.image_url:
                                try:
                                    logger.info(f"📢 Публикация задачи {task.id} в Telegram")
                                    
                                    # Ссылка будет автоматически получена через DefaultLinkService внутри publish_task_to_telegram
                                    pub_result = publish_task_to_telegram(
                                        task=task,
                                        translation=task_translation,
                                        telegram_group=telegram_group
                                    )
                                    
                                    if pub_result['success']:
                                        task.published = True
                                        task.save(update_fields=['published'])
                                        published_count += 1
                                        logger.info(f"✅ Задача {task.id} опубликована в Telegram")
                                        detailed_logs.append(f"📢 Задача {task.id} опубликована в Telegram (канал: {telegram_group.group_name})")
                                    else:
                                        pub_error = f"Задача {task.id}: {', '.join(pub_result['errors'])}"
                                        publish_errors.append(pub_error)
                                        logger.error(f"❌ {pub_error}")
                                        detailed_logs.append(f"❌ Ошибка публикации задачи {task.id}: {', '.join(pub_result['errors'])}")
                                        
                                except Exception as pub_error:
                                    error_msg = f"Ошибка публикации задачи {task.id}: {pub_error}"
                                    logger.error(f"❌ {error_msg}")
                                    publish_errors.append(error_msg)
                    
                    except Exception as task_error:
                        error_msg = f"Ошибка создания задачи для языка '{language}': {task_error}"
                        logger.error(f"❌ {error_msg}")
                        error_messages.append(error_msg)
                        failed_tasks += 1
                        continue
            
            except Exception as e:
                error_msg = f"Ошибка обработки задачи: {e}"
                logger.error(f"❌ {error_msg}")
                error_messages.append(error_msg)
                failed_tasks += 1
                continue
        
        # Итоговый отчет
        logger.info(f"✅ Импорт завершен: загружено {successfully_loaded}, ошибок {failed_tasks}")
        detailed_logs.append("=" * 60)
        detailed_logs.append(f"📊 ИТОГОВАЯ СТАТИСТИКА:")
        detailed_logs.append(f"✅ Успешно загружено задач: {successfully_loaded}")
        detailed_logs.append(f"❌ Ошибок при загрузке: {failed_tasks}")
        
        if publish:
            logger.info(f"📢 Опубликовано в Telegram: {published_count}")
            detailed_logs.append(f"📢 Опубликовано в Telegram: {published_count}")
        
        detailed_logs.append("=" * 60)
        
        return {
            'successfully_loaded': successfully_loaded,
            'failed_tasks': failed_tasks,
            'successfully_loaded_ids': successfully_loaded_ids,
            'error_messages': error_messages,
            'published_count': published_count,
            'publish_errors': publish_errors,
            'detailed_logs': detailed_logs  # Добавляем детальные логи
        }
    
    except FileNotFoundError:
        error_msg = f"Файл не найден: {file_path}"
        logger.error(f"❌ {error_msg}")
        return {
            'successfully_loaded': 0,
            'failed_tasks': 0,
            'successfully_loaded_ids': [],
            'error_messages': [error_msg],
            'published_count': 0,
            'publish_errors': [],
            'detailed_logs': [error_msg]
        }
    
    except json.JSONDecodeError as e:
        error_msg = f"Ошибка парсинга JSON: {e}"
        logger.error(f"❌ {error_msg}")
        return {
            'successfully_loaded': 0,
            'failed_tasks': 0,
            'successfully_loaded_ids': [],
            'error_messages': [error_msg],
            'published_count': 0,
            'publish_errors': [],
            'detailed_logs': [error_msg]
        }
    
    except Exception as e:
        error_msg = f"Неожиданная ошибка импорта: {e}"
        logger.error(f"❌ {error_msg}")
        return {
            'successfully_loaded': 0,
            'failed_tasks': 0,
            'successfully_loaded_ids': [],
            'error_messages': [error_msg],
            'published_count': 0,
            'publish_errors': [],
            'detailed_logs': [error_msg]
        }

