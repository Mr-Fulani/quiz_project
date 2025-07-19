import os
import requests
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from topics.models import Topic
from duckduckgo_search import DDGS

class Command(BaseCommand):
    help = 'Создает все темы, скачивает иконки и настраивает их'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Начинаю полную настройку тем...")
        
        # Список всех тем
        all_topics = [
            'Python', 'JavaScript', 'React', 'SQL', 'Django', 'Docker', 'Git', 'Golang',
            'Node.js', 'Vue.js', 'Angular', 'TypeScript', 'PHP', 'Java', 'C++', 'C#',
            'Ruby', 'Go', 'Rust', 'Swift', 'Kotlin', 'Scala', 'R', 'MATLAB', 'Julia',
            'HTML', 'CSS', 'Sass', 'Less', 'Bootstrap', 'Tailwind CSS', 'Material-UI',
            'Redux', 'Vuex', 'MobX', 'GraphQL', 'REST API', 'MongoDB', 'PostgreSQL',
            'MySQL', 'Redis', 'Elasticsearch', 'AWS', 'Azure', 'Google Cloud', 'Heroku',
            'Kubernetes', 'Jenkins', 'GitLab CI', 'GitHub Actions', 'Jest', 'Cypress',
            'Selenium', 'Postman', 'Insomnia', 'Figma', 'Adobe XD', 'Sketch'
        ]
        
        # Папка для сохранения иконок
        icons_dir = os.path.join(settings.BASE_DIR, 'static', 'blog', 'images', 'icons')
        os.makedirs(icons_dir, exist_ok=True)
        
        # Создаем темы и скачиваем иконки
        created_topics = 0
        downloaded_icons = 0
        
        with DDGS() as ddgs:
            for i, topic_name in enumerate(all_topics):
                # Создаем тему если её нет
                topic, created = Topic.objects.get_or_create(
                    name=topic_name,
                    defaults={
                        'description': f'Тесты по теме {topic_name}',
                        'icon': '/static/blog/images/icons/default-icon.png'
                    }
                )
                
                if created:
                    self.stdout.write(f"✅ Создана тема: {topic_name}")
                    created_topics += 1
                
                # Проверяем, есть ли уже иконка
                icon_filename = f"{topic_name.lower().replace(' ', '-').replace('.', '')}-icon.png"
                icon_path = os.path.join(icons_dir, icon_filename)
                
                if os.path.exists(icon_path):
                    self.stdout.write(f"  ⚠️  Иконка уже существует: {icon_filename}")
                    continue
                
                # Скачиваем иконку
                query = f"{topic_name} icon filetype:png"
                self.stdout.write(f"  🔎 Поиск иконки для: {topic_name}")
                
                try:
                    # Добавляем задержку между запросами
                    if i > 0:
                        time.sleep(2)  # 2 секунды между запросами
                    
                    results = []
                    for r in ddgs.images(query, safesearch='off', size='Medium', color='color', license_image='Share'):
                        results.append(r)
                        if len(results) >= 1:
                            break
                    
                    if results:
                        image_url = results[0]['image']
                        response = requests.get(image_url, stream=True, timeout=10)
                        response.raise_for_status()
                        
                        with open(icon_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        # Обновляем путь к иконке в БД
                        topic.icon = f'/static/blog/images/icons/{icon_filename}'
                        topic.save()
                        
                        self.stdout.write(f"  ✅ Скачана иконка: {icon_filename}")
                        downloaded_icons += 1
                    else:
                        self.stdout.write(f"  ❌ Не найдена иконка для: {topic_name}")
                        
                except Exception as e:
                    error_msg = str(e)
                    if "Ratelimit" in error_msg or "202" in error_msg:
                        self.stdout.write(f"  ⚠️  Rate limit для {topic_name}, пропускаю...")
                        time.sleep(5)  # Увеличиваем задержку при rate limit
                    else:
                        self.stdout.write(f"  ❌ Ошибка скачивания для {topic_name}: {e}")
        
        self.stdout.write(f"\n📊 Итоговая статистика:")
        self.stdout.write(f"  - Создано тем: {created_topics}")
        self.stdout.write(f"  - Скачано иконок: {downloaded_icons}")
        self.stdout.write(f"  - Всего тем в БД: {Topic.objects.count()}")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Полная настройка тем завершена!")) 