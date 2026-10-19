"""
Привязывает записи без тенанта (tenant=NULL, созданные до мультитенантности или ботом
до перехода на ботов тенантов) к указанному тенанту.

Пока у записи нет тенанта, бот и интеграции считают её общей для всех тенантов.
После привязки изоляция становится строгой.

    python manage.py assign_tenant_to_legacy_rows --slug it-dev            # только показать
    python manage.py assign_tenant_to_legacy_rows --slug it-dev --apply    # записать
    python manage.py assign_tenant_to_legacy_rows --slug it-dev --apply --models accounts.TelegramUser tasks.Task
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from tenants.models import Tenant


def tenant_scoped_models():
    """Модели с прямым FK tenant на Tenant."""
    models = []
    for model in apps.get_models():
        field = next((f for f in model._meta.get_fields() if getattr(f, 'name', None) == 'tenant'), None)
        if field is not None and getattr(field, 'related_model', None) is Tenant and field.null:
            models.append(model)
    return sorted(models, key=lambda m: m._meta.label)


class Command(BaseCommand):
    help = 'Привязать записи без тенанта (tenant=NULL) к тенанту. Без --apply только показывает.'

    def add_arguments(self, parser):
        parser.add_argument('--slug', required=True, help='slug тенанта, которому отдать записи')
        parser.add_argument('--apply', action='store_true', help='записать изменения (иначе — только отчёт)')
        parser.add_argument('--models', nargs='*', help='ограничить моделями app_label.Model')

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options['slug'])
        except Tenant.DoesNotExist:
            raise CommandError(f"Тенант {options['slug']!r} не найден")

        models = tenant_scoped_models()
        if options['models']:
            wanted = set(options['models'])
            models = [m for m in models if m._meta.label in wanted]
            missing = wanted - {m._meta.label for m in models}
            if missing:
                raise CommandError(f"Нет моделей с tenant: {', '.join(sorted(missing))}")

        total = 0
        for model in models:
            queryset = model._default_manager.filter(tenant__isnull=True)
            count = queryset.count()
            if not count:
                continue
            total += count
            if not options['apply']:
                self.stdout.write(f"{model._meta.label}: {count}")
                continue
            try:
                with transaction.atomic():
                    queryset.update(tenant=tenant)
                self.stdout.write(self.style.SUCCESS(f"{model._meta.label}: {count} → {tenant.slug}"))
            except IntegrityError as exc:
                # Например, у тенанта уже есть запись с тем же telegram_id — разберите вручную
                self.stdout.write(self.style.ERROR(f"{model._meta.label}: пропущено, конфликт уникальности ({exc})"))

        verb = 'привязано' if options['apply'] else 'будет привязано (запустите с --apply)'
        self.stdout.write(f"Всего записей без тенанта: {total}, {verb}")
