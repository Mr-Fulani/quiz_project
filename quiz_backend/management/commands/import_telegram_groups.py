import csv

from django.core.management.base import BaseCommand
from quiz_backend.platforms.models import TelegramGroup


class Command(BaseCommand):
    """
    Команда для импорта данных из CSV файла в таблицу TelegramGroup.

    Ожидается, что CSV файл содержит следующие колонки:
      - group_name
      - group_id
      - topic_id
      - language
      - location_type (необязательное, по умолчанию 'group')
      - username (необязательное)
    """
    help = 'Импорт данных из CSV файла в таблицу TelegramGroup'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV файлу с данными')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        self.stdout.write(f"Начинается импорт данных из {csv_file_path}")
        count = 0
        try:
            with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    try:
                        group, created = TelegramGroup.objects.get_or_create(
                            group_id=int(row['group_id']),
                            defaults={
                                'group_name': row['group_name'],
                                'topic_id_id': int(row['topic_id']),
                                'language': row['language'],
                                'location_type': row.get('location_type', 'group'),
                                'username': row.get('username') or None
                            }
                        )
                        if not created:
                            # Обновляем запись, если она уже существует
                            group.group_name = row['group_name']
                            group.topic_id_id = int(row['topic_id'])
                            group.language = row['language']
                            group.location_type = row.get('location_type', 'group')
                            group.username = row.get('username') or None
                            group.save()
                        count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Ошибка при обработке строки {row}: {e}"))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"Файл {csv_file_path} не найден."))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка чтения файла: {e}"))
            return
        self.stdout.write(self.style.SUCCESS(f"Импортировано {count} записей.")) 