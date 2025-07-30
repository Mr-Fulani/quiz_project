from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tasks.models import Task, TaskStatistics
from topics.models import Topic, Subtopic
import random
from platforms.models import Group

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates test data for the application'

    def handle(self, *args, **kwargs):
        # В начале функции handle получаем веб-платформу
        web_platform = Group.objects.get(location_type='web')

        # Создаем тестовых пользователей
        users = []
        for i in range(5):
            user = User.objects.create_user(
                username=f'test_user_{i}',
                email=f'test{i}@example.com',
                password='testpass123',
                first_name=f'User{i}',
                last_name=f'Test'
            )
            users.append(user)
            self.stdout.write(f'Created user: {user.username}')

        # Создаем темы
        topics = []
        for topic_name in ['Python', 'JavaScript', 'Java', 'SQL', 'Git']:
            topic = Topic.objects.create(
                name=topic_name,
                description=f'Description for {topic_name}'
            )
            topics.append(topic)
            self.stdout.write(f'Created topic: {topic.name}')

            # Создаем подтемы для каждой темы
            for j in range(3):
                subtopic = Subtopic.objects.create(
                    name=f'{topic_name} Subtopic {j}',
                    topic=topic
                )
                self.stdout.write(f'Created subtopic: {subtopic.name}')

        # Создаем задачи
        difficulties = ['easy', 'medium', 'hard']
        tasks = []
        for topic in topics:
            for _ in range(5):  # 5 задач для каждой темы
                task = Task.objects.create(
                    topic=topic,
                    subtopic=random.choice(topic.subtopics.all()),
                    difficulty=random.choice(difficulties),
                    published=True,
                    group=web_platform  # Добавили это
                )
                tasks.append(task)
                self.stdout.write(f'Created task: Task {task.id}')

        # Создаем статистику
        for user in users:
            for task in random.sample(tasks, k=random.randint(5, 15)):  # От 5 до 15 случайных задач для каждого пользователя
                TaskStatistics.objects.create(
                    user=user,
                    task=task,
                    attempts=random.randint(1, 5),
                    successful=random.choice([True, False]),
                )
                self.stdout.write(f'Created statistics for user {user.username} and task {task.id}')

        self.stdout.write(self.style.SUCCESS('Successfully created test data'))

        # Получаем или создаем веб-платформу
        web_platform, created = Group.objects.get_or_create(
            group_name='Website Platform',
            group_id=0,  # используем 0 как специальный ID для веб-платформы
            topic_id=0,  # или другое подходящее значение
            language='en',  # или другой язык по умолчанию
            location_type='web'
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('Successfully created web platform entry'))
        else:
            self.stdout.write(self.style.SUCCESS('Web platform entry already exists')) 