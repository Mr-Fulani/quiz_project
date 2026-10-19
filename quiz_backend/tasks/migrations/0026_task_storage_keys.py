"""
Ссылки на картинки и видео задач хранятся ключом файла в хранилище, без домена:
домен подставляется при чтении из R2_PUBLIC_DOMAIN (см. tasks/storage_urls.py).
"""
import json

from django.db import migrations

import tasks.fields
from tasks.storage_urls import to_public_url, to_storage_key


def _convert(convert):
    def run(apps, schema_editor):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute('SELECT id, image_url, video_url, video_urls FROM tasks')
            rows = cursor.fetchall()
            for task_id, image_url, video_url, video_urls in rows:
                if isinstance(video_urls, str):
                    video_urls = json.loads(video_urls or '{}')
                new_urls = (
                    {lang: convert(url) for lang, url in video_urls.items()}
                    if isinstance(video_urls, dict) else video_urls
                )
                new_image, new_video = convert(image_url), convert(video_url)
                if (new_image, new_video, new_urls) != (image_url, video_url, video_urls):
                    cursor.execute(
                        'UPDATE tasks SET image_url = %s, video_url = %s, video_urls = %s WHERE id = %s',
                        [new_image, new_video, json.dumps(new_urls), task_id],
                    )
    return run


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0025_alter_tasktranslation_source_link"),
    ]

    operations = [
        migrations.AlterField(
            model_name="task",
            name="image_url",
            field=tasks.fields.StorageURLField(
                help_text="URL изображения задачи (в БД хранится ключ файла в хранилище)",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="task",
            name="video_url",
            field=tasks.fields.StorageURLField(
                blank=True,
                help_text="URL видео задачи (для совместимости, основное видео)",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="task",
            name="video_urls",
            field=tasks.fields.StorageURLMapField(
                blank=True,
                default=dict,
                help_text='URL видео по языкам: {"ru": "url1", "en": "url2"}',
            ),
        ),
        migrations.RunPython(_convert(to_storage_key), _convert(to_public_url)),
    ]
