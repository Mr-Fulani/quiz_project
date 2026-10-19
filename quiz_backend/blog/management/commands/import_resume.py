"""
Management команда для импорта резюме из JSON-файла в БД.
Используйте: python manage.py import_resume resume.json --tenant <slug>

JSON — объект с полями модели Resume: name, contact_info_en/ru, email, websites,
summary_en/ru, skills, work_history, education, languages.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from blog.models import Resume
from tenants.models import Tenant

RESUME_FIELDS = (
    'name', 'contact_info_en', 'contact_info_ru', 'email', 'websites', 'summary_en', 'summary_ru',
    'skills', 'work_history', 'education', 'languages',
)


class Command(BaseCommand):
    help = 'Импортирует резюме из JSON-файла в БД'

    def add_arguments(self, parser):
        parser.add_argument('path', help='Путь к JSON-файлу с данными резюме')
        parser.add_argument('--tenant', required=True, help='Slug тенанта, которому принадлежит резюме')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(slug=options['tenant']).first()
        if tenant is None:
            raise CommandError(f"Тенант {options['tenant']!r} не найден")
        try:
            with open(options['path'], encoding='utf-8') as fh:
                data = json.load(fh)
        except (OSError, ValueError) as e:
            raise CommandError(f'Не удалось прочитать {options["path"]}: {e}')

        unknown = set(data) - set(RESUME_FIELDS)
        if unknown:
            raise CommandError(f'Неизвестные поля: {", ".join(sorted(unknown))}')
        if not data.get('name'):
            raise CommandError('Поле name обязательно')

        # Проверяем, есть ли уже активное резюме
        existing = Resume.objects.filter(tenant=tenant, is_active=True).first()
        if existing:
            self.stdout.write(
                self.style.WARNING(f'Активное резюме уже существует (ID: {existing.id})')
            )
            confirm = input('Хотите перезаписать его? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Импорт отменён'))
                return
            existing.delete()

        resume = Resume.objects.create(tenant=tenant, is_active=True, **data)

        self.stdout.write(
            self.style.SUCCESS(f'✓ Резюме успешно импортировано (ID: {resume.id})')
        )
        self.stdout.write(self.style.SUCCESS(f'  Имя: {resume.name}'))
        self.stdout.write(self.style.SUCCESS(f'  Навыков: {len(resume.skills)}'))
        self.stdout.write(self.style.SUCCESS(f'  Записей в Work History: {len(resume.work_history)}'))
        self.stdout.write(self.style.SUCCESS(f'  Записей в Education: {len(resume.education)}'))
        self.stdout.write(self.style.SUCCESS(f'  Языков: {len(resume.languages)}'))
