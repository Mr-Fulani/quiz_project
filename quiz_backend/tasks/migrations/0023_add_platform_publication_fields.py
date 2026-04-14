"""
Миграция: добавление полей статуса публикации по платформам.

- published_telegram: задача опубликована в Telegram-канале/группе
- published_website:  задача доступна на сайте
- published_mini_app: задача доступна в Telegram Mini App

Существующие задачи с published=True получают published_telegram=True
(обратная совместимость: поле published = синоним published_telegram).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0022_backgroundmusic_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='published_telegram',
            field=models.BooleanField(
                default=False,
                verbose_name='Опубликовано в Telegram',
                help_text='Задача опубликована в Telegram-канале/группе',
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='published_website',
            field=models.BooleanField(
                default=False,
                verbose_name='Опубликовано на сайте',
                help_text='Задача доступна на сайте',
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='published_mini_app',
            field=models.BooleanField(
                default=False,
                verbose_name='Опубликовано в Mini App',
                help_text='Задача доступна в Telegram Mini App',
            ),
        ),
        # Заполняем published_telegram из существующего поля published
        migrations.RunSQL(
            sql='UPDATE tasks SET published_telegram = published WHERE published = TRUE',
            reverse_sql='',
        ),
    ]
