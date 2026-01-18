#!/usr/bin/env python
"""
Скрипт для исправления языков задач в продакшене.

Проверяет и исправляет задачи с неподдерживаемыми языками сайта (tr, ar, etc.)
на английский язык по умолчанию.

Использование:
    python manage.py shell < fix_unsupported_languages.py
    или
    python fix_unsupported_languages.py (если DJANGO_SETTINGS_MODULE настроен)
"""

import os
import sys
import django
from collections import defaultdict

# Настройка Django - пробуем разные варианты
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    # Добавляем путь к проекту
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    sys.path.insert(0, os.path.join(project_root, 'quiz_backend'))

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    django.setup()
    print("✅ Django настроен успешно")
except Exception as e:
    print(f"❌ Ошибка настройки Django: {e}")
    print("Убедитесь что:")
    print("1. Вы находитесь в корне проекта")
    print("2. Активировано виртуальное окружение")
    print("3. Установлены все зависимости")
    sys.exit(1)

try:
    from tasks.models import TaskTranslation
    from django.conf import settings
    print("✅ Модели импортированы успешно")
except ImportError as e:
    print(f"❌ Ошибка импорта моделей: {e}")
    sys.exit(1)


def get_supported_languages():
    """Получить список поддерживаемых языков из настроек Django."""
    return [lang_code for lang_code, _ in getattr(settings, 'LANGUAGES', [('en', 'English'), ('ru', 'Russian')])]


def analyze_unsupported_languages():
    """
    Анализирует задачи с неподдерживаемыми языками.

    Returns:
        dict: Статистика по неподдерживаемым языкам
    """
    supported_languages = get_supported_languages()
    print(f"Поддерживаемые языки сайта: {supported_languages}")

    try:
        # Получаем все переводы задач
        all_translations = TaskTranslation.objects.all()
        total_translations = all_translations.count()
    except Exception as e:
        print(f"❌ Ошибка доступа к базе данных: {e}")
        return None

    # Группируем по языкам
    language_stats = defaultdict(int)
    unsupported_translations = []

    for translation in all_translations:
        language = translation.language.lower()
        language_stats[language] += 1

        if language not in supported_languages:
            unsupported_translations.append(translation)

    print(f"\nВсего переводов задач: {total_translations}")
    print("\nСтатистика по языкам:")
    for lang, count in sorted(language_stats.items()):
        status = "✅" if lang in supported_languages else "❌"
        print(f"  {status} {lang}: {count} переводов")

    unsupported_count = len(unsupported_translations)
    if unsupported_count == 0:
        print("\n🎉 Все переводы задач используют поддерживаемые языки!")
        return None

    print(f"\n⚠️  Найдено {unsupported_count} переводов с неподдерживаемыми языками:")
    unsupported_by_lang = defaultdict(list)
    for translation in unsupported_translations:
        unsupported_by_lang[translation.language].append(translation)

    for lang, translations in unsupported_by_lang.items():
        print(f"  - {lang}: {len(translations)} переводов")

    return unsupported_translations


def fix_unsupported_languages(unsupported_translations, dry_run=True):
    """
    Исправляет неподдерживаемые языки на английский.

    Args:
        unsupported_translations: Список переводов с неподдерживаемыми языками
        dry_run: Если True, только показать что будет изменено без реальных изменений
    """
    if not unsupported_translations:
        print("Нет переводов для исправления.")
        return

    mode = 'ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР' if dry_run else 'ИСПОЛНЕНИЕ'
    print(f"\n{mode} исправлений:")
    print(f"Будет исправлено {len(unsupported_translations)} переводов")

    # Группируем по языкам для статистики
    by_language = defaultdict(list)
    for translation in unsupported_translations:
        by_language[translation.language].append(translation)

    for lang, translations in by_language.items():
        print(f"  {lang} → en: {len(translations)} переводов")

    if dry_run:
        print("\nЭто предварительный просмотр. Реальные изменения не внесены.")
        return

    # Выполняем изменения
    updated_count = 0
    try:
        for translation in unsupported_translations:
            old_lang = translation.language
            translation.language = 'en'
            translation.save()
            updated_count += 1
            if updated_count % 100 == 0:
                print(f"Обработано {updated_count}/{len(unsupported_translations)} переводов...")

        print(f"\n✅ Исправлено {updated_count} переводов задач")
        print("Все неподдерживаемые языки изменены на 'en'")
    except Exception as e:
        print(f"❌ Ошибка при обновлении переводов: {e}")
        print(f"Обработано {updated_count} переводов перед ошибкой")


def main():
    """Главная функция скрипта."""
    print("🔍 Анализ задач с неподдерживаемыми языками\n")
    print("=" * 50)

    # Шаг 1: Анализ
    unsupported_translations = analyze_unsupported_languages()

    if not unsupported_translations:
        return

    # Шаг 2: Предварительный просмотр
    print("\n" + "=" * 50)
    fix_unsupported_languages(unsupported_translations, dry_run=True)

    # Шаг 3: Запрос подтверждения
    print("\n" + "=" * 50)
    try:
        response = input(f"\n⚠️  ВНИМАНИЕ: Будет изменено {len(unsupported_translations)} переводов задач.\n"
                        "Это действие нельзя отменить. Продолжить? (yes/no): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n❌ Операция отменена пользователем (EOF/KeyboardInterrupt).")
        return

    if response not in ['yes', 'y', 'да', 'д']:
        print("❌ Операция отменена пользователем.")
        return

    # Шаг 4: Выполнение изменений
    print("\n" + "=" * 50)
    fix_unsupported_languages(unsupported_translations, dry_run=False)

    print("\n" + "=" * 50)
    print("🎉 Исправление языков завершено!")
    print("\nРекомендации:")
    print("- Проверьте работу сайта с английскими URL")
    print("- Убедитесь, что английские переводы корректны")
    print("- При необходимости пересоздайте кэш")


if __name__ == '__main__':
    main()