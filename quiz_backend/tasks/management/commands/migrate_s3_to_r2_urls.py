"""
Django management команда для миграции URL изображений с S3 на R2.
Заменяет домен в URL на новый R2 домен, сохраняя путь к файлу.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from urllib.parse import urlparse, urlunparse
import logging

from tasks.models import Task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Мигрирует URL изображений с S3 на R2, заменяя домен на новый'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Проверка без реальных изменений в базе данных',
        )
        parser.add_argument(
            '--old-domain',
            type=str,
            help='Старый домен S3 для замены (если не указан, будет определен автоматически)',
        )
        parser.add_argument(
            '--new-domain',
            type=str,
            help='Новый домен R2 (если не указан, будет использован из настроек)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        old_domain = options.get('old_domain')
        new_domain = options.get('new_domain')
        
        # Определяем новый домен из настроек если не указан
        if not new_domain:
            new_domain = getattr(settings, 'AWS_PUBLIC_MEDIA_DOMAIN', None)
            if not new_domain:
                self.stdout.write(
                    self.style.ERROR('❌ Новый домен R2 не настроен. Установите R2_PUBLIC_DOMAIN или используйте --new-domain')
                )
                return
        
        # Определяем старый домен если не указан
        if not old_domain:
            # Пытаемся определить из существующих URL в базе
            sample_task = Task.objects.filter(image_url__isnull=False).first()
            if sample_task and sample_task.image_url:
                parsed = urlparse(sample_task.image_url)
                old_domain = parsed.netloc
                self.stdout.write(f"📋 Автоматически определен старый домен: {old_domain}")
            else:
                self.stdout.write(
                    self.style.WARNING('⚠️ Не удалось автоматически определить старый домен. Используйте --old-domain')
                )
                return
        
        self.stdout.write(f"🔄 Начинаем миграцию URL:")
        self.stdout.write(f"   Старый домен: {old_domain}")
        self.stdout.write(f"   Новый домен: {new_domain}")
        if dry_run:
            self.stdout.write(self.style.WARNING("   Режим DRY-RUN: изменения не будут сохранены"))
        
        # Находим все задачи с image_url содержащим старый домен
        tasks = Task.objects.filter(image_url__icontains=old_domain)
        total_count = tasks.count()
        
        self.stdout.write(f"\n📊 Найдено задач для миграции: {total_count}")
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Нет задач для миграции"))
            return
        
        updated_count = 0
        error_count = 0
        
        for task in tasks:
            try:
                old_url = task.image_url
                parsed = urlparse(old_url)
                
                # Проверяем, что это действительно старый домен
                if parsed.netloc != old_domain:
                    continue
                
                # Заменяем домен
                new_url_parts = parsed._replace(netloc=new_domain)
                new_url = urlunparse(new_url_parts)
                
                if dry_run:
                    self.stdout.write(f"   [DRY-RUN] Задача {task.id}: {old_url} -> {new_url}")
                else:
                    task.image_url = new_url
                    task.save(update_fields=['image_url'])
                    logger.info(f"Мигрирован URL для задачи {task.id}: {old_url} -> {new_url}")
                
                updated_count += 1
                
                if updated_count % 100 == 0:
                    self.stdout.write(f"   Обработано: {updated_count}/{total_count}")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Ошибка при миграции URL для задачи {task.id}: {e}")
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Ошибка для задачи {task.id}: {e}")
                )
        
        self.stdout.write(f"\n📈 Результаты миграции:")
        self.stdout.write(f"   Всего обработано: {total_count}")
        self.stdout.write(f"   Успешно обновлено: {updated_count}")
        self.stdout.write(f"   Ошибок: {error_count}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️ Это был DRY-RUN. Для реальной миграции запустите без --dry-run"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Миграция завершена успешно!"))

