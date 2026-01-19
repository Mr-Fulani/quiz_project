#!/usr/bin/env python
"""
Скрипт для исправления ТОЛЬКО языков в существующих переводах.
Не удаляет данные, только обновляет language поля.
"""

import os
import sys
import subprocess
import django

# Настройка Django
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'quiz_backend'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    django.setup()
    from tasks.models import TaskTranslation
    print("✅ Django настроен")
except Exception as e:
    print(f"❌ Ошибка Django: {e}")
    sys.exit(1)

def fix_languages_from_backup():
    """Исправляет языки на основе данных из бэкапа"""

    # Параметры подключения к БД
    db_params = {
        'host': os.environ.get('DB_HOST', 'postgres_db_local_prod'),
        'port': os.environ.get('DB_PORT', '5432'),
        'user': os.environ.get('DB_USER', 'admin_fulani_quiz'),
        'password': os.environ.get('DB_PASSWORD', '4748699'),
        'database': os.environ.get('DB_NAME', 'fulani_quiz_db')
    }

    # Установка переменной окружения для пароля
    env = os.environ.copy()
    env['PGPASSWORD'] = db_params['password']

    # SQL запрос для обновления языков из бэкапа
    sql_query = """
    -- Обновляем языки из бэкапа данных
    UPDATE task_translations
    SET language = backup_data.language
    FROM (
        -- Здесь вставляем данные из бэкапа
        VALUES
        -- Данные будут вставлены скриптом
    ) AS backup_data(id, language, question, answers, correct_answer, explanation, publish_date, task_id, long_explanation)
    WHERE task_translations.id = backup_data.id;
    """

    print("🔧 Исправление языков из бэкапа...")
    print("   Обновляем существующие записи, не удаляя данные")

    # Получаем данные из бэкапа
    backup_file = find_backup_file()
    if not backup_file:
        return False

    # Извлекаем данные task_translations из бэкапа
    with open(backup_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Ищем блок COPY для task_translations
    lines = content.split('\n')
    in_task_translations = False
    task_data_lines = []

    for line in lines:
        if 'COPY task_translations' in line:
            in_task_translations = True
            continue
        elif in_task_translations and line.strip() == '\\.':
            break
        elif in_task_translations:
            task_data_lines.append(line)

    if not task_data_lines:
        print("❌ Не найдены данные task_translations в бэкапе")
        return False

    print(f"   Найдено {len(task_data_lines)} строк данных для обновления")

    # Создаем временный SQL файл
    temp_sql_file = '/tmp/fix_languages.sql'

    with open(temp_sql_file, 'w', encoding='utf-8') as f:
        f.write("-- Обновление языков в task_translations\n")
        f.write("BEGIN;\n\n")

        for line in task_data_lines:
            if line.strip():
                # Парсим строку: id<TAB>language<TAB>...
                parts = line.split('\t')
                if len(parts) >= 2:
                    translation_id = parts[0].strip()
                    language = parts[1].strip()

                    # Создаем UPDATE запрос
                    f.write(f"UPDATE task_translations SET language = '{language}' WHERE id = {translation_id};\n")

        f.write("\nCOMMIT;\n")

    print(f"   Создан SQL файл: {temp_sql_file}")

    # Выполняем SQL файл
    sql_cmd = [
        'psql',
        '-h', db_params['host'],
        '-p', db_params['port'],
        '-U', db_params['user'],
        '-d', db_params['database'],
        '-f', temp_sql_file
    ]

    print(f"   Выполнение обновления...")
    result = subprocess.run(sql_cmd, env=env, capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ Языки успешно обновлены!")

        # Проверяем результат
        tr_count = TaskTranslation.objects.filter(language='tr').count()
        ar_count = TaskTranslation.objects.filter(language='ar').count()
        en_count = TaskTranslation.objects.filter(language='en').count()
        ru_count = TaskTranslation.objects.filter(language='ru').count()

        print("\n📊 Результат обновления:")
        print(f"   🇹🇷 TR записей: {tr_count}")
        print(f"   🇸🇦 AR записей: {ar_count}")
        print(f"   🇷🇺 RU записей: {ru_count}")
        print(f"   🇬🇧 EN записей: {en_count}")

        # Очищаем временный файл
        os.remove(temp_sql_file)

        return True
    else:
        print(f"❌ Ошибка обновления: {result.stderr}")
        return False

def find_backup_file():
    """Найти файл резервной копии"""
    # Сначала ищем в текущей директории (в контейнере)
    backup_dir = os.getcwd()
    backup_files = [f for f in os.listdir(backup_dir) if f.startswith('backup_before_lang_fix_') and f.endswith('.sql')]

    # Если не нашли, ищем в /host_backup (если смонтировано)
    if not backup_files:
        host_backup_dir = '/host_backup'
        if os.path.exists(host_backup_dir):
            backup_files = [f for f in os.listdir(host_backup_dir) if f.startswith('backup_before_lang_fix_') and f.endswith('.sql')]
            if backup_files:
                backup_dir = host_backup_dir

    if not backup_files:
        print("❌ Файл резервной копии не найден")
        print("   Ищем файлы вида: backup_before_lang_fix_*.sql")
        return None

    # Берем самый свежий
    backup_files.sort(reverse=True)
    backup_file = os.path.join(backup_dir, backup_files[0])
    print(f"📁 Найден бэкап: {backup_file}")
    return backup_file

def main():
    print("🔧 Исправление языков переводов из бэкапа\n")

    if fix_languages_from_backup():
        print("\n✅ Языки исправлены! Проверь в админке.")
    else:
        print("\n❌ Ошибка исправления!")

if __name__ == '__main__':
    main()