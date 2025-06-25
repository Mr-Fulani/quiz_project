from django.core.management.base import BaseCommand
from topics.models import Topic, Subtopic
import random

class Command(BaseCommand):
    help = 'Создает тестовые подтемы для существующих тем'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Начинаю создание тестовых подтем...")
        
        # Данные подтем для каждой темы
        subtopics_data = {
            'Python': [
                'Синтаксис',
                'Структуры данных', 
                'ООП',
                'Библиотеки'
            ],
            'JavaScript': [
                'DOM',
                'Async/Await',
                'ES6+',
                'Frameworks'
            ],
            'React': [
                'Компоненты',
                'Hooks',
                'State Management',
                'Router'
            ],
            'SQL': [
                'SELECT запросы',
                'JOIN операции',
                'Индексы',
                'Процедуры'
            ],
            'Django': [
                'Модели и ORM',
                'Views и URLs',
                'Templates',
                'Forms'
            ],
            'Docker': [
                'Контейнеры',
                'Docker Compose',
                'Volumes',
                'Networks'
            ],
            'Git': [
                'Основные команды',
                'Ветки',
                'Merge и Rebase',
                'Remote репозитории'
            ],
            'Golang': [
                'Goroutines',
                'Channels',
                'Interfaces',
                'Packages'
            ]
        }
        
        # Проверяем, есть ли темы в базе
        topics_count = Topic.objects.count()
        if topics_count == 0:
            self.stdout.write(self.style.ERROR("❌ В базе данных нет тем. Сначала создайте темы."))
            return
        
        self.stdout.write(f"📊 Найдено тем в базе: {topics_count}")
        
        created_count = 0
        
        for topic_name, subtopic_names in subtopics_data.items():
            try:
                topic = Topic.objects.get(name=topic_name)
                self.stdout.write(f"\n📚 Обрабатываю тему: {topic_name}")
                
                for subtopic_name in subtopic_names:
                    subtopic, created = Subtopic.objects.get_or_create(
                        name=subtopic_name,
                        topic=topic
                    )
                    
                    if created:
                        self.stdout.write(f"  ✅ Создана подтема: {subtopic_name}")
                        created_count += 1
                    else:
                        self.stdout.write(f"  ⚠️  Подтема уже существует: {subtopic_name}")
                        
            except Topic.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"❌ Тема '{topic_name}' не найдена в базе данных"))
                continue
        
        # Показываем статистику
        total_subtopics = Subtopic.objects.count()
        
        self.stdout.write(f"\n📈 Итоговая статистика:")
        self.stdout.write(f"  - Всего тем: {Topic.objects.count()}")
        self.stdout.write(f"  - Всего подтем: {total_subtopics}")
        self.stdout.write(f"  - Создано новых подтем: {created_count}")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Готово!")) 