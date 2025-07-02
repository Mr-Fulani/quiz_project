import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = 'Ожидает готовности базы данных'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Таймаут ожидания в секундах (по умолчанию 30)',
        )

    def handle(self, *args, **options):
        self.stdout.write("⏳ Ожидание готовности базы данных...")
        
        timeout = options['timeout']
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Проверяем соединение с БД
                db_conn = connections['default']
                db_conn.cursor()
                self.stdout.write(
                    self.style.SUCCESS("✅ База данных готова!")
                )
                return
            except OperationalError:
                self.stdout.write("⏳ База данных еще не готова, ожидание...")
                time.sleep(1)
        
        self.stdout.write(
            self.style.ERROR(f"❌ Таймаут ожидания базы данных ({timeout} сек)")
        )
        exit(1) 