"""
Management command для диагностики проблем с MessageAttachment в админке.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from blog.models import MessageAttachment, Message
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Диагностика проблем с MessageAttachment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Исправить найденные проблемы',
        )

    def handle(self, *args, **options):
        self.stdout.write('🔍 Начинаем диагностику MessageAttachment...')

        # Проверяем общее количество
        total_count = MessageAttachment.objects.count()
        self.stdout.write(f'📊 Всего вложений: {total_count}')

        if total_count == 0:
            self.stdout.write('ℹ️  Нет вложений для проверки')
            return

        # Проверяем вложения без сообщений
        orphaned_count = MessageAttachment.objects.filter(message__isnull=True).count()
        self.stdout.write(f'⚠️  Вложений без сообщений: {orphaned_count}')

        # Проверяем вложения с пустыми именами файлов
        empty_filename_count = MessageAttachment.objects.filter(filename='').count()
        self.stdout.write(f'⚠️  Вложений с пустым именем файла: {empty_filename_count}')

        # Проверяем вложения без файлов
        no_file_count = MessageAttachment.objects.filter(file='').count()
        self.stdout.write(f'⚠️  Вложений без файла: {no_file_count}')

        # Проверяем каждое вложение на проблемы
        problematic_attachments = []
        self.stdout.write('🔎 Проверяем каждое вложение...')

        for attachment in MessageAttachment.objects.all():
            issues = []

            # Проверяем __str__ метод
            try:
                str(attachment)
            except Exception as e:
                issues.append(f'__str__ error: {e}')

            # Проверяем message связь
            if not attachment.message:
                issues.append('No message relation')
            else:
                # Проверяем, существует ли сообщение
                try:
                    message_exists = Message.objects.filter(id=attachment.message.id).exists()
                    if not message_exists:
                        issues.append('Message does not exist')
                except Exception as e:
                    issues.append(f'Message check error: {e}')

            # Проверяем файл
            if attachment.file:
                try:
                    # Проверяем размер файла
                    if hasattr(attachment.file, 'size'):
                        size = attachment.file.size
                        if size is None or size < 0:
                            issues.append(f'Invalid file size: {size}')
                except Exception as e:
                    issues.append(f'File size error: {e}')

                # Проверяем URL
                try:
                    if hasattr(attachment.file, 'url'):
                        url = attachment.file.url
                        if not url:
                            issues.append('Empty file URL')
                    else:
                        issues.append('No file URL attribute')
                except Exception as e:
                    issues.append(f'File URL error: {e}')
            else:
                issues.append('No file field')

            if issues:
                problematic_attachments.append((attachment, issues))

        self.stdout.write(f'🚨 Найдено проблемных вложений: {len(problematic_attachments)}')

        for attachment, issues in problematic_attachments[:10]:  # Показываем первые 10
            self.stdout.write(f'  ID {attachment.id}: {issues}')

        if len(problematic_attachments) > 10:
            self.stdout.write(f'  ... и еще {len(problematic_attachments) - 10} проблемных вложений')

        # Исправление проблем
        if options['fix']:
            self.stdout.write('🔧 Начинаем исправление...')

            fixed_count = 0
            deleted_count = 0

            for attachment, issues in problematic_attachments:
                try:
                    with transaction.atomic():
                        should_delete = False

                        # Если сообщение не существует, удаляем вложение
                        if 'Message does not exist' in str(issues) or 'No message relation' in str(issues):
                            should_delete = True
                            self.stdout.write(f'🗑️  Удаляем вложение ID {attachment.id} (сообщение не существует)')

                        # Если файл поврежден, тоже удаляем
                        if 'No file field' in str(issues) or 'Empty file URL' in str(issues):
                            should_delete = True
                            self.stdout.write(f'🗑️  Удаляем вложение ID {attachment.id} (поврежденный файл)')

                        if should_delete:
                            attachment.delete()
                            deleted_count += 1
                        else:
                            fixed_count += 1

                except Exception as e:
                    self.stdout.write(f'❌ Ошибка при обработке вложения ID {attachment.id}: {e}')

            self.stdout.write(f'✅ Исправлено: {fixed_count}, Удалено: {deleted_count}')

        self.stdout.write('✅ Диагностика завершена')