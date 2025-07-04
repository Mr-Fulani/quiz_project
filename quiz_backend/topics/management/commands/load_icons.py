import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from topics.models import Topic


class Command(BaseCommand):
    help = 'Загружает иконки из папки static/blog/images/icons в БД для тем'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно обновить все иконки, даже если они уже установлены',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Пропустить темы, у которых уже есть иконки (кроме default)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет изменено, но не применять изменения',
        )

    def handle(self, *args, **options):
        self.stdout.write("🎨 Начинаю загрузку иконок для тем...")
        
        # Путь к папке с иконками (используем STATIC_ROOT)
        icons_dir = os.path.join(settings.STATIC_ROOT, 'blog', 'images', 'icons')
        
        if not os.path.exists(icons_dir):
            self.stdout.write(
                self.style.ERROR(f"❌ Папка с иконками не найдена: {icons_dir}")
            )
            return
        
        # Получаем список файлов иконок
        icon_files = []
        for filename in os.listdir(icons_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.gif')):
                icon_files.append(filename)
        
        if not icon_files:
            self.stdout.write(
                self.style.WARNING("⚠️  В папке с иконками не найдено изображений")
            )
            return
        
        self.stdout.write(f"📁 Найдено {len(icon_files)} файлов иконок")
        
        # Получаем все темы из БД
        topics = Topic.objects.all()
        if not topics.exists():
            self.stdout.write(
                self.style.ERROR("❌ В базе данных нет тем")
            )
            return
        
        self.stdout.write(f"📚 Найдено {topics.count()} тем в БД")
        
        # Словарь для сопоставления имен файлов с темами
        icon_mapping = {}
        
        for icon_file in icon_files:
            # Извлекаем название темы из имени файла
            # Примеры: python-icon.png -> Python, java-icon.png -> Java
            base_name = os.path.splitext(icon_file)[0]  # убираем расширение
            
            # Убираем суффиксы типа -icon, -logo и т.д.
            theme_name = re.sub(r'-icon$|-logo$|-symbol$', '', base_name, flags=re.IGNORECASE)
            
            # Преобразуем в правильный формат (первая буква заглавная)
            theme_name = theme_name.title()
            
            # Специальные случаи
            if theme_name.lower() == 'cpp':
                theme_name = 'C++'
            elif theme_name.lower() == 'csharp':
                theme_name = 'C#'
            elif theme_name.lower() == 'asp.net':
                theme_name = 'ASP.NET'
            elif theme_name.lower() == 'api.testing':
                theme_name = 'API Testing'
            elif theme_name.lower() == 'ai.ethics':
                theme_name = 'AI Ethics'
            elif theme_name.lower() == 'big.data':
                theme_name = 'Big Data'
            elif theme_name.lower() == 'burp.suite':
                theme_name = 'Burp Suite'
            
            icon_mapping[theme_name] = icon_file
        
        self.stdout.write("\n🔍 Сопоставление иконок с темами:")
        for theme_name, icon_file in icon_mapping.items():
            self.stdout.write(f"  {theme_name} → {icon_file}")
        
        # Обновляем иконки в БД
        updated_count = 0
        skipped_count = 0
        not_found_count = 0
        
        for topic in topics:
            if topic.name in icon_mapping:
                icon_file = icon_mapping[topic.name]
                icon_path = f'/static/blog/images/icons/{icon_file}'
                
                # Проверяем, нужно ли обновлять
                default_icon = '/static/blog/images/icons/default-icon.png'
                skip_existing = options.get('skip-existing', False)
                should_skip = (
                    (topic.icon == icon_path and not options['force']) or
                    (skip_existing and topic.icon != default_icon)
                )
                
                if should_skip:
                    self.stdout.write(f"  ⏭️  Пропускаю {topic.name} (иконка уже установлена)")
                    skipped_count += 1
                    continue
                
                if options['dry_run']:
                    self.stdout.write(f"  🔄 Будет обновлено: {topic.name} → {icon_path}")
                else:
                    topic.icon = icon_path
                    topic.save()
                    self.stdout.write(f"  ✅ Обновлено: {topic.name} → {icon_path}")
                
                updated_count += 1
            else:
                self.stdout.write(f"  ❌ Не найдена иконка для темы: {topic.name}")
                not_found_count += 1
        
        # Статистика
        self.stdout.write(f"\n📊 Итоговая статистика:")
        self.stdout.write(f"  - Всего тем: {topics.count()}")
        self.stdout.write(f"  - Обновлено: {updated_count}")
        self.stdout.write(f"  - Пропущено: {skipped_count}")
        self.stdout.write(f"  - Не найдено иконок: {not_found_count}")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("\n⚠️  Режим dry-run: изменения не применены"))
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ Загрузка иконок завершена!"))
        
        # Показываем темы без иконок
        if not_found_count > 0:
            self.stdout.write(f"\n📝 Темы без иконок:")
            for topic in topics:
                if topic.name not in icon_mapping:
                    self.stdout.write(f"  - {topic.name}")
            
            self.stdout.write(f"\n💡 Добавьте соответствующие файлы иконок в папку:")
            self.stdout.write(f"   {icons_dir}")
            self.stdout.write(f"   Формат имен: {topic.name.lower()}-icon.png") 