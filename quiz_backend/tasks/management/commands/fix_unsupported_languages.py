"""
Management command для исправления языков задач в продакшене.

Проверяет и исправляет задачи с неподдерживаемыми языками сайта (tr, ar, etc.)
на английский язык по умолчанию.

Использование:
    python manage.py fix_unsupported_languages --dry-run  # только анализ
    python manage.py fix_unsupported_languages --fix      # анализ + исправление
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from tasks.models import TaskTranslation
from collections import defaultdict


class Command(BaseCommand):
    help = 'Исправляет языки задач с неподдерживаемых на английский'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только анализ без изменений',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Выполнить исправление языков',
        )

    def get_supported_languages(self):
        """Получить список поддерживаемых языков из настроек Django."""
        return [lang_code for lang_code, _ in getattr(settings, 'LANGUAGES', [('en', 'English'), ('ru', 'Russian')])]

    def analyze_unsupported_languages(self):
        """
        Анализирует задачи с неподдерживаемыми языками.

        Returns:
            list: Список переводов с неподдерживаемыми языками
        """
        supported_languages = self.get_supported_languages()
        self.stdout.write(f"Поддерживаемые языки сайта: {supported_languages}")

        # Получаем все переводы задач
        all_translations = TaskTranslation.objects.all()
        total_translations = all_translations.count()

        # Группируем по языкам
        language_stats = defaultdict(int)
        unsupported_translations = []

        for translation in all_translations:
            language = translation.language.lower()
            language_stats[language] += 1

            if language not in supported_languages:
                unsupported_translations.append(translation)

        self.stdout.write(f"\nВсего переводов задач: {total_translations}")
        self.stdout.write("\nСтатистика по языкам:")

        for lang, count in sorted(language_stats.items()):
            status = "✅" if lang in supported_languages else "❌"
            self.stdout.write(f"  {status} {lang}: {count} переводов")

        unsupported_count = len(unsupported_translations)
        if unsupported_count == 0:
            self.stdout.write(self.style.SUCCESS("\n🎉 Все переводы задач используют поддерживаемые языки!"))
            return []

        self.stdout.write(self.style.WARNING(f"\n⚠️  Найдено {unsupported_count} переводов с неподдерживаемыми языками:"))
        unsupported_by_lang = defaultdict(list)
        for translation in unsupported_translations:
            unsupported_by_lang[translation.language].append(translation)

        for lang, translations in unsupported_by_lang.items():
            self.stdout.write(f"  - {lang}: {len(translations)} переводов")

        return unsupported_translations

    def fix_unsupported_languages(self, unsupported_translations, dry_run=True):
        """
        Исправляет неподдерживаемые языки на английский.

        Args:
            unsupported_translations: Список переводов с неподдерживаемыми языками
            dry_run: Если True, только показать что будет изменено
        """
        if not unsupported_translations:
            self.stdout.write("Нет переводов для исправления.")
            return

        mode = 'ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР' if dry_run else 'ИСПОЛНЕНИЕ'
        self.stdout.write(self.style.WARNING(f"\n{mode} исправлений:"))
        self.stdout.write(f"Будет исправлено {len(unsupported_translations)} переводов")

        # Группируем по языкам для статистики
        by_language = defaultdict(list)
        for translation in unsupported_translations:
            by_language[translation.language].append(translation)

        for lang, translations in by_language.items():
            self.stdout.write(f"  {lang} → en: {len(translations)} переводов")

        if dry_run:
            self.stdout.write("\nЭто предварительный просмотр. Реальные изменения не внесены.")
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
                    self.stdout.write(f"Обработано {updated_count}/{len(unsupported_translations)} переводов...")

            self.stdout.write(self.style.SUCCESS(f"\n✅ Исправлено {updated_count} переводов задач"))
            self.stdout.write("Все неподдерживаемые языки изменены на 'en'")

        except Exception as e:
            raise CommandError(f"Ошибка при обновлении переводов: {e}")

    def handle(self, *args, **options):
        """Главная функция команды."""
        self.stdout.write(self.style.SUCCESS("🔍 Анализ задач с неподдерживаемыми языками\n"))
        self.stdout.write("=" * 50)

        # Определяем режим работы
        dry_run = options['dry_run'] or not options['fix']

        # Шаг 1: Анализ
        unsupported_translations = self.analyze_unsupported_languages()

        if not unsupported_translations:
            return

        # Шаг 2: Действия в зависимости от режима
        self.stdout.write("\n" + "=" * 50)
        self.fix_unsupported_languages(unsupported_translations, dry_run=dry_run)

        if dry_run and not options['fix']:
            self.stdout.write(self.style.WARNING(f"\n💡 Для выполнения исправлений запустите команду с флагом --fix"))
            self.stdout.write(self.style.WARNING(f"   python manage.py fix_unsupported_languages --fix"))
            return

        if not dry_run:
            self.stdout.write("\n" + "=" * 50)
            self.stdout.write(self.style.SUCCESS("🎉 Исправление языков завершено!"))
            self.stdout.write("\nРекомендации:")
            self.stdout.write("- Проверьте работу сайта с английскими URL")
            self.stdout.write("- Убедитесь, что английские переводы корректны")
            self.stdout.write("- При необходимости пересоздайте кэш")