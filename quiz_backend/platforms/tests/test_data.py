from accounts.models import CustomUser
from tasks.models import Task, TaskStatistics
from topics.models import Topic
from django.utils import timezone
from datetime import timedelta
import random

def generate_test_data():
    # Очищаем существующие тестовые данные
    print("Cleaning old data...")
    TaskStatistics.objects.all().delete()
    Task.objects.all().delete()
    Topic.objects.all().delete()
    CustomUser.objects.filter(username__startswith='test_user_').delete()

    print("Generating new data...")
    # Создаем темы
    topics = []
    topic_names = ['Python', 'JavaScript', 'SQL', 'Algorithms', 'Machine Learning']
    for name in topic_names:
        topic, _ = Topic.objects.get_or_create(
            name=name,
            description=f'Description for {name}'
        )
        topics.append(topic)

    # Создаем задачи
    tasks = []
    difficulties = ['easy', 'medium', 'hard']
    for topic in topics:
        for i in range(5):
            task = Task.objects.create(
                topic=topic,
                difficulty=random.choice(difficulties),
                published=True,
                create_date=timezone.now() - timedelta(days=random.randint(0, 60))
            )
            tasks.append(task)

    # Создаем пользователей
    users = []
    for i in range(10):
        user, _ = CustomUser.objects.get_or_create(
            username=f'test_user_{i}',
            email=f'test{i}@example.com'
        )
        users.append(user)

    # Создаем уникальные комбинации пользователь-задача для статистики
    user_task_pairs = set()
    while len(user_task_pairs) < 200:
        user = random.choice(users)
        task = random.choice(tasks)
        pair = (user.id, task.id)
        if pair not in user_task_pairs:
            user_task_pairs.add(pair)
            days_ago = random.randint(0, 30)
            attempts = random.randint(1, 10)
            
            TaskStatistics.objects.create(
                user=user,
                task=task,
                attempts=attempts,
                successful=random.choice([True, False]),
                last_attempt_date=timezone.now() - timedelta(days=days_ago)
            )

    result = {
        'topics': len(topics),
        'tasks': len(tasks),
        'users': len(users),
        'statistics': TaskStatistics.objects.count()
    }
    print("Data generation completed!")
    return result

if __name__ == '__main__':
    result = generate_test_data()
    print(result)