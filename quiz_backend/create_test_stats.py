#!/usr/bin/env python
"""
Скрипт для создания тестовой статистики пользователя zloy
"""
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from tasks.models import Task, TaskStatistics
from topics.models import Topic
from datetime import datetime, timedelta

User = get_user_model()

def create_test_stats():
    try:
        # Находим пользователя zloy
        user = User.objects.get(username='zloy')
        print(f'User found: {user.username}')
        
        # Получаем задачи для статистики
        tasks = Task.objects.filter(published=True)[:25]
        print(f'Found {tasks.count()} tasks')
        
        created_count = 0
        for i, task in enumerate(tasks):
            success = i % 4 != 3  # 3 из 4 задач успешные (75% успешность)
            attempts = (i % 3) + 1
            
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
                created_count += 1
                print(f'Created stats for task {task.id} (topic: {task.topic.name}) - success: {success}, attempts: {attempts}')
        
        print(f'Total created: {created_count} statistics records')
        
        # Показываем итоговую статистику
        total_stats = TaskStatistics.objects.filter(user=user)
        successful_stats = total_stats.filter(successful=True)
        print(f'Total user stats: {total_stats.count()}')
        print(f'Successful: {successful_stats.count()}')
        print(f'Success rate: {(successful_stats.count() / total_stats.count() * 100):.1f}%' if total_stats.count() > 0 else 'No stats')
        
    except User.DoesNotExist:
        print('User zloy not found')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    create_test_stats() 