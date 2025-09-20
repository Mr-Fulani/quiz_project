#!/usr/bin/env python3
"""
Очистка неиспользуемых зависимостей
"""

import os
import re

def get_safe_to_remove_dependencies():
    """Возвращает список зависимостей, которые можно безопасно удалить"""
    
    return {
        'bot': [
            # Тестовые зависимости
            'pytest', 'pytest-asyncio', 'pytest-cov', 'coverage',
            
            # Django зависимости (bot не использует Django напрямую)
            'django', 'django-cors-headers', 'django-debug-toolbar', 
            'django-filter', 'django-imagekit', 'django-silk', 
            'django-tinymce', 'djangorestframework', 'drf-yasg',
            'social-auth-app-django',
            
            # Flask зависимости (не используется в bot)
            'flask',
            
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

def clean_requirements_file(component):
    """Очищает файл requirements.txt для компонента"""
    
    safe_to_remove = get_safe_to_remove_dependencies()
    dependencies = safe_to_remove.get(component, [])
    
    requirements_file = f"{component}/requirements.txt"
    if not os.path.exists(requirements_file):
        print(f"Файл {requirements_file} не найден")
        return
        
    print(f"🧹 Очистка {requirements_file}...")
    
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

def main():
    """Основная функция"""
    print("🧹 Очистка неиспользуемых зависимостей...")
    
    components = ['bot', 'mini_app', 'quiz_backend']
    
    for component in components:
        clean_requirements_file(component)
    
    print("\n✅ Очистка завершена!")

if __name__ == "__main__":
    main()
