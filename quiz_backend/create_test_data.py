import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone

# from quiz_backend.accounts.models import CustomUser
# from quiz_backend.tasks.models import Task, TaskStatistics
# from quiz_backend.topics.models import Topic


from tasks.models import Task, TaskStatistics
from accounts.models import CustomUser
from topics.models import Topic

def create_test_data():
    print("Начинаем создание тестовых данных...")
    
    # Создаем тестовую тему
    topic = Topic.objects.create(
        name='Test Topic',
        description='Test Description'
    )
    print(f"Создана тема: {topic.name}")

    # Создаем тестовую задачу
    task = Task.objects.create(
        topic=topic,
        difficulty='medium',
        published=True
    )
    print(f"Создана задача с ID: {task.id}")

    # Создаем 5 пользователей с разной статистикой
    users_data = [
        {
            'username': 'test_user1',
            'attempts': 5,
            'successful': True,
        },
        {
            'username': 'test_user2',
            'attempts': 10,
            'successful': False,
        },
        {
            'username': 'test_user3',
            'attempts': 3,
            'successful': True,
        },
        {
            'username': 'test_user4',
            'attempts': 7,
            'successful': False,
        },
        {
            'username': 'test_user5',
            'attempts': 1,
            'successful': True,
        }
    ]

    for user_data in users_data:
        try:
            # Создаем пользователя с паролем
            user = CustomUser.objects.create_user(
                username=user_data['username'],
                password='testpass123'
            )
            
            # Создаем статистику для пользователя
            stats = TaskStatistics.objects.create(
                user=user,
                task=task,
                attempts=user_data['attempts'],
                successful=user_data['successful'],
                last_attempt_date=timezone.now()
            )
            print(f"Создан пользователь {user.username} со статистикой: попыток - {stats.attempts}, успешно - {stats.successful}")
        except Exception as e:
            print(f"Ошибка при создании пользователя {user_data['username']}: {str(e)}")

if __name__ == '__main__':
    create_test_data() 