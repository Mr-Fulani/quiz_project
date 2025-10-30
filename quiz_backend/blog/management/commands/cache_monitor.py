"""
Management команда для мониторинга состояния кэша.

Использование:
    python manage.py cache_monitor
    python manage.py cache_monitor --clear  # Очистить весь кэш
    python manage.py cache_monitor --stats  # Показать статистику
"""
import sys
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Мониторинг и управление кэшем Django'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить весь кэш',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Показать детальную статистику кэша',
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Тест работы кэша',
        )

    def handle(self, *args, **options):
        """Основная логика команды."""
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('МОНИТОРИНГ КЭША DJANGO'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Показываем текущую конфигурацию
        self._show_configuration()
        
        # Очистка кэша
        if options['clear']:
            self._clear_cache()
            return
        
        # Статистика
        if options['stats']:
            self._show_stats()
            return
        
        # Тест кэша
        if options['test']:
            self._test_cache()
            return
        
        # По умолчанию показываем базовую информацию
        self._show_basic_info()

    def _show_configuration(self):
        """Показать конфигурацию кэша."""
        cache_backend = settings.CACHES['default']['BACKEND']
        
        self.stdout.write('\n📋 Конфигурация кэша:')
        self.stdout.write(f'   Backend: {self.style.WARNING(cache_backend)}')
        
        if 'redis' in cache_backend.lower():
            location = settings.CACHES['default'].get('LOCATION', 'не указано')
            self.stdout.write(f'   Location: {self.style.WARNING(location)}')
            
            options = settings.CACHES['default'].get('OPTIONS', {})
            if options:
                self.stdout.write('   Options:')
                for key, value in options.items():
                    if isinstance(value, dict):
                        self.stdout.write(f'      {key}:')
                        for k, v in value.items():
                            self.stdout.write(f'         {k}: {v}')
                    else:
                        self.stdout.write(f'      {key}: {value}')
        
        key_prefix = settings.CACHES['default'].get('KEY_PREFIX', 'нет')
        timeout = settings.CACHES['default'].get('TIMEOUT', 300)
        
        self.stdout.write(f'   Key Prefix: {self.style.WARNING(key_prefix)}')
        self.stdout.write(f'   Default Timeout: {self.style.WARNING(f"{timeout}s")}')

    def _show_basic_info(self):
        """Показать базовую информацию о кэше."""
        self.stdout.write('\n📊 Базовая информация:')
        
        # Проверяем подключение к кэшу
        try:
            cache.set('_test_key', 'test_value', 1)
            value = cache.get('_test_key')
            cache.delete('_test_key')
            
            if value == 'test_value':
                self.stdout.write(self.style.SUCCESS('   ✅ Кэш работает корректно'))
            else:
                self.stdout.write(self.style.ERROR('   ❌ Кэш не работает'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Ошибка подключения: {str(e)}'))
            return
        
        # Проверяем популярные ключи
        self.stdout.write('\n🔑 Популярные ключи кэша:')
        
        test_keys = [
            'user_stats_1',
            'user_stats_2',
            'quiz:user_stats_1',
        ]
        
        found_keys = 0
        for key in test_keys:
            value = cache.get(key)
            if value is not None:
                found_keys += 1
                self.stdout.write(f'   ✅ {key}: присутствует')
        
        if found_keys == 0:
            self.stdout.write('   ℹ️  Кэш пуст или ключи не найдены')

    def _show_stats(self):
        """Показать детальную статистику кэша (только для Redis)."""
        cache_backend = settings.CACHES['default']['BACKEND']
        
        if 'redis' not in cache_backend.lower():
            self.stdout.write(self.style.WARNING(
                '\n⚠️  Детальная статистика доступна только для Redis'
            ))
            return
        
        try:
            from django_redis import get_redis_connection
            
            redis_conn = get_redis_connection("default")
            info = redis_conn.info()
            
            self.stdout.write('\n📊 Статистика Redis:')
            self.stdout.write(f'   Версия: {info.get("redis_version", "N/A")}')
            self.stdout.write(f'   Uptime: {info.get("uptime_in_seconds", 0) / 3600:.1f} часов')
            self.stdout.write(f'   Подключенных клиентов: {info.get("connected_clients", 0)}')
            self.stdout.write(f'   Использовано памяти: {info.get("used_memory_human", "N/A")}')
            self.stdout.write(f'   Пик памяти: {info.get("used_memory_peak_human", "N/A")}')
            
            # Статистика ключей
            db_info = redis_conn.info('keyspace')
            if db_info:
                self.stdout.write('\n📈 Статистика ключей:')
                for db, stats in db_info.items():
                    self.stdout.write(f'   {db}: {stats}')
            
            # Статистика попаданий/промахов
            keyspace_hits = info.get('keyspace_hits', 0)
            keyspace_misses = info.get('keyspace_misses', 0)
            total = keyspace_hits + keyspace_misses
            
            if total > 0:
                hit_rate = (keyspace_hits / total) * 100
                self.stdout.write('\n🎯 Эффективность кэша:')
                self.stdout.write(f'   Попадания: {keyspace_hits:,}')
                self.stdout.write(f'   Промахи: {keyspace_misses:,}')
                self.stdout.write(f'   Hit Rate: {self.style.SUCCESS(f"{hit_rate:.2f}%")}')
                
                if hit_rate < 50:
                    self.stdout.write(self.style.WARNING(
                        '   ⚠️  Hit Rate ниже 50% - возможно, требуется оптимизация'
                    ))
            
        except ImportError:
            self.stdout.write(self.style.ERROR(
                '\n❌ django-redis не установлен'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'\n❌ Ошибка получения статистики: {str(e)}'
            ))

    def _clear_cache(self):
        """Очистить весь кэш."""
        self.stdout.write('\n🗑️  Очистка кэша...')
        
        try:
            cache.clear()
            self.stdout.write(self.style.SUCCESS('   ✅ Кэш успешно очищен'))
            
            # Проверяем, что кэш действительно очищен
            cache.set('_test_key', 'test', 1)
            if cache.get('_test_key') == 'test':
                self.stdout.write(self.style.SUCCESS('   ✅ Кэш работает после очистки'))
                cache.delete('_test_key')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Ошибка очистки: {str(e)}'))

    def _test_cache(self):
        """Тест производительности кэша."""
        import time
        
        self.stdout.write('\n🧪 Тест производительности кэша:')
        
        # Тест записи
        start = time.time()
        for i in range(1000):
            cache.set(f'test_key_{i}', f'value_{i}', 60)
        write_time = time.time() - start
        
        self.stdout.write(f'   Запись 1000 ключей: {write_time:.3f}s ({1000/write_time:.0f} ops/s)')
        
        # Тест чтения
        start = time.time()
        for i in range(1000):
            cache.get(f'test_key_{i}')
        read_time = time.time() - start
        
        self.stdout.write(f'   Чтение 1000 ключей: {read_time:.3f}s ({1000/read_time:.0f} ops/s)')
        
        # Тест удаления
        start = time.time()
        for i in range(1000):
            cache.delete(f'test_key_{i}')
        delete_time = time.time() - start
        
        self.stdout.write(f'   Удаление 1000 ключей: {delete_time:.3f}s ({1000/delete_time:.0f} ops/s)')
        
        # Оценка
        total_time = write_time + read_time + delete_time
        if total_time < 1:
            self.stdout.write(self.style.SUCCESS('\n   ✅ Отличная производительность!'))
        elif total_time < 3:
            self.stdout.write(self.style.SUCCESS('\n   ✅ Хорошая производительность'))
        else:
            self.stdout.write(self.style.WARNING('\n   ⚠️  Производительность может быть улучшена'))
        
        self.stdout.write('\n')

