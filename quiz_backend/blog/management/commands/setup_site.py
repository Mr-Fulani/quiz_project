from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Записывает домен и название в Sites framework (SITE_ID). Домены тенантов задаются в админке.'

    def add_arguments(self, parser):
        parser.add_argument('domain', help='Домен без https, например example.com')
        parser.add_argument('--name', default='', help='Название сайта (по умолчанию — домен)')

    def handle(self, *args, **options):
        domain = options['domain'].strip().strip('/')
        name = options['name'] or domain
        site, created = Site.objects.update_or_create(
            id=settings.SITE_ID, defaults={'domain': domain, 'name': name},
        )
        action = 'Создан' if created else 'Обновлён'
        self.stdout.write(self.style.SUCCESS(f'✅ {action} сайт #{site.id}: {site.domain} ({site.name})'))
