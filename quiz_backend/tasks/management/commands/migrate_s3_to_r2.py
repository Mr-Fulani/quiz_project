"""
Django management команда для миграции файлов из S3 в R2.
Копирует все объекты из S3 бакета в R2 бакет, сохраняя структуру директорий.
"""
import os
import boto3
from botocore.exceptions import ClientError
from django.core.management.base import BaseCommand
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Мигрирует файлы из S3 бакета в R2 бакет'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Проверка без реальной миграции файлов',
        )
        parser.add_argument(
            '--prefix',
            type=str,
            default='',
            help='Префикс для фильтрации объектов (например: images/)',
        )
        parser.add_argument(
            '--target-env',
            type=str,
            choices=['prod', 'dev'],
            default=None,
            help='Целевое окружение для миграции (prod или dev). По умолчанию определяется из DEBUG',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Ограничить количество файлов для миграции (для тестирования)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        prefix = options.get('prefix', '')
        limit = options.get('limit')
        target_env = options.get('target_env')
        
        # Проверяем настройки S3 (источник)
        s3_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        s3_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        s3_bucket = os.getenv('S3_BUCKET_NAME')
        s3_region = os.getenv('S3_REGION', 'us-east-1')
        
        # Проверяем настройки R2 (назначение)
        use_r2 = getattr(settings, 'USE_R2_STORAGE', False)
        if not use_r2:
            self.stdout.write(
                self.style.ERROR('❌ USE_R2_STORAGE не включен. Включите R2 в настройках перед миграцией.')
            )
            return
        
        r2_account_id = os.getenv('R2_ACCOUNT_ID')
        r2_access_key = os.getenv('R2_ACCESS_KEY_ID')
        r2_secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
        r2_bucket = os.getenv('R2_BUCKET_NAME')
        r2_endpoint = f'https://{r2_account_id}.r2.cloudflarestorage.com' if r2_account_id else None
        
        # Проверка наличия всех необходимых настроек
        missing = []
        if not s3_access_key or not s3_secret_key or not s3_bucket:
            missing.append('S3 credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME)')
        if not r2_access_key or not r2_secret_key or not r2_bucket or not r2_endpoint:
            missing.append('R2 credentials (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME)')
        
        if missing:
            self.stdout.write(
                self.style.ERROR(f'❌ Отсутствуют необходимые настройки: {", ".join(missing)}')
            )
            return
        
        # Определяем целевое окружение
        if not target_env:
            target_env = 'prod' if not settings.DEBUG else 'dev'
        
        self.stdout.write("🔄 Начинаем миграцию файлов из S3 в R2")
        self.stdout.write(f"   S3 бакет: {s3_bucket}")
        self.stdout.write(f"   R2 бакет: {r2_bucket}")
        self.stdout.write(f"   Целевое окружение: {target_env}")
        if prefix:
            self.stdout.write(f"   Префикс: {prefix}")
        if dry_run:
            self.stdout.write(self.style.WARNING("   Режим DRY-RUN: файлы не будут скопированы"))
        
        try:
            # Создаем клиенты
            s3_client = boto3.client(
                's3',
                aws_access_key_id=s3_access_key,
                aws_secret_access_key=s3_secret_key,
                region_name=s3_region
            )
            
            r2_client = boto3.client(
                's3',
                aws_access_key_id=r2_access_key,
                aws_secret_access_key=r2_secret_key,
                endpoint_url=r2_endpoint
            )
            
            # Списываем все объекты из S3
            self.stdout.write(f"\n📋 Получение списка объектов из S3...")
            objects_to_migrate = []
            paginator = s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=s3_bucket, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects_to_migrate.append(obj['Key'])
            
            total_count = len(objects_to_migrate)
            self.stdout.write(f"   Найдено объектов: {total_count}")
            
            if total_count == 0:
                self.stdout.write(self.style.SUCCESS("✅ Нет объектов для миграции"))
                return
            
            if limit:
                objects_to_migrate = objects_to_migrate[:limit]
                self.stdout.write(f"   Ограничение: мигрируем только первые {limit} объектов")
            
            # Мигрируем файлы
            success_count = 0
            error_count = 0
            skipped_count = 0
            
            for key in objects_to_migrate:
                try:
                    # Проверяем, существует ли уже объект в R2
                    try:
                        r2_client.head_object(Bucket=r2_bucket, Key=key)
                        skipped_count += 1
                        if success_count % 100 == 0:
                            self.stdout.write(f"   Пропущено (уже существует): {key}")
                        continue
                    except ClientError as e:
                        if e.response['Error']['Code'] != '404':
                            raise
                    
                    if dry_run:
                        self.stdout.write(f"   [DRY-RUN] Копирование: {key}")
                        success_count += 1
                        continue
                    
                    # Определяем целевой ключ с учетом окружения
                    # Если ключ уже содержит prod/ или dev/, заменяем на target_env
                    # Иначе добавляем префикс окружения
                    if key.startswith('prod/') or key.startswith('dev/'):
                        # Заменяем существующий префикс окружения
                        target_key = key.split('/', 1)[1]  # Убираем prod/ или dev/
                        target_key = f'{target_env}/{target_key}'
                    elif key.startswith('images/') or key.startswith('videos/'):
                        # Добавляем префикс окружения перед images/ или videos/
                        target_key = f'{target_env}/{key}'
                    else:
                        # Добавляем префикс окружения и images/ (по умолчанию для изображений)
                        if not key.startswith('tmp/'):
                            target_key = f'{target_env}/images/{key}'
                        else:
                            target_key = f'{target_env}/{key}'
                    
                    # Копируем объект из S3 в R2
                    # Используем copy_object для эффективного копирования
                    copy_source = {
                        'Bucket': s3_bucket,
                        'Key': key
                    }
                    
                    # Получаем метаданные из S3
                    s3_metadata = s3_client.head_object(Bucket=s3_bucket, Key=key)
                    content_type = s3_metadata.get('ContentType', 'application/octet-stream')
                    
                    # Копируем в R2 с новым ключом
                    r2_client.copy_object(
                        CopySource=copy_source,
                        Bucket=r2_bucket,
                        Key=target_key,
                        ContentType=content_type,
                        MetadataDirective='COPY'
                    )
                    
                    if success_count % 100 == 0:
                        self.stdout.write(f"   Прогресс: {success_count}/{len(objects_to_migrate)} (копирование: {key} -> {target_key})")
                    
                    success_count += 1
                    if success_count % 100 == 0:
                        self.stdout.write(f"   Прогресс: {success_count}/{len(objects_to_migrate)}")
                        logger.info(f"Мигрировано {success_count} объектов")
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"Ошибка при миграции объекта {key}: {e}")
                    self.stdout.write(
                        self.style.ERROR(f"   ❌ Ошибка для {key}: {e}")
                    )
            
            self.stdout.write(f"\n📈 Результаты миграции:")
            self.stdout.write(f"   Всего объектов: {len(objects_to_migrate)}")
            self.stdout.write(f"   Успешно мигрировано: {success_count}")
            self.stdout.write(f"   Пропущено (уже существует): {skipped_count}")
            self.stdout.write(f"   Ошибок: {error_count}")
            
            if dry_run:
                self.stdout.write(self.style.WARNING("\n⚠️ Это был DRY-RUN. Для реальной миграции запустите без --dry-run"))
            else:
                self.stdout.write(self.style.SUCCESS(f"\n✅ Миграция завершена успешно!"))
                
        except Exception as e:
            logger.error(f"Критическая ошибка при миграции: {e}", exc_info=True)
            self.stdout.write(
                self.style.ERROR(f"❌ Критическая ошибка: {e}")
            )

