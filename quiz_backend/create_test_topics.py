#!/usr/bin/env python
"""
Скрипт для создания тестовых тем в Django.
Запуск: python manage.py shell < create_test_topics.py
"""

import os
import sys
import django

# Настройка Django окружения
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from topics.models import Topic, Subtopic

def create_test_topics():
    """Создает тестовые темы для мини-приложения"""
    
    # Очищаем существующие темы
    Topic.objects.all().delete()
    
    topics_data = [
        {
            'name': 'Python',
            'description': 'Тестирование знаний языка программирования Python',
            'icon': '/static/images/icons/python-icon.png',
            'subtopics': ['Основы Python', 'ООП в Python', 'Структуры данных', 'Модули и пакеты']
        },
        {
            'name': 'JavaScript',
            'description': 'Основы языка программирования JavaScript',
            'icon': '/static/images/icons/js-icon.png',
            'subtopics': ['Основы JS', 'DOM манипуляции', 'Асинхронность', 'ES6+']
        },
        {
            'name': 'React',
            'description': 'Библиотека React для создания пользовательских интерфейсов',
            'icon': '/static/images/icons/react-icon.png',
            'subtopics': ['Компоненты', 'Хуки', 'State Management', 'Роутинг']
        },
        {
            'name': 'SQL',
            'description': 'Язык структурированных запросов для работы с базами данных',
            'icon': '/static/images/icons/sql-icon.png',
            'subtopics': ['Основы SQL', 'Соединения', 'Функции', 'Индексы']
        },
        {
            'name': 'Django',
            'description': 'Web-фреймворк для Python',
            'icon': '/static/images/icons/django-icon.png',
            'subtopics': ['Модели', 'Представления', 'Шаблоны', 'Формы']
        },
        {
            'name': 'Git',
            'description': 'Система контроля версий',
            'icon': '/static/images/icons/git-icon.png',
            'subtopics': ['Основы Git', 'Ветвление', 'Слияние', 'Удаленные репозитории']
        },
        {
            'name': 'Docker',
            'description': 'Платформа для контейнеризации приложений',
            'icon': '/static/images/icons/docker-icon.png',
            'subtopics': ['Контейнеры', 'Образы', 'Docker Compose', 'Volumes']
        },
        {
            'name': 'Linux',
            'description': 'Операционная система и администрирование',
            'icon': '/static/images/icons/linux-icon.png',
            'subtopics': ['Командная строка', 'Файловая система', 'Процессы', 'Сети']
        },
        {
            'name': 'HTML/CSS',
            'description': 'Языки разметки и стилизации веб-страниц',
            'icon': '/static/images/icons/html-icon.png',
            'subtopics': ['Семантика HTML', 'CSS Flexbox', 'CSS Grid', 'Responsive Design']
        },
        {
            'name': 'Node.js',
            'description': 'Серверная JavaScript среда выполнения',
            'icon': '/static/images/icons/nodejs-icon.png',
            'subtopics': ['Основы Node.js', 'Express.js', 'NPM', 'Асинхронность']
        },
        {
            'name': 'Алгоритмы',
            'description': 'Алгоритмы и структуры данных',
            'icon': '/static/images/icons/algorithm-icon.png',
            'subtopics': ['Сортировка', 'Поиск', 'Графы', 'Динамическое программирование']
        },
        {
            'name': 'Machine Learning',
            'description': 'Машинное обучение и анализ данных',
            'icon': '/static/images/icons/ml-icon.png',
            'subtopics': ['Основы ML', 'Scikit-learn', 'Pandas', 'Визуализация данных']
        }
    ]
    
    created_topics = []
    
    for topic_data in topics_data:
        # Создаем тему
        topic = Topic.objects.create(
            name=topic_data['name'],
            description=topic_data['description'],
            icon=topic_data['icon']
        )
        
        # Создаем подтемы
        for subtopic_name in topic_data['subtopics']:
            Subtopic.objects.create(
                name=subtopic_name,
                topic=topic
            )
        
        created_topics.append(topic)
        print(f"✓ Создана тема: {topic.name} с {len(topic_data['subtopics'])} подтемами")
    
    print(f"\n🎉 Успешно создано {len(created_topics)} тем!")
    return created_topics

if __name__ == '__main__':
    create_test_topics() 