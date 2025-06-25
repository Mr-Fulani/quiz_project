from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tasks.models import Task, TaskStatistics, Topic
from datetime import datetime, timedelta

User = get_user_model()

class Command(BaseCommand):
    help = 'Создает тестовую статистику для пользователя zloy'

    def handle(self, *args, **options):
        try:
            # Находим пользователя zloy
            user = User.objects.get(username='zloy')
            self.stdout.write(f'Найден пользователь: {user.username}')
            
            # Получаем все темы
            topics = Topic.objects.all()
            self.stdout.write(f'Найдено тем: {topics.count()}')
            
            stats_created = 0
            
            # Создаем статистику для разных тем
            for topic in topics[:5]:  # Берем первые 5 тем
                tasks = Task.objects.filter(topic=topic, published=True)[:3]  # По 3 задачи из каждой темы
                
                for i, task in enumerate(tasks):
                    # Создаем статистику с разным уровнем успешности
                    success = i < 2  # Первые 2 задачи успешные, 3-я неуспешная
                    attempts = i + 1
                    
                    stats, created = TaskStatistics.objects.get_or_create(
                        user=user,
                        task=task,
                        defaults={
                            'attempts': attempts,
                            'successful': success,
                            'last_attempt_date': datetime.now() - timedelta(days=i)
                        }
                    )
                    
                    if created:
                        stats_created += 1
                        self.stdout.write(f'Создана статистика для {task.id} - {topic.name} (успешно: {success})')
            
            self.stdout.write(
                self.style.SUCCESS(f'Успешно создано {stats_created} записей статистики')
            )
            
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Пользователь zloy не найден')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка: {e}')
            ) 