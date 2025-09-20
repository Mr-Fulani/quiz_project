#!/usr/bin/env python3
"""
Безопасная очистка зависимостей с учетом косвенных зависимостей
"""

import os
import re
from pathlib import Path

def get_safe_to_remove_dependencies():
    """Возвращает список зависимостей, которые можно безопасно удалить"""
    
    # Зависимости, которые точно можно удалить (тестовые, отладочные, неиспользуемые)
    safe_to_remove = {
        'bot': [
            # Тестовые зависимости
            'pytest', 'pytest-asyncio', 'pytest-cov', 'coverage',
            
            # Django зависимости (bot не использует Django напрямую)
            'Django', 'django-cors-headers', 'django-debug-toolbar', 
            'django-filter', 'django-imagekit', 'django-silk', 
            'django-tinymce', 'djangorestframework', 'drf-yasg',
            'social-auth-app-django',
            
            # Flask зависимости (не используется в bot)
            'Flask',
            
            # AWS зависимости (не используются)
            'aioboto3', 'aiobotocore', 'boto3', 'botocore', 's3transfer',
            
            # Другие неиспользуемые
            'aiofiles', 'aioitertools', 'aioresponses', 'beautifulsoup4',
            'duckduckgo_search', 'lxml', 'requests', 'stripe', 'validators',
            
            # DRF зависимости
            'coreapi', 'coreschema', 'uritemplate',
            
            # Неиспользуемые системные
            'alembic', 'asyncpg', 'psycopg2-binary', 'python-dotenv',
        ],
        
        'mini_app': [
            # Тестовые зависимости
            'pytest-cov',
            
            # Неиспользуемые в mini_app
            'aiofiles', 'duckduckgo_search', 'jinja2', 'python-multipart',
            'telegram-webapp-auth', 'uvicorn',  # uvicorn может быть нужен для запуска
        ],
        
        'quiz_backend': [
            # Тестовые зависимости
            'pytest', 'pytest-asyncio', 'pytest-cov', 'coverage',
            
            # AWS зависимости (не используются)
            'aioboto3', 'aiobotocore', 'boto3', 'botocore', 's3transfer',
            
            # Неиспользуемые
            'aiofiles', 'aioitertools', 'aioresponses', 'beautifulsoup4',
            'duckduckgo_search', 'lxml', 'requests', 'validators',
            
            # Telegram зависимости (не используются в backend)
            'telegram-webapp-auth',
            
            # DRF зависимости (не используются напрямую)
            'coreapi', 'coreschema', 'uritemplate',
            
            # Неиспользуемые системные
            'alembic', 'asyncpg', 'psycopg2-binary', 'python-dotenv',
        ]
    }
    
    return safe_to_remove

def analyze_safe_removals():
    """Анализирует безопасные для удаления зависимости"""
    
    safe_to_remove = get_safe_to_remove_dependencies()
    
    total_removed = 0
    
    for component, dependencies in safe_to_remove.items():
        print(f"\n{'='*60}")
        print(f"Компонент: {component}")
        print(f"{'='*60}")
        
        requirements_file = f"{component}/requirements.txt"
        if not os.path.exists(requirements_file):
            print(f"Файл {requirements_file} не найден")
            continue
            
        # Читаем текущие зависимости
        current_deps = []
        with open(requirements_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    current_deps.append(line)
        
        # Находим зависимости для удаления
        to_remove = []
        remaining_deps = []
        
        for dep in current_deps:
            package_name = re.split(r'[>=<]', dep)[0].strip().lower()
            if package_name in dependencies:
                to_remove.append(dep)
            else:
                remaining_deps.append(dep)
        
        print(f"📊 Статистика:")
        print(f"   Текущих зависимостей: {len(current_deps)}")
        print(f"   Можно удалить: {len(to_remove)}")
        print(f"   Останется: {len(remaining_deps)}")
        
        if to_remove:
            print(f"\n🗑️  Зависимости для удаления:")
            for dep in sorted(to_remove):
                print(f"   - {dep}")
        
        total_removed += len(to_remove)
    
    print(f"\n{'='*60}")
    print(f"📈 ИТОГО: Можно удалить {total_removed} зависимостей")
    print(f"{'='*60}")
    
    return safe_to_remove

def create_cleaned_requirements():
    """Создает очищенные файлы requirements.txt"""
    
    safe_to_remove = get_safe_to_remove_dependencies()
    
    for component, dependencies in safe_to_remove.items():
        requirements_file = f"{component}/requirements.txt"
        if not os.path.exists(requirements_file):
            continue
            
        print(f"\n🧹 Очистка {requirements_file}...")
        
        # Читаем текущие зависимости
        current_deps = []
        with open(requirements_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    current_deps.append(line)
        
        # Фильтруем зависимости
        cleaned_deps = []
        removed_count = 0
        
        for dep in current_deps:
            package_name = re.split(r'[>=<]', dep)[0].strip().lower()
            if package_name not in dependencies:
                cleaned_deps.append(dep)
            else:
                removed_count += 1
        
        # Создаем backup
        backup_file = f"{requirements_file}.backup"
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(current_deps))
        
        # Записываем очищенный файл
        with open(requirements_file, 'w', encoding='utf-8') as f:
            for dep in sorted(cleaned_deps):
                f.write(f"{dep}\n")
        
        print(f"   ✅ Удалено {removed_count} зависимостей")
        print(f"   📁 Создан backup: {backup_file}")

if __name__ == "__main__":
    print("🔍 Анализ неиспользуемых зависимостей...")
    analyze_safe_removals()
    
    response = input("\n❓ Создать очищенные файлы requirements.txt? (y/N): ")
    if response.lower() in ['y', 'yes', 'да']:
        create_cleaned_requirements()
        print("\n✅ Очистка завершена! Проверьте изменения перед коммитом.")
    else:
        print("\n❌ Очистка отменена.")
