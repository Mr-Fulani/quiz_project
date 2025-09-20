import os
from django.core.management.base import BaseCommand
from django.conf import settings
from topics.models import Topic

class Command(BaseCommand):
    help = 'Загружает иконки для тем (аналог fix_icon_mapping для обратной совместимости)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно обновить все иконки, даже если они уже установлены',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Пропустить темы с уже установленными иконками',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет изменено, но не применять изменения',
        )

    def handle(self, *args, **options):
        self.stdout.write("🎨 Начинаю загрузку иконок для тем...")
        
        # Папка с иконками
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
        
        # Получаем все темы
        topics = Topic.objects.all()
        self.stdout.write(f"📚 Найдено {topics.count()} тем")
        
        updated_count = 0
        skipped_count = 0
        not_found_count = 0
        
        for topic in topics:
            # Логика пропуска
            if options['skip_existing'] and topic.icon:
                self.stdout.write(f"  ⏭️  Пропущена тема с иконкой: {topic.name}")
                skipped_count += 1
                continue
            elif not options['force'] and topic.icon:
                continue
                
            # Формируем возможные имена файлов для темы
            possible_names = self.get_possible_icon_names(topic.name)
            
            # Ищем подходящий файл иконки с приоритетом точного совпадения
            found_icon = None
            
            # Сначала ищем точное совпадение
            for icon_file in icon_files:
                icon_name_lower = icon_file.lower()
                for possible_name in possible_names:
                    expected_pattern = f"{possible_name.lower()}-icon"
                    if icon_name_lower == expected_pattern or icon_name_lower.startswith(expected_pattern):
                        found_icon = icon_file
                        break
                if found_icon:
                    break
            
            # Если точного совпадения нет, ищем частичное
            if not found_icon:
                for icon_file in icon_files:
                    icon_name_lower = icon_file.lower()
                    for possible_name in possible_names:
                        if possible_name.lower() in icon_name_lower:
                            found_icon = icon_file
                            break
                    if found_icon:
                        break
            
            if found_icon:
                new_icon_path = f'/static/blog/images/icons/{found_icon}'
                
                if options['dry_run']:
                    self.stdout.write(f"  🔍 [DRY RUN] Обновить: {topic.name} → {found_icon}")
                    updated_count += 1
                else:
                    # Обновляем путь к иконке в БД
                    topic.icon = new_icon_path
                    topic.save()
                    self.stdout.write(f"  ✅ Обновлено: {topic.name} → {found_icon}")
                    updated_count += 1
            else:
                self.stdout.write(f"  ❌ Не найдена иконка для: {topic.name}")
                not_found_count += 1
        
        self.stdout.write(f"\n📊 Итоговая статистика:")
        self.stdout.write(f"  - Всего тем: {topics.count()}")
        self.stdout.write(f"  - Обновлено: {updated_count}")
        self.stdout.write(f"  - Пропущено: {skipped_count}")
        self.stdout.write(f"  - Не найдено иконок: {not_found_count}")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("\n🔍 Режим dry-run: изменения не применены"))
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ Загрузка иконок завершена!"))

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
