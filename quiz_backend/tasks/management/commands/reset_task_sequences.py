"""
Django management команда для сброса счетчиков ID задач.

Использование:
    python manage.py reset_task_sequences
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Сбрасывает счетчики ID для всех таблиц задач (без удаления данных)'

    def handle(self, *args, **options):
        self.stdout.write('Сброс счетчиков ID...')
        
        sequences = [
            ('tasks_id_seq', 'tasks'),
            ('task_translations_id_seq', 'task_translations'),
            ('task_statistics_id_seq', 'task_statistics'),
            ('task_polls_id_seq', 'task_polls'),
            ('task_comments_id_seq', 'task_comments'),
            ('task_comment_images_id_seq', 'task_comment_images'),
            ('task_comment_reports_id_seq', 'task_comment_reports'),
        ]
        
        with connection.cursor() as cursor:
            for seq_name, table_name in sequences:
                try:
                    # Получаем текущее максимальное значение ID
                    cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table_name};")
                    max_id = cursor.fetchone()[0]
                    
                    # Если таблица пуста, сбрасываем на 1, иначе на max_id + 1
                    next_id = 1 if max_id == 0 else max_id + 1
                    cursor.execute(f"ALTER SEQUENCE {seq_name} RESTART WITH {next_id};")
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Сброшен счетчик {seq_name} → следующий ID будет {next_id}'
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️  Не удалось сбросить {seq_name}: {e}'
                        )
                    )
        
        self.stdout.write(
            self.style.SUCCESS('\n✅ Счетчики ID успешно сброшены')
        )

