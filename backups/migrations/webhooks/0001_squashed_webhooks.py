# Squashed migration for webhooks app
# Generated manually to sync local and production environments

import uuid
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    replaces = [
        ('webhooks', '0001_initial'),
        ('webhooks', '0002_webhook_target_platforms_webhook_webhook_type_and_more'),
        ('webhooks', '0003_globalwebhooklink'),
        ('webhooks', '0004_add_browser_automation_fields'),
        ('webhooks', '0005_make_access_token_optional'),
        ('webhooks', '0006_add_russian_webhook_type'),
        ('webhooks', '0007_alter_webhook_webhook_type'),
        ('webhooks', '0008_add_english_webhook_type'),
        ('webhooks', '0009_alter_webhook_webhook_type'),
    ]

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='DefaultLink',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('language', models.CharField(help_text='Язык', max_length=10)),
                ('topic', models.CharField(help_text='Тема', max_length=100)),
                ('link', models.CharField(help_text='URL ссылки', max_length=255, validators=[models.validators.URLValidator()])),
            ],
            options={
                'db_table': 'default_links',
                'unique_together': {('language', 'topic')},
                'indexes': [models.Index(fields=['language', 'topic'], name='default_links_language_topic_idx')],
            },
        ),
        migrations.CreateModel(
            name='GlobalWebhookLink',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('platform', models.CharField(help_text='Платформа (instagram, tiktok, etc.)', max_length=50, unique=True)),
                ('url', models.URLField(help_text='URL для глобального вебхука')),
                ('is_active', models.BooleanField(default=True, help_text='Активна ли ссылка')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, help_text='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Дата обновления')),
            ],
            options={
                'db_table': 'global_webhook_links',
                'verbose_name': 'Глобальная ссылка вебхука',
                'verbose_name_plural': 'Глобальные ссылки вебхуков',
                'indexes': [models.Index(fields=['is_active'], name='global_webhook_links_is_active_idx')],
            },
        ),
        migrations.CreateModel(
            name='SocialMediaCredentials',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('platform', models.CharField(choices=[('instagram', 'Instagram'), ('tiktok', 'TikTok'), ('youtube', 'YouTube'), ('pinterest', 'Pinterest')], help_text='Платформа', max_length=20, unique=True)),
                ('username', models.CharField(help_text='Имя пользователя', max_length=100)),
                ('access_token', models.TextField(blank=True, help_text='Access token', null=True)),
                ('refresh_token', models.TextField(blank=True, help_text='Refresh token', null=True)),
                ('token_expires_at', models.DateTimeField(blank=True, help_text='Когда истекает токен', null=True)),
                ('is_active', models.BooleanField(default=True, help_text='Активны ли credentials')),
                ('browser_type', models.CharField(choices=[('chromium', 'Chromium'), ('firefox', 'Firefox')], default='chromium', help_text='Тип браузера для автоматизации', max_length=20)),
                ('headless_mode', models.BooleanField(default=True, help_text='Запускать браузер в headless режиме')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, help_text='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Дата обновления')),
                ('deactivated_at', models.DateTimeField(blank=True, help_text='Дата деактивации', null=True)),
            ],
            options={
                'db_table': 'social_media_credentials',
                'verbose_name': 'Credentials для соцсетей',
                'verbose_name_plural': 'Credentials для соцсетей',
                'indexes': [models.Index(fields=['is_active'], name='social_media_credentials_is_active_idx')],
            },
        ),
        migrations.CreateModel(
            name='Webhook',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, help_text='Уникальный идентификатор вебхука', primary_key=True)),
                ('url', models.CharField(help_text='URL вебхука', max_length=255, unique=True)),
                ('service_name', models.CharField(blank=True, help_text='Название сервиса (например, make.com, Zapier)', max_length=100, null=True)),
                ('webhook_type', models.CharField(choices=[('social_media', 'Социальные сети'), ('russian_only', 'Только русский язык'), ('english_only', 'Только английский язык'), ('other', 'Другое')], default='other', help_text='Тип webhook', max_length=50, verbose_name='Тип webhook')),
                ('target_platforms', models.JSONField(blank=True, default=list, help_text='Список платформ для этого webhook (например: ["instagram", "tiktok", "youtube_shorts"])')),
                ('is_active', models.BooleanField(default=True, help_text='Активен ли вебхук')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, help_text='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Дата последнего обновления')),
            ],
            options={
                'db_table': 'webhooks',
                'verbose_name': 'Вебхук',
                'verbose_name_plural': 'Вебхуки',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['created_at'], name='webhooks_created_at_idx'),
                    models.Index(fields=['is_active'], name='webhooks_is_active_idx'),
                ],
            },
        ),
    ]
