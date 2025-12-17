"""
Django management команда для массовой регенерации нерабочих изображений.
Находит задачи с нерабочими ссылками на изображения и регенерирует их.
"""
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from urllib.parse import urlparse
import requests
from typing import List, Optional

from tasks.models import Task, TaskTranslation
from tasks.services.image_generation_service import generate_image_for_task
from tasks.services.s3_service import upload_image_to_s3

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Регенерирует изображения для задач с нерабочими ссылками'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Проверка без реальной регенерации',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Обработать только N задач (для тестирования)',
        )
        parser.add_argument(
            '--task-ids',
            type=str,
            help='Обработать конкретные ID задач через запятую (например: 1,2,3)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Регенерировать даже если URL рабочий',
        )
        parser.add_argument(
            '--check-s3-domain',
            type=str,
            help='Проверять задачи с указанным S3 доменом (например: bucket.s3.region.amazonaws.com)',
        )

    def check_url(self, url: str, timeout: int = 5) -> bool:
        """
        Проверяет доступность URL.
        
        Args:
            url: URL для проверки
            timeout: Таймаут запроса в секундах
            
        Returns:
            True если URL доступен, False иначе
        """
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"URL {url} недоступен: {e}")
            return False

    def get_tasks_to_regenerate(self, check_s3_domain: Optional[str] = None, force: bool = False) -> List[Task]:
        """
        Находит задачи, которые нужно регенерировать.
        
        Args:
            check_s3_domain: Проверять только задачи с указанным S3 доменом
            force: Регенерировать все задачи с image_url
            
        Returns:
            Список задач для регенерации
        """
        if force:
            # Регенерировать все задачи с image_url
            tasks = Task.objects.filter(image_url__isnull=False).exclude(image_url='')
            return list(tasks)
        
        tasks_to_regenerate = []
        
        # Находим задачи с нерабочими ссылками
        if check_s3_domain:
            # Проверяем только задачи с указанным S3 доменом
            tasks = Task.objects.filter(
                image_url__isnull=False
            ).exclude(image_url='')
            
            for task in tasks:
                if task.image_url and check_s3_domain in task.image_url:
                    tasks_to_regenerate.append(task)
        else:
            # Проверяем все задачи с image_url
            tasks = Task.objects.filter(
                image_url__isnull=False
            ).exclude(image_url='')
            
            for task in tasks:
                if task.image_url:
                    # Проверяем доступность URL
                    if not self.check_url(task.image_url):
                        tasks_to_regenerate.append(task)
        
        return tasks_to_regenerate

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options.get('limit')
        task_ids_str = options.get('task_ids')
        force = options.get('force', False)
        check_s3_domain = options.get('check_s3_domain')
        
        self.stdout.write("🔄 Начинаем регенерацию изображений для задач с нерабочими ссылками")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("   Режим DRY-RUN: изображения не будут регенерированы"))
        
        # Получаем список задач для обработки
        if task_ids_str:
            # Обрабатываем конкретные задачи
            try:
                task_ids = [int(id.strip()) for id in task_ids_str.split(',')]
                tasks = Task.objects.filter(id__in=task_ids)
                tasks_to_process = list(tasks)
                self.stdout.write(f"📋 Обработка конкретных задач: {task_ids}")
            except ValueError as e:
                self.stdout.write(self.style.ERROR(f"❌ Неверный формат task-ids: {e}"))
                return
        else:
            # Находим задачи для регенерации
            tasks_to_process = self.get_tasks_to_regenerate(check_s3_domain, force)
            
            if limit:
                tasks_to_process = tasks_to_process[:limit]
                self.stdout.write(f"📋 Ограничение: обработаем только первые {limit} задач")
        
        total_count = len(tasks_to_process)
        self.stdout.write(f"\n📊 Найдено задач для обработки: {total_count}")
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Нет задач для регенерации"))
            return
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for task in tasks_to_process:
            try:
                # Получаем первый доступный перевод (приоритет: 'ru', затем любой)
                translation = task.translations.filter(language='ru').first()
                if not translation:
                    translation = task.translations.first()
                
                if not translation:
                    skipped_count += 1
                    logger.warning(f"Задача {task.id} не имеет переводов, пропускаем")
                    self.stdout.write(f"   ⚠️ Задача {task.id}: нет переводов, пропущена")
                    continue
                
                if not translation.question:
                    skipped_count += 1
                    logger.warning(f"Задача {task.id} не имеет вопроса в переводе, пропускаем")
                    self.stdout.write(f"   ⚠️ Задача {task.id}: нет вопроса, пропущена")
                    continue
                
                # Получаем название темы
                topic_name = task.topic.name if task.topic else 'unknown'
                
                if dry_run:
                    self.stdout.write(
                        f"   [DRY-RUN] Задача {task.id}: регенерация изображения "
                        f"(тема: {topic_name}, язык: {translation.language})"
                    )
                    success_count += 1
                    continue
                
                # Генерируем новое изображение
                self.stdout.write(f"   🎨 Генерация изображения для задачи {task.id}...")
                image = generate_image_for_task(translation.question, topic_name)
                
                if not image:
                    error_count += 1
                    logger.error(f"Не удалось сгенерировать изображение для задачи {task.id}")
                    self.stdout.write(f"   ❌ Задача {task.id}: ошибка генерации изображения")
                    continue
                
                # Формируем имя файла
                subtopic_name = task.subtopic.name if task.subtopic else 'general'
                image_name = f"{topic_name}_{subtopic_name}_{translation.language}_{task.id}.png"
                image_name = image_name.replace(" ", "_").lower()
                
                # Загружаем в R2/S3
                new_image_url = upload_image_to_s3(image, image_name)
                
                if not new_image_url:
                    error_count += 1
                    logger.error(f"Не удалось загрузить изображение для задачи {task.id}")
                    self.stdout.write(f"   ❌ Задача {task.id}: ошибка загрузки изображения")
                    continue
                
                # Обновляем URL в базе данных
                old_url = task.image_url
                task.image_url = new_image_url
                task.save(update_fields=['image_url'])
                
                logger.info(f"Регенерировано изображение для задачи {task.id}: {old_url} -> {new_image_url}")
                self.stdout.write(f"   ✅ Задача {task.id}: изображение регенерировано")
                success_count += 1
                
                if success_count % 10 == 0:
                    self.stdout.write(f"   Прогресс: {success_count}/{total_count}")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Ошибка при регенерации изображения для задачи {task.id}: {e}", exc_info=True)
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Задача {task.id}: ошибка - {e}")
                )
        
        self.stdout.write(f"\n📈 Результаты регенерации:")
        self.stdout.write(f"   Всего обработано: {total_count}")
        self.stdout.write(f"   Успешно регенерировано: {success_count}")
        self.stdout.write(f"   Пропущено: {skipped_count}")
        self.stdout.write(f"   Ошибок: {error_count}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️ Это был DRY-RUN. Для реальной регенерации запустите без --dry-run"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Регенерация завершена!"))

