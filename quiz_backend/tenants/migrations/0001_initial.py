# tenants/migrations/0001_initial.py

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(help_text='Уникальный идентификатор тенанта (например: quiz-code, quiz-islam). Используется в URL и в docker-compose переменных.', max_length=100, unique=True)),
                ('name', models.CharField(help_text='Отображаемое название платформы (например: Quiz Code)', max_length=255)),
                ('domain', models.CharField(help_text='Основной домен сайта (например: quiz-code.com). Без www и https.', max_length=255, unique=True)),
                ('mini_app_domain', models.CharField(blank=True, help_text='Домен мини-аппа (например: mini.quiz-code.com). Без https.', max_length=255, null=True, unique=True)),
                ('bot_token', models.CharField(blank=True, help_text='Токен Telegram-бота этого тенанта (от @BotFather)', max_length=255)),
                ('bot_username', models.CharField(blank=True, help_text='Username бота без @ (например: mr_proger_bot)', max_length=100)),
                ('site_name', models.CharField(help_text='Название сайта для отображения в шаблонах и SEO', max_length=255)),
                ('site_description', models.TextField(blank=True, help_text='Краткое SEO-описание платформы')),
                ('theme_color', models.CharField(default='#6C63FF', help_text='Основной цвет темы в HEX (например: #6C63FF)', max_length=20)),
                ('logo', models.ImageField(blank=True, help_text='Логотип тенанта', null=True, upload_to='tenants/logos/')),
                ('default_language', models.CharField(default='ru', help_text='Язык по умолчанию (ru, en, ar и т.д.)', max_length=10)),
                ('meta_keywords', models.TextField(blank=True, help_text='Ключевые слова для SEO через запятую')),
                ('is_active', models.BooleanField(default=True, help_text='Активен ли тенант. Неактивные тенанты не принимают запросы.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Тенант',
                'verbose_name_plural': 'Тенанты',
                'db_table': 'tenants',
                'ordering': ['name'],
            },
        ),
    ]
