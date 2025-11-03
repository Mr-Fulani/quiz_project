"""
Django management команда для удаления всех задач и сброса счетчиков ID.

Использование:
    python manage.py reset_tasks [--confirm]
"""
from django.core.management.base import BaseCommand
from django.db import connection
from tasks.models import Task
import sys


class Command(BaseCommand):
    help = 'Удаляет все задачи из базы данных и сбрасывает счетчики ID'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Подтверждение удаления (без этого параметра команда не выполнится)',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  ВНИМАНИЕ: Это удалит ВСЕ задачи из базы данных!\n'
                    'Для подтверждения используйте флаг --confirm'
                )
            )
            sys.exit(1)

        # Подсчитываем количество задач перед удалением
        task_count = Task.objects.count()
        
        if task_count == 0:
            self.stdout.write(self.style.SUCCESS('✅ База данных уже пуста'))
            return

        self.stdout.write(f'Найдено задач: {task_count}')

        # Удаляем все задачи
        self.stdout.write('Удаление задач...')
        Task.objects.all().delete()
        
        # Сбрасываем счетчики ID через SQL
        with connection.cursor() as cursor:
            # Сбрасываем счетчик для tasks
            cursor.execute("ALTER SEQUENCE tasks_id_seq RESTART WITH 1;")
            self.stdout.write('✓ Сброшен счетчик tasks_id_seq')
            
            # Сбрасываем счетчики для связанных таблиц
            try:
                cursor.execute("ALTER SEQUENCE task_translations_id_seq RESTART WITH 1;")
                self.stdout.write('✓ Сброшен счетчик task_translations_id_seq')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Не удалось сбросить task_translations_id_seq: {e}'))
            
            try:
                cursor.execute("ALTER SEQUENCE task_statistics_id_seq RESTART WITH 1;")
                self.stdout.write('✓ Сброшен счетчик task_statistics_id_seq')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Не удалось сбросить task_statistics_id_seq: {e}'))
            
            try:
                cursor.execute("ALTER SEQUENCE task_polls_id_seq RESTART WITH 1;")
                self.stdout.write('✓ Сброшен счетчик task_polls_id_seq')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Не удалось сбросить task_polls_id_seq: {e}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Успешно удалено {task_count} задач\n'
                '✅ Счетчики ID сброшены. Новые задачи начнутся с ID = 1'
            )
        )

