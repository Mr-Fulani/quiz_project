from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.conf import settings

class Command(BaseCommand):
    help = 'Настраивает правильный домен для сайта в Sites framework'

    def handle(self, *args, **options):
        try:
            # Получаем или создаем Site с ID=1 (SITE_ID=1)
            site, created = Site.objects.get_or_create(
                id=1,
                defaults={
                    'domain': 'quiz-code.com',
                    'name': 'QuizHub - Programming Quizzes & Learning Platform'
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Создан новый сайт: {site.domain}')
                )
            else:
                # Обновляем существующий сайт, если нужно
                updated = False
                if site.domain != 'quiz-code.com':
                    site.domain = 'quiz-code.com'
                    updated = True
                
                if site.name != 'QuizHub - Programming Quizzes & Learning Platform':
                    site.name = 'QuizHub - Programming Quizzes & Learning Platform'
                    updated = True
                
                if updated:
                    site.save()
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Обновлен сайт: {site.domain}')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Сайт уже правильно настроен: {site.domain}')
                    )
            
            # Проверяем настройки
            self.stdout.write('\n📊 Текущие настройки:')
            self.stdout.write(f'   SITE_ID: {getattr(settings, "SITE_ID", "НЕ УСТАНОВЛЕН")}')
            self.stdout.write(f'   Домен: {site.domain}')
            self.stdout.write(f'   Название: {site.name}')
            
            # Информация о sitemap
            self.stdout.write('\n🗺️  Sitemap будет доступен по адресу:')
            self.stdout.write(f'   https://{site.domain}/sitemap.xml')
            
            # Информация о robots.txt
            self.stdout.write('\n🤖 Robots.txt:')
            self.stdout.write(f'   Основной сайт: https://{site.domain}/static/robots.txt')
            self.stdout.write(f'   Мини-приложение: https://mini.quiz-code.com/api/robots.txt')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка при настройке сайта: {e}')
            ) 