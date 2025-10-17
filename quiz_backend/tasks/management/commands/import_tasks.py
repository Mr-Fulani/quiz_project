"""
Management команда для импорта задач из JSON через CLI.
Использование: python manage.py import_tasks --file path/to/tasks.json --publish
"""
from django.core.management.base import BaseCommand
from tasks.services.task_import_service import import_tasks_from_json


class Command(BaseCommand):
    help = 'Импорт задач из JSON файла'

    def add_arguments(self, parser):
        """
        Добавляет аргументы командной строки.
        """
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Путь к JSON файлу с задачами'
        )
        parser.add_argument(
            '--publish',
            action='store_true',
            help='Опубликовать задачи в Telegram сразу после импорта'
        )

    def handle(self, *args, **options):
        """
        Выполняет импорт задач.
        """
        file_path = options['file']
        publish = options['publish']

        self.stdout.write(
            self.style.SUCCESS(f'📄 Начинаем импорт из {file_path}')
        )
        
        if publish:
            self.stdout.write(
                self.style.WARNING('📢 Задачи будут опубликованы в Telegram')
            )

        # Импортируем задачи
        result = import_tasks_from_json(file_path, publish=publish)

        # Выводим результаты
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('Результаты импорта:'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Успешно загружено задач: {result['successfully_loaded']}"
            )
        )
        
        if result['successfully_loaded_ids']:
            self.stdout.write(
                f"   ID загруженных задач: {', '.join(map(str, result['successfully_loaded_ids']))}"
            )
        
        if result['failed_tasks'] > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️ Ошибок при загрузке: {result['failed_tasks']}"
                )
            )
        
        if result['published_count'] > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"📢 Опубликовано в Telegram: {result['published_count']}"
                )
            )

        # Выводим ошибки
        if result['error_messages']:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('Ошибки импорта:'))
            for error in result['error_messages']:
                self.stdout.write(self.style.ERROR(f"  ❌ {error}"))

        if result['publish_errors']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Ошибки публикации:'))
            for error in result['publish_errors']:
                self.stdout.write(self.style.WARNING(f"  ⚠️ {error}"))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('✅ Импорт завершен'))
        self.stdout.write(self.style.SUCCESS('=' * 50))

