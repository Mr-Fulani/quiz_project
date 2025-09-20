import os
from django.core.management.base import BaseCommand
from django.conf import settings
from topics.models import Topic

class Command(BaseCommand):
    help = 'Исправляет сопоставление иконок с темами'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно обновить все иконки, даже если они уже установлены',
        )

    def handle(self, *args, **options):
        self.stdout.write("🔧 Исправляю сопоставление иконок с темами...")
        
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
        not_found_count = 0
        
        for topic in topics:
            # Пропускаем темы с уже установленными иконками, если не используется --force
            if not options['force'] and topic.icon:
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
                # Обновляем путь к иконке в БД
                topic.icon = f'/static/blog/images/icons/{found_icon}'
                topic.save()
                self.stdout.write(f"  ✅ {topic.name} → {found_icon}")
                updated_count += 1
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