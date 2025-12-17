"""
Django management команда для массовой генерации изображений для всех задач.

Генерирует изображения для всех задач в БД, которые еще не имеют изображений,
или регенерирует их принудительно. Включает паузы между генерациями для избежания ошибок.
"""
import logging
import time
import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from tasks.models import Task
from tasks.services.image_generation_service import generate_image_for_task
from tasks.services.s3_service import upload_image_to_s3

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Генерирует изображения для всех задач в БД. '
        'Можно указать фильтры по ID задач или translation_group_id. '
        'Включает паузы между генерациями для избежания ошибок.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Проверка без реальной генерации',
        )
        parser.add_argument(
            '--task-ids',
            type=str,
            help='Список ID задач через запятую (например: 1,2,3). Если не указан, обрабатываются все задачи.',
        )
        parser.add_argument(
            '--translation-group-ids',
            type=str,
            help='Список translation_group_id через запятую. Если не указан, обрабатываются все задачи.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Регенерировать изображения даже если они уже существуют',
        )
        parser.add_argument(
            '--pause',
            type=float,
            default=0.5,
            help='Пауза между генерациями в секундах (по умолчанию: 0.5)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Обработать только N задач (для тестирования)',
        )
        parser.add_argument(
            '--batch-test',
            action='store_true',
            help='Сначала протестировать на 10 задачах, затем продолжить все или по 100',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Размер батча для обработки (по умолчанию: 100)',
        )
        parser.add_argument(
            '--check-urls',
            action='store_true',
            help='Проверять работоспособность существующих URL перед пропуском',
        )

    def check_url(self, url: str, timeout: int = 5) -> bool:
        """
        Проверяет работоспособность URL изображения.
        
        Args:
            url: URL для проверки
            timeout: Таймаут запроса в секундах
            
        Returns:
            True если URL доступен, False иначе
        """
        if not url:
            return False
        
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            return response.status_code == 200
        except (requests.RequestException, Exception) as e:
            logger.debug(f"URL недоступен {url}: {e}")
            return False

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        task_ids_str = options.get('task_ids')
        translation_group_ids_str = options.get('translation_group_ids')
        force = options.get('force', False)
        pause = options.get('pause', 0.5)
        limit = options.get('limit')
        batch_test = options.get('batch_test', False)
        batch_size = options.get('batch_size', 100)
        check_urls = options.get('check_urls', False)

        # Формируем queryset
        queryset = Task.objects.select_related('topic', 'subtopic').prefetch_related('translations')

        # Фильтр по task_ids
        if task_ids_str:
            try:
                task_ids = [int(id.strip()) for id in task_ids_str.split(',')]
                queryset = queryset.filter(id__in=task_ids)
                self.stdout.write(
                    self.style.SUCCESS(f'📋 Фильтр по ID задач: {task_ids}')
                )
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('❌ Неверный формат task_ids. Используйте: 1,2,3')
                )
                return

        # Фильтр по translation_group_ids
        if translation_group_ids_str:
            try:
                from uuid import UUID
                group_ids = [UUID(id.strip()) for id in translation_group_ids_str.split(',')]
                queryset = queryset.filter(translation_group_id__in=group_ids)
                self.stdout.write(
                    self.style.SUCCESS(f'📋 Фильтр по translation_group_id: {group_ids}')
                )
            except (ValueError, AttributeError) as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Неверный формат translation_group_ids: {e}')
                )
                return

        # Фильтр по наличию изображений (если не force и не check_urls)
        # Если check_urls=True, мы проверим URL позже
        if not force and not check_urls:
            queryset = queryset.filter(image_url__isnull=True) | queryset.filter(image_url='')

        # Применяем limit если указан (но не в batch_test режиме)
        if limit and not batch_test:
            queryset = queryset[:limit]

        total_tasks = queryset.count()

        if total_tasks == 0:
            self.stdout.write(
                self.style.WARNING('⚠️ Не найдено задач для обработки')
            )
            if not force:
                self.stdout.write('💡 Используйте --force для регенерации существующих изображений')
            return

        self.stdout.write('=' * 60)
        self.stdout.write(
            self.style.SUCCESS(f'📊 Найдено задач для генерации: {total_tasks}')
        )
        self.stdout.write(f'⏸️  Пауза между генерациями: {pause} сек')
        if force:
            self.stdout.write(
                self.style.WARNING('🔄 Режим принудительной регенерации (--force)')
            )
        if check_urls:
            self.stdout.write('🔍 Режим проверки URL (--check-urls)')
        if batch_test:
            self.stdout.write(f'🧪 Режим тестирования: сначала 10 задач, затем батчами по {batch_size}')
        self.stdout.write('=' * 60)

        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 РЕЖИМ ПРОВЕРКИ (dry-run) - генерация не будет выполнена')
            )
            self.stdout.write('=' * 60)

        # Подтверждение (только если не batch_test)
        if not dry_run and not batch_test:
            confirm = input(
                f'\n⚠️  Вы уверены, что хотите сгенерировать изображения для {total_tasks} задач? '
                f'(yes/no): '
            )
            if confirm.lower() not in ['yes', 'y', 'да', 'д']:
                self.stdout.write(self.style.WARNING('❌ Операция отменена'))
                return

        # Обработка
        generated_count = 0
        skipped_count = 0
        error_count = 0
        errors = []
        
        try:
            # Для batch_test сначала обрабатываем 10 задач
            tasks_to_process = list(queryset)
            if batch_test:
                test_tasks = tasks_to_process[:10]
                remaining_tasks = tasks_to_process[10:]
            
            self.stdout.write(
                self.style.WARNING(f'\n🧪 ТЕСТОВЫЙ РЕЖИМ: Сначала обработаем {len(test_tasks)} задач...')
            )
            
            # Обрабатываем тестовые задачи
            test_generated = 0
            test_errors = 0
            for idx, task in enumerate(test_tasks, 1):
                result = self._process_task(
                    task, idx, len(test_tasks), dry_run, force, check_urls, pause
                )
                if result == 'generated':
                    test_generated += 1
                    generated_count += 1
                elif result == 'error':
                    test_errors += 1
                    error_count += 1
                elif result == 'skipped':
                    skipped_count += 1
            
            # Проверяем результаты теста
            if test_errors > test_generated:
                self.stdout.write(
                    self.style.ERROR(
                        f'\n❌ Тест провален: {test_errors} ошибок из {len(test_tasks)} задач. '
                        'Остановка выполнения.'
                    )
                )
                return
            
            if not dry_run:
                confirm = input(
                    f'\n✅ Тест пройден: {test_generated} успешно, {test_errors} ошибок. '
                    f'Продолжить обработку оставшихся {len(remaining_tasks)} задач? (yes/no): '
                )
                if confirm.lower() not in ['yes', 'y', 'да', 'д']:
                    self.stdout.write(self.style.WARNING('❌ Операция отменена'))
                    return
            
            # Обрабатываем оставшиеся задачи батчами
            tasks_to_process = remaining_tasks
            total_tasks = len(tasks_to_process)
            
            self.stdout.write(
                self.style.SUCCESS(f'\n🚀 Продолжаем обработку {total_tasks} задач батчами по {batch_size}...')
            )
            
            for batch_start in range(0, total_tasks, batch_size):
                batch_end = min(batch_start + batch_size, total_tasks)
                batch = tasks_to_process[batch_start:batch_end]
                
                self.stdout.write(
                    f'\n📦 Обработка батча {batch_start // batch_size + 1}: '
                    f'задачи {batch_start + 1}-{batch_end} из {total_tasks}'
                )
                
                for idx, task in enumerate(batch, batch_start + 1):
                    result = self._process_task(
                        task, idx, total_tasks, dry_run, force, check_urls, pause
                    )
                    if result == 'generated':
                        generated_count += 1
                    elif result == 'error':
                        error_count += 1
                    elif result == 'skipped':
                        skipped_count += 1
            else:
                # Обычная обработка
                total_tasks = len(tasks_to_process)
                for idx, task in enumerate(tasks_to_process, 1):
                    result = self._process_task(
                        task, idx, total_tasks, dry_run, force, check_urls, pause
                    )
                    if result == 'generated':
                        generated_count += 1
                    elif result == 'error':
                        error_count += 1
                    elif result == 'skipped':
                        skipped_count += 1

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\n⚠️  Операция прервана пользователем')
            )

        # Итоговый отчет
        self._print_summary(dry_run, total_tasks, generated_count, skipped_count, error_count, errors)

    def _process_task(self, task, idx, total_tasks, dry_run, force, check_urls, pause):
        """
        Обрабатывает одну задачу: проверяет URL, генерирует изображение.
        
        Returns:
            'generated' - изображение успешно сгенерировано
            'skipped' - задача пропущена (изображение уже есть и работает)
            'error' - произошла ошибка
        """
        # Проверяем наличие изображения
        if not force and task.image_url:
            if check_urls:
                # Проверяем работоспособность URL
                if self.check_url(task.image_url):
                    self.stdout.write(
                        f'⏭️  [{idx}/{total_tasks}] Задача {task.id}: изображение уже существует и доступно'
                    )
                    return 'skipped'
                else:
                    # URL не работает, нужно регенерировать
                    self.stdout.write(
                        self.style.WARNING(
                            f'🔧 [{idx}/{total_tasks}] Задача {task.id}: URL не работает, регенерируем...'
                        )
                    )
            else:
                # Не проверяем URL, просто пропускаем
                self.stdout.write(f'⏭️  [{idx}/{total_tasks}] Задача {task.id}: изображение уже существует')
                return 'skipped'

        # Получаем первый перевод для генерации
        translation = task.translations.first()
        if not translation:
            error_msg = f"Задача {task.id}: отсутствуют переводы"
            self.stdout.write(
                self.style.ERROR(f'❌ [{idx}/{total_tasks}] {error_msg}')
            )
            return 'error'

        try:
            topic_name = task.topic.name if task.topic else 'python'
            language_code = translation.language or "unknown"
            
            self.stdout.write(
                f'🎨 [{idx}/{total_tasks}] Генерация изображения для задачи {task.id} '
                f'(язык: {topic_name}, перевод: {language_code})...'
            )

            if not dry_run:
                # Генерируем изображение
                image = generate_image_for_task(translation.question, topic_name)

                if image:
                    # Формируем имя файла в формате, как в боте
                    subtopic_name = task.subtopic.name if task.subtopic else 'general'
                    image_name = f"{task.topic.name}_{subtopic_name}_{language_code}_{task.id}.png"
                    image_name = image_name.replace(" ", "_").lower()

                    self.stdout.write(f'☁️  [{idx}/{total_tasks}] Загрузка в S3: {image_name}...')

                    image_url = upload_image_to_s3(image, image_name)

                    if image_url:
                        task.image_url = image_url
                        task.error = False
                        task.save(update_fields=['image_url', 'error'])
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✅ [{idx}/{total_tasks}] Задача {task.id}: изображение загружено в S3'
                            )
                        )
                        self.stdout.write(f'   URL: {image_url}')
                        
                        # Пауза между генерациями (кроме последней)
                        if idx < total_tasks:
                            time.sleep(pause)
                        
                        return 'generated'
                    else:
                        task.error = True
                        task.save(update_fields=['error'])
                        error_msg = f"Задача {task.id}: не удалось загрузить в S3"
                        self.stdout.write(
                            self.style.ERROR(f'❌ [{idx}/{total_tasks}] {error_msg}')
                        )
                        return 'error'
                else:
                    task.error = True
                    task.save(update_fields=['error'])
                    error_msg = f"Задача {task.id}: не удалось сгенерировать изображение"
                    self.stdout.write(
                        self.style.ERROR(f'❌ [{idx}/{total_tasks}] {error_msg}')
                    )
                    return 'error'
            else:
                # Dry-run режим
                self.stdout.write(
                    self.style.SUCCESS(
                        f'🔍 [{idx}/{total_tasks}] Задача {task.id}: будет сгенерировано изображение'
                    )
                )
                return 'generated'

        except Exception as e:
            task.error = True
            task.save(update_fields=['error'])
            error_msg = f"Задача {task.id}: {str(e)}"
            self.stdout.write(
                self.style.ERROR(f'❌ [{idx}/{total_tasks}] {error_msg}')
            )
            logger.error(f"Ошибка при генерации изображения для задачи {task.id}: {e}", exc_info=True)
            return 'error'

    def _print_summary(self, dry_run, total_tasks, generated_count, skipped_count, error_count, errors):
        """Выводит итоговую статистику."""
        self.stdout.write('=' * 60)
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 РЕЖИМ ПРОВЕРКИ - генерация НЕ была выполнена')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ Операция завершена!')
            )

        self.stdout.write('=' * 60)
        self.stdout.write(
            self.style.SUCCESS(f'📊 Итоговая статистика:')
        )
        self.stdout.write(f'   📝 Всего обработано задач: {total_tasks}')
        self.stdout.write(f'   ✅ Сгенерировано: {generated_count}')
        if skipped_count > 0:
            self.stdout.write(f'   ⏭️  Пропущено (уже есть): {skipped_count}')
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Ошибок: {error_count}')
            )

        self.stdout.write('=' * 60)

        if not dry_run and generated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n🎯 Изображения успешно сгенерированы и загружены в S3/R2.\n'
                    '   Теперь вы можете опубликовать задачи через Django Admin.'
                )
            )

