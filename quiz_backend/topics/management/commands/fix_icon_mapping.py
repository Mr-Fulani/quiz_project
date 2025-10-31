import os
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from django.core.exceptions import OperationalError
from topics.models import Topic

class Command(BaseCommand):
    help = 'Исправляет сопоставление иконок с темами'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно обновить все иконки, даже если они уже установлены',
        )
        parser.add_argument(
            '--max-retries',
            type=int,
            default=5,
            help='Максимальное количество попыток подключения к БД (по умолчанию: 5)',
        )

    def wait_for_db(self, max_retries=5):
        """Ожидает готовности базы данных с повторными попытками"""
        for attempt in range(max_retries):
            try:
                # Пытаемся выполнить простой запрос к БД
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                return True
            except (OperationalError, Exception) as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Экспоненциальная задержка: 1s, 2s, 4s, 8s...
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️  БД недоступна (попытка {attempt + 1}/{max_retries}), "
                            f"ожидание {wait_time}с перед повторной попыткой..."
                        )
                    )
                    time.sleep(wait_time)
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"❌ Не удалось подключиться к БД после {max_retries} попыток: {str(e)}"
                        )
                    )
                    return False
        return False

    def handle(self, *args, **options):
        self.stdout.write("🔧 Исправляю сопоставление иконок с темами...")
        
        # Проверяем доступность БД перед выполнением команды
        max_retries = options.get('max_retries', 5)
        if not self.wait_for_db(max_retries):
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  Пропуск сопоставления иконок: база данных недоступна. "
                    "Команда может быть выполнена позже вручную."
                )
            )
            return
        
        # Папка с иконками (используем staticfiles после collectstatic)
        icons_dir = os.path.join(settings.BASE_DIR, 'staticfiles', 'blog', 'images', 'icons')
        
        # Если staticfiles не существует, используем исходную папку
        if not os.path.exists(icons_dir):
            icons_dir = os.path.join(settings.BASE_DIR, 'blog', 'static', 'blog', 'images', 'icons')
        
        if not os.path.exists(icons_dir):
            self.stdout.write(f"❌ Папка с иконками не найдена: {icons_dir}")
            return
        
        # Получаем список всех файлов иконок, приоритизируя PNG
        icon_files = []
        for filename in os.listdir(icons_dir):
            if filename.endswith(('.png', '.jpg', '.jpeg', '.svg')):
                icon_files.append(filename)
        
        # Сортируем файлы: PNG в начале, затем SVG
        def icon_priority(filename):
            if filename.endswith('.png'):
                return 0
            elif filename.endswith(('.jpg', '.jpeg')):
                return 1
            elif filename.endswith('.svg'):
                return 2
            else:
                return 3
        
        icon_files.sort(key=icon_priority)
        
        self.stdout.write(f"📁 Найдено {len(icon_files)} файлов иконок")
        
        # Получаем все темы с обработкой ошибок
        try:
            topics = Topic.objects.all()
            topics_count = topics.count()
            self.stdout.write(f"📚 Найдено {topics_count} тем")
        except (OperationalError, Exception) as e:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Ошибка при получении тем из БД: {str(e)}. "
                    "Команда прервана."
                )
            )
            return
        
        updated_count = 0
        not_found_count = 0
        
        for topic in topics:
            # Пропускаем темы с уже установленными иконками, если не используется --force
            if not options['force'] and topic.icon:
                continue
                
            # Формируем возможные имена файлов для темы
            possible_names = self.get_possible_icon_names(topic.name)
            
            # Ищем подходящий файл иконки, проверяя на пустоту
            found_icon = None
            
            # 1. Точное совпадение
            for icon_file in icon_files:
                icon_name_lower = icon_file.lower()
                for possible_name in possible_names:
                    expected_pattern = f"{possible_name.lower()}-icon"
                    if icon_name_lower == expected_pattern or icon_name_lower.startswith(expected_pattern):
                        icon_full_path = os.path.join(icons_dir, icon_file)
                        if os.path.exists(icon_full_path) and os.path.getsize(icon_full_path) > 100:
                            found_icon = icon_file
                            break
                        else:
                            self.stdout.write(f"  ⚠️  Пропущена пустая иконка (точное совпадение): {icon_file}")
                if found_icon:
                    break
            
            # 2. Частичное совпадение, если точное не найдено
            if not found_icon:
                for icon_file in icon_files:
                    icon_name_lower = icon_file.lower()
                    for possible_name in possible_names:
                        if possible_name.lower() in icon_name_lower:
                            icon_full_path = os.path.join(icons_dir, icon_file)
                            if os.path.exists(icon_full_path) and os.path.getsize(icon_full_path) > 100:
                                found_icon = icon_file
                                break
                            else:
                                self.stdout.write(f"  ⚠️  Пропущена пустая иконка (частичное совпадение): {icon_file}")
                    if found_icon:
                        break
            
            if found_icon:
                # Проверяем, что файл действительно существует
                icon_path = os.path.join(icons_dir, found_icon)
                if os.path.exists(icon_path):
                    # Обновляем путь к иконке в БД
                    topic.icon = f'/static/blog/images/icons/{found_icon}'
                    topic.save()
                    self.stdout.write(f"  ✅ {topic.name} → {found_icon}")
                    updated_count += 1
                else:
                    self.stdout.write(f"  ❌ Файл не существует: {found_icon}")
                    not_found_count += 1
            else:
                self.stdout.write(f"  ❌ Не найдена иконка для: {topic.name}")
                not_found_count += 1
        
        self.stdout.write(f"\n📊 Итоговая статистика:")
        self.stdout.write(f"  - Обновлено тем: {updated_count}")
        self.stdout.write(f"  - Не найдено иконок: {not_found_count}")
        self.stdout.write(f"  - Всего тем: {topics.count()}")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Сопоставление иконок завершено!"))

    def get_possible_icon_names(self, topic_name):
        """Возвращает возможные имена файлов для темы"""
        # Основное имя темы
        base_name = topic_name.lower().replace(' ', '-').replace('.', '').replace('#', 'sharp')
        
        # Специальные случаи
        special_cases = {
            'Adobe XD': ['adobe-xd'],
            'C#': ['csharp', 'c#'],
            'C++': ['c++', 'cpp'],
            'CSS': ['css'],
            'GitHub Actions': ['github-actions'],
            'GitLab CI': ['gitlab-ci'],
            'Google Cloud': ['google-cloud'],
            'GraphQL': ['graphql'],
            'HTML': ['html'],
            'JavaScript': ['javascript', 'js'],
            'Material-UI': ['material-ui', 'mui'],
            'MATLAB': ['matlab'],
            'MobX': ['mobx'],
            'MongoDB': ['mongodb'],
            'MySQL': ['mysql'],
            'Node.js': ['nodejs', 'node'],
            'PHP': ['php'],
            'PostgreSQL': ['postgresql'],
            'REST API': ['rest-api', 'rest'],
            'SQL': ['sql'],
            'Tailwind CSS': ['tailwind-css', 'tailwind'],
            'TypeScript': ['typescript', 'ts'],
            'Vue.js': ['vuejs', 'vue'],
            'Vuex': ['vuex']
        }
        
        if topic_name in special_cases:
            return special_cases[topic_name]
        
        return [base_name] 