"""
Django management команда для получения списка досок Pinterest
и сохранения их в extra_data для использования при постинге.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from webhooks.models import SocialMediaCredentials
from tasks.services.platforms.pinterest_api import PinterestAPI
import json
import requests


class Command(BaseCommand):
    help = 'Получает список досок Pinterest и сохраняет их в extra_data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--boards',
            type=str,
            help='JSON строка с досками в формате {"название": "board_id", ...}',
        )
        parser.add_argument(
            '--boards-file',
            type=str,
            help='Путь к JSON файлу с досками',
        )

    def handle(self, *args, **options):
        # Получаем учетные данные Pinterest
        try:
            creds = SocialMediaCredentials.objects.get(platform='pinterest', is_active=True)
        except SocialMediaCredentials.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('❌ Pinterest учетные данные не найдены.')
            )
            self.stdout.write('Сначала выполните OAuth авторизацию: /auth/pinterest/authorize/')
            return
        
        if not creds.access_token:
            self.stdout.write(
                self.style.ERROR('❌ Access token не найден.')
            )
            self.stdout.write('Сначала выполните OAuth авторизацию: /auth/pinterest/authorize/')
            return
        
        # Инициализируем extra_data, если его нет
        if not creds.extra_data:
            creds.extra_data = {}
        
        # Получаем информацию о пользователе
        api = PinterestAPI(creds.access_token)
        user_info = api.get_user_info()
        board_count = 0
        if user_info:
            board_count = user_info.get('board_count', 0)
            username = user_info.get('username', '')
            self.stdout.write(f'👤 Пользователь: {username}')
            self.stdout.write(f'📊 Количество досок по API: {board_count}')
        
        # Сначала проверяем аргументы командной строки (приоритет)
        if options['boards']:
            try:
                boards_cache = json.loads(options['boards'])
                self.stdout.write(self.style.SUCCESS('✅ Получены доски из аргумента --boards'))
                for name, board_id in boards_cache.items():
                    self.stdout.write(f'   • {name}: {board_id}')
            except json.JSONDecodeError as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Ошибка парсинга JSON: {e}')
                )
                return
        elif options['boards_file']:
            try:
                with open(options['boards_file'], 'r', encoding='utf-8') as f:
                    boards_cache = json.load(f)
                self.stdout.write(f'✅ Получены доски из файла {options["boards_file"]}')
                for name, board_id in boards_cache.items():
                    self.stdout.write(f'   • {name}: {board_id}')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Ошибка чтения файла: {e}')
                )
                return
        else:
            # Пробуем получить доски через API
            self.stdout.write('\n📋 Попытка получить доски через API...')
            boards_data = api.get_boards()
            
            boards_cache = {}
            
            if boards_data and boards_data.get('items'):
                items = boards_data.get('items', [])
                self.stdout.write(self.style.SUCCESS(f'✅ Получено досок через API: {len(items)}'))
                
                for board in items:
                    board_name = board.get('name')
                    board_id = board.get('id')
                    if board_name and board_id:
                        boards_cache[board_name] = str(board_id)
                        self.stdout.write(f'   • {board_name}: {board_id}')
            
            # Если API не вернул доски, но board_count > 0, пробуем получить из пинов
            if not boards_cache and board_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠️ API не вернул доски, но у вас их {board_count}.'
                    )
                )
                self.stdout.write('Пробуем получить board_id из существующих пинов...\n')
                
                # Пробуем получить доски из пинов
                pins_data = api.get_pins()
                if not pins_data or not pins_data.get('items'):
                    self.stdout.write(
                        self.style.WARNING('⚠️ У вас нет пинов, поэтому board_id не может быть извлечен автоматически.')
                    )
                    self.stdout.write('\n📋 Решение (выберите один способ):')
                    self.stdout.write('\nСпособ 1: Создайте один тестовый пин на каждой доске (можно потом удалить)')
                    self.stdout.write('  1. Создайте один тестовый пин на каждой доске через веб-интерфейс Pinterest')
                    self.stdout.write('  2. Запустите команду БЕЗ аргументов - она извлечет board_id из пинов')
                    self.stdout.write('  3. После этого можете удалить тестовые пины - доски останутся')
                    self.stdout.write('\nСпособ 2: Укажите board_id вручную через --boards')
                    self.stdout.write('  docker compose exec quiz_backend python manage.py get_pinterest_boards --boards \'{"Python": "900579325426238155", "code": "900579325426238155"}\'')
                    self.stdout.write('\n💡 Формат: {"название_доски": "board_id", ...}')
                    return
                
                if pins_data and pins_data.get('items'):
                    pins = pins_data.get('items', [])
                    self.stdout.write(f'✅ Найдено пинов: {len(pins)}')
                    
                    # Показываем все board_id из пинов для отладки
                    all_board_ids = set()
                    for pin in pins:
                        board_id = pin.get('board_id')
                        if board_id:
                            all_board_ids.add(str(board_id))
                    if all_board_ids:
                        self.stdout.write(f'📋 Найденные board_id в пинах: {sorted(all_board_ids)}')
                
                # Извлекаем уникальные board_id из пинов
                unique_board_ids = {}
                for pin in pins:
                    board_id = pin.get('board_id')
                    if board_id:
                        board_id_str = str(board_id)
                        # Пробуем получить название доски из разных мест
                        board_name = (
                            pin.get('board_name') or 
                            pin.get('board', {}).get('name') or
                            pin.get('board_owner', {}).get('board_name')
                        )
                        
                        if board_id_str not in unique_board_ids:
                            unique_board_ids[board_id_str] = {
                                'id': board_id_str,
                                'name': board_name,
                                'count': 0
                            }
                        unique_board_ids[board_id_str]['count'] += 1
                
                if unique_board_ids:
                    self.stdout.write(f'\n✅ Найдено уникальных досок: {len(unique_board_ids)}')
                    
                    # Пробуем получить названия досок через API
                    for board_id, board_info in unique_board_ids.items():
                        if not board_info['name']:
                            # Пробуем получить название доски через API
                            try:
                                board_response = requests.get(
                                    f"{api.BASE_URL}/boards/{board_id}",
                                    headers=api.headers,
                                    timeout=10
                                )
                                if board_response.status_code == 200:
                                    board_data = board_response.json()
                                    board_info['name'] = board_data.get('name', f'Board_{board_id}')
                            except:
                                pass
                        
                        # Если название не получено, используем board_id как название
                        # В Sandbox API названия досок недоступны, но board_id мы получили из пинов
                        board_name = board_info['name'] or board_id
                        self.stdout.write(f'   • {board_name}: {board_id} (пинов: {board_info["count"]})')
                        boards_cache[board_name] = board_id
                    
                    # Если названия не получены, объясняем ситуацию
                    if any(name.startswith('Board_') or name.isdigit() for name in boards_cache.keys()):
                        self.stdout.write(
                            self.style.WARNING(
                                '\n⚠️ Названия досок не получены из API (ограничение Sandbox API).'
                            )
                        )
                        self.stdout.write('Но board_id успешно извлечен из ваших пинов!')
                        
                        # Показываем, сколько досок найдено и сколько всего
                        if board_count > len(boards_cache):
                            self.stdout.write(
                                self.style.WARNING(
                                    f'\n⚠️ Найдено досок с пинами: {len(boards_cache)}, но всего досок: {board_count}'
                                )
                            )
                            self.stdout.write('Чтобы получить board_id для остальных досок:')
                            self.stdout.write('  1. Добавьте по одному пину на каждую доску без пинов')
                            self.stdout.write('  2. Запустите команду снова БЕЗ аргументов')
                        
                        self.stdout.write('\n💡 Чтобы указать правильные названия досок, используйте:')
                        self.stdout.write('   docker compose exec quiz_backend python manage.py get_pinterest_boards --boards \'{"code": "900579325426238155", "Python": "900579325426238155"}\'')
                        self.stdout.write('   (где ключи - это названия досок, значения - board_id)')
                    
                    if boards_cache:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'\n✅ Получено досок из пинов: {len(boards_cache)}'
                            )
                        )
            
            # Если все еще нет досок, показываем инструкции
            if not boards_cache:
                self.stdout.write('\n💡 У вас нет пинов, поэтому board_id не может быть извлечен автоматически.')
                self.stdout.write('\n📋 Решение (выберите один способ):')
                self.stdout.write('\nСпособ 1: Создайте один тестовый пин на каждой доске (можно потом удалить)')
                self.stdout.write('  1. Создайте один тестовый пин на каждой доске через веб-интерфейс Pinterest')
                self.stdout.write('  2. Запустите команду БЕЗ аргументов - она извлечет board_id из пинов')
                self.stdout.write('  3. После этого можете удалить тестовые пины - доски останутся')
                self.stdout.write('\nСпособ 2: Укажите board_id вручную через --boards')
                self.stdout.write('  docker compose exec quiz_backend python manage.py get_pinterest_boards --boards \'{"Python": "900579325426238155", "code": "900579325426238155"}\'')
                self.stdout.write('\n💡 Формат: {"название_доски": "board_id", ...}')
                return
        
        # Если доски получены, сохраняем их
        if boards_cache:
            creds.extra_data['boards_cache'] = boards_cache
            creds.extra_data['boards_cache_time'] = timezone.now().isoformat()
            creds.save(update_fields=['extra_data'])
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Сохранено досок в extra_data: {len(boards_cache)}'
                )
            )
            self.stdout.write('Доски будут использоваться при постинге для выбора по теме задачи.')
            
            # Показываем сохраненные доски
            self.stdout.write('\n📋 Сохраненные доски:')
            for name, board_id in boards_cache.items():
                self.stdout.write(f'   • {name}: {board_id}')
        else:
            self.stdout.write(
                self.style.ERROR('\n❌ Не удалось получить доски.')
            )
            self.stdout.write('Попробуйте указать их вручную через --manual флаг.')


