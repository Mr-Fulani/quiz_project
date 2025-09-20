#!/usr/bin/env python3
"""
Скрипт для анализа неиспользуемых зависимостей в проекте
"""

import os
import re
import subprocess
from pathlib import Path

def get_imports_from_file(file_path):
    """Извлекает все импорты из Python файла"""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Находим все import и from statements
        import_patterns = [
            r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import',
        ]
        
        for line in content.split('\n'):
            line = line.strip()
            for pattern in import_patterns:
                match = re.match(pattern, line)
                if match:
                    imports.add(match.group(1))
                    
    except Exception as e:
        print(f"Ошибка при чтении файла {file_path}: {e}")
        
    return imports

def get_all_imports_in_directory(directory):
    """Получает все импорты в директории"""
    all_imports = set()
    
    for root, dirs, files in os.walk(directory):
        # Пропускаем __pycache__ и .git
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.venv', 'venv']]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                imports = get_imports_from_file(file_path)
                all_imports.update(imports)
                
    return all_imports

def get_requirements_from_file(requirements_file):
    """Извлекает список зависимостей из requirements.txt"""
    requirements = set()
    
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Извлекаем имя пакета (до знака =, <, >)
                    package_name = re.split(r'[>=<]', line)[0].strip().lower()
                    requirements.add(package_name)
                    
    except Exception as e:
        print(f"Ошибка при чтении файла {requirements_file}: {e}")
        
    return requirements

def normalize_package_name(package_name):
    """Нормализует имя пакета для сравнения"""
    # Заменяем дефисы на подчеркивания
    normalized = package_name.replace('-', '_').lower()
    
    # Специальные случаи
    mapping = {
        'pil': 'pillow',
        'psycopg2_binary': 'psycopg2',
        'django_cors_headers': 'corsheaders',
        'django_debug_toolbar': 'debug_toolbar',
        'django_filter': 'django_filters',
        'django_imagekit': 'imagekit',
        'django_silk': 'silk',
        'django_tinymce': 'tinymce',
        'djangorestframework': 'rest_framework',
        'drf_yasg': 'drf_yasg',
        'social_auth_app_django': 'social_auth',
        'telegram_webapp_auth': 'telegram_webapp',
        'duckduckgo_search': 'duckduckgo',
    }
    
    return mapping.get(normalized, normalized)

def analyze_dependencies():
    """Основная функция анализа"""
    
    components = [
        ('bot', 'bot/requirements.txt'),
        ('mini_app', 'mini_app/requirements.txt'),
        ('quiz_backend', 'quiz_backend/requirements.txt'),
    ]
    
    for component_name, requirements_file in components:
        print(f"\n{'='*60}")
        print(f"Анализ компонента: {component_name}")
        print(f"{'='*60}")
        
        if not os.path.exists(requirements_file):
            print(f"Файл {requirements_file} не найден")
            continue
            
        if not os.path.exists(component_name):
            print(f"Директория {component_name} не найдена")
            continue
        
        # Получаем импорты и зависимости
        imports = get_all_imports_in_directory(component_name)
        requirements = get_requirements_from_file(requirements_file)
        
        # Нормализуем импорты
        normalized_imports = set()
        for imp in imports:
            normalized_imports.add(normalize_package_name(imp))
            
        # Нормализуем зависимости
        normalized_requirements = set()
        for req in requirements:
            normalized_requirements.add(normalize_package_name(req))
        
        # Находим неиспользуемые зависимости
        unused = normalized_requirements - normalized_imports
        
        print(f"\n📊 Статистика:")
        print(f"   Всего импортов: {len(imports)}")
        print(f"   Всего зависимостей: {len(requirements)}")
        print(f"   Неиспользуемых: {len(unused)}")
        
        if unused:
            print(f"\n❌ Неиспользуемые зависимости:")
            for dep in sorted(unused):
                # Найдем оригинальное имя пакета
                original_name = None
                for req in requirements:
                    if normalize_package_name(req) == dep:
                        original_name = req
                        break
                if original_name:
                    print(f"   - {original_name}")
        else:
            print(f"\n✅ Все зависимости используются!")

if __name__ == "__main__":
    analyze_dependencies()
