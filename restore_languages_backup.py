#!/usr/bin/env python
"""
Скрипт для восстановления языков из резервной копии.
Используется для отката изменений, сделанных fix_unsupported_languages.py
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

def find_backup_file():
    """Найти файл резервной копии"""
    backup_dir = project_root
    backup_files = [f for f in os.listdir(backup_dir) if f.startswith('backup_before_lang_fix_') and f.endswith('.sql')]

    if not backup_files:
        print("❌ Файл резервной копии не найден")
        return None

    # Берем самый свежий
    backup_files.sort(reverse=True)
    backup_file = os.path.join(backup_dir, backup_files[0])
    print(f"📁 Найден бэкап: {backup_file}")
    return backup_file

def restore_languages():
    """Восстановить языки из бэкапа - только таблицу task_translations"""
    backup_file = find_backup_file()
    if not backup_file:
        return False

    print("⚠️  ВНИМАНИЕ: Этот скрипт восстановит ТОЛЬКО таблицу task_translations")
    print("   Остальные таблицы останутся без изменений")
    input("   Нажмите Enter для продолжения или Ctrl+C для отмены...")

    # Параметры подключения к БД
    db_params = {
        'host': os.environ.get('DB_HOST', 'postgres_db_local_prod'),
        'port': os.environ.get('DB_PORT', '5432'),
        'user': os.environ.get('DB_USER', 'admin_fulani_quiz'),
        'password': os.environ.get('DB_PASSWORD', '4748699'),
        'database': os.environ.get('DB_NAME', 'fulani_quiz_db')
    }

    print(f"🔄 Восстановление таблицы task_translations...")
    print(f"   Файл: {backup_file}")
    print(f"   БД: {db_params['database']}")

    try:
        # Используем pg_restore или psql для восстановления только task_translations
        # Сначала получаем только данные таблицы task_translations из бэкапа

        # Команда для восстановления - используем docker exec
        docker_cmd = [
            'docker', 'exec', '-i', 'postgres_db_local_prod',
            'psql', '-U', db_params['user'], '-d', db_params['database']
        ]

        # Установка пароля
        env = os.environ.copy()
        env['PGPASSWORD'] = db_params['password']

        # Сначала очистим таблицу
        print("   Очистка текущих данных task_translations...")
        truncate_cmd = docker_cmd + ['-c', 'TRUNCATE TABLE tasks_tasktranslation RESTART IDENTITY;']
        result = subprocess.run(truncate_cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Ошибка очистки: {result.stderr}")
            return False

        # Теперь восстановим из бэкапа только task_translations
        print("   Восстановление данных task_translations...")
        with open(backup_file, 'r', encoding='utf-8', errors='ignore') as f:
            backup_content = f.read()

        # Ищем только INSERT для task_translations
        lines = backup_content.split('\n')
        task_translation_inserts = []
        capture = False

        for line in lines:
            if 'COPY tasks_tasktranslation' in line:
                capture = True
                task_translation_inserts.append(line)
            elif capture and line.strip() == '\\.':
                capture = False
                task_translation_inserts.append(line)
                break
            elif capture:
                task_translation_inserts.append(line)

        if not task_translation_inserts:
            print("❌ Не найдены данные task_translations в бэкапе")
            return False

        # Выполняем восстановление
        insert_data = '\n'.join(task_translation_inserts)
        restore_cmd = docker_cmd + ['-c', insert_data]

        result = subprocess.run(restore_cmd, env=env, capture_output=True, text=True, input=insert_data)

        if result.returncode == 0:
            print("✅ Восстановление выполнено успешно")

            # Проверяем результат
            tr_count = TaskTranslation.objects.filter(language='tr').count()
            ar_count = TaskTranslation.objects.filter(language='ar').count()
            en_count = TaskTranslation.objects.filter(language='en').count()
            ru_count = TaskTranslation.objects.filter(language='ru').count()

            print("\n📊 Результат восстановления:")
            print(f"   TR записей: {tr_count}")
            print(f"   AR записей: {ar_count}")
            print(f"   RU записей: {ru_count}")
            print(f"   EN записей: {en_count}")

            return True
        else:
            print(f"❌ Ошибка восстановления: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Исключение: {e}")
        return False

def main():
    print("🔄 Восстановление языков задач из резервной копии\n")

    if restore_languages():
        print("\n✅ Восстановление завершено!")
        print("🔍 Теперь исправьте логику формирования URL, а не базу данных!")
    else:
        print("\n❌ Восстановление не удалось!")
        print("💡 Попробуйте восстановить вручную:")
        print("   psql -U [user] -d [db] < backup_file.sql")

if __name__ == '__main__':
    main()