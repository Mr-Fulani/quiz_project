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

    # Если все еще не нашли, показываем возможные места
    if not backup_files:
        print("❌ Файл резервной копии не найден")
        print("   Ищем файлы вида: backup_before_lang_fix_*.sql")
        print("   Проверьте директории:")
        print("   - Текущая директория")
        print("   - /host_backup (если смонтировано)")
        print("   - Корень проекта на хосте")
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
    try:
        input("   Нажмите Enter для продолжения или Ctrl+C для отмены...")
    except KeyboardInterrupt:
        print("\n❌ Операция отменена")
        return False

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
        # Проверяем наличие psql
        print("   Проверка доступности psql...")
        psql_check = subprocess.run(['which', 'psql'], capture_output=True, text=True)
        if psql_check.returncode != 0:
            print("❌ psql не найден. Убедитесь что скрипт запускается в контейнере с PostgreSQL клиентом")
            return False

        # Установка переменной окружения для пароля
        env = os.environ.copy()
        env['PGPASSWORD'] = db_params['password']

        # Сначала очистим таблицу
        print("   Очистка текущих данных task_translations...")
        truncate_cmd = [
            'psql',
            '-h', db_params['host'],
            '-p', db_params['port'],
            '-U', db_params['user'],
            '-d', db_params['database'],
            '-c', 'TRUNCATE TABLE tasks_tasktranslation RESTART IDENTITY CASCADE;'
        ]

        result = subprocess.run(truncate_cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Ошибка очистки: {result.stderr}")
            return False

        # Теперь восстановим данные через psql с бэкап файлом
        print("   Восстановление данных task_translations...")

        # Используем psql для выполнения бэкап файла
        restore_cmd = [
            'psql',
            '-h', db_params['host'],
            '-p', db_params['port'],
            '-U', db_params['user'],
            '-d', db_params['database'],
            '-f', backup_file
        ]

        print(f"   Выполнение: psql -h {db_params['host']} -U {db_params['user']} -d {db_params['database']} -f {backup_file}")
        result = subprocess.run(restore_cmd, env=env, capture_output=True, text=True)

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