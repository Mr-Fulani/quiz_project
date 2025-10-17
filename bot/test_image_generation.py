#!/usr/bin/env python3
"""
Тестовый скрипт для проверки генерации изображений с кодом
Проверяет новую систему форматирования и извлечения кода из markdown
"""

import json
import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bot.services.image_service import (
    extract_code_from_markdown,
    smart_format_code,
    generate_console_image,
    get_lexer
)


def test_extract_code_from_markdown():
    """Тест извлечения кода из markdown блоков"""
    print("\n" + "=" * 80)
    print("ТЕСТ 1: Извлечение кода из markdown блоков")
    print("=" * 80)
    
    test_text = """Функция ниже должна вычислять факториал числа. В чём ошибка её реализации?

```python
def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 2)
```"""
    
    code, language = extract_code_from_markdown(test_text)
    print(f"\n✅ Извлеченный код:\n{code}")
    print(f"\n✅ Определенный язык: {language}")
    
    return code, language


def test_smart_format_code():
    """Тест умного форматирования кода"""
    print("\n" + "=" * 80)
    print("ТЕСТ 2: Умное форматирование кода")
    print("=" * 80)
    
    # Тест Python
    bad_python_code = """def hello(  ):
print("Hello")
if True:
x=1
return x"""
    
    print(f"\n📝 Исходный код (плохо отформатированный):\n{bad_python_code}")
    formatted = smart_format_code(bad_python_code, 'python')
    print(f"\n✅ Отформатированный код:\n{formatted}")
    
    # Тест JavaScript
    bad_js_code = """function test(){
if(true){
console.log("test")
}
return 42
}"""
    
    print(f"\n📝 Исходный JavaScript код:\n{bad_js_code}")
    formatted_js = smart_format_code(bad_js_code, 'javascript')
    print(f"\n✅ Отформатированный JavaScript:\n{formatted_js}")


def test_image_generation_from_json():
    """Тест генерации изображений из JSON файлов"""
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Генерация изображений из JSON")
    print("=" * 80)
    
    # Путь к JSON файлам
    json_files = [
        'uploads/python.json',
        'uploads/javascript.json',
        'uploads/java.json'
    ]
    
    output_dir = Path('bot/test_output')
    output_dir.mkdir(exist_ok=True)
    
    for json_file in json_files:
        json_path = project_root / json_file
        
        if not json_path.exists():
            print(f"⚠️ Файл {json_file} не найден, пропускаем")
            continue
        
        print(f"\n📄 Обработка файла: {json_file}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Берем первую задачу для теста
        if not data.get('tasks'):
            print(f"⚠️ В файле {json_file} нет задач")
            continue
        
        task = data['tasks'][0]
        
        # Берем русский перевод или первый доступный
        translations = task.get('translations', [])
        translation = next((t for t in translations if t['language'] == 'ru'), translations[0] if translations else None)
        
        if not translation:
            print(f"⚠️ Нет переводов для задачи")
            continue
        
        question = translation['question']
        print(f"\n📝 Вопрос:\n{question[:200]}...")
        
        # Извлекаем код и язык
        code, language = extract_code_from_markdown(question)
        print(f"\n✅ Извлечен код на языке: {language}")
        print(f"Размер кода: {len(code)} символов")
        
        # Генерируем изображение
        logo_path = project_root / 'bot' / 'assets' / 'logo.png'
        logo = str(logo_path) if logo_path.exists() else None
        
        try:
            image = generate_console_image(code, language, logo)
            
            # Сохраняем изображение
            output_filename = f"test_{task['topic'].lower()}_{language}.png"
            output_path = output_dir / output_filename
            image.save(str(output_path), format='PNG')
            
            print(f"✅ Изображение сохранено: {output_path}")
            print(f"   Размер изображения: {image.size}")
        
        except Exception as e:
            print(f"❌ Ошибка при генерации изображения: {e}")
            import traceback
            traceback.print_exc()


def test_lexer_aliases():
    """Тест поддержки alias для языков"""
    print("\n" + "=" * 80)
    print("ТЕСТ 4: Поддержка alias языков")
    print("=" * 80)
    
    test_aliases = [
        ('py', 'python'),
        ('js', 'javascript'),
        ('ts', 'typescript'),
        ('golang', 'go'),
        ('react', 'jsx'),
        ('cs', 'csharp'),
    ]
    
    for alias, expected in test_aliases:
        try:
            lexer = get_lexer(alias)
            print(f"✅ {alias:10} -> {lexer.name}")
        except Exception as e:
            print(f"❌ {alias:10} -> Ошибка: {e}")


def main():
    """Главная функция для запуска всех тестов"""
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК ТЕСТОВ ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ С КОДОМ")
    print("=" * 80)
    
    try:
        # Тест 1: Извлечение кода
        test_extract_code_from_markdown()
        
        # Тест 2: Форматирование
        test_smart_format_code()
        
        # Тест 3: Генерация изображений
        test_image_generation_from_json()
        
        # Тест 4: Alias языков
        test_lexer_aliases()
        
        print("\n" + "=" * 80)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("=" * 80)
        print("\n💡 Проверьте сгенерированные изображения в директории: bot/test_output/")
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

