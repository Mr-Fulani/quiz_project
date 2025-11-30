# Generated manually for social media integration

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0003_taskcomment_taskcommentimage_taskcommentreport_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SocialMediaPost',
            fields=[
                ('id', models.AutoField(help_text='Уникальный идентификатор', primary_key=True, serialize=False)),
                ('platform', models.CharField(choices=[('pinterest', 'Pinterest'), ('instagram', 'Instagram'), ('tiktok', 'TikTok'), ('yandex_dzen', 'Яндекс Дзен'), ('youtube_shorts', 'YouTube Shorts'), ('facebook', 'Facebook')], help_text='Платформа социальной сети', max_length=50)),
                ('method', models.CharField(choices=[('api', 'Прямое API'), ('webhook', 'Webhook')], default='api', help_text='Метод публикации (API или webhook)', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Ожидает'), ('processing', 'Обрабатывается'), ('published', 'Опубликовано'), ('failed', 'Ошибка')], default='pending', help_text='Статус публикации', max_length=20)),
                ('post_id', models.CharField(blank=True, help_text='ID поста в соцсети', max_length=255, null=True)),
                ('post_url', models.URLField(blank=True, help_text='Ссылка на пост', max_length=500, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Дата создания записи')),
                ('published_at', models.DateTimeField(blank=True, help_text='Дата фактической публикации', null=True)),
                ('error_message', models.TextField(blank=True, help_text='Сообщение об ошибке', null=True)),
                ('retry_count', models.IntegerField(default=0, help_text='Количество попыток публикации')),
                ('task', models.ForeignKey(help_text='Связанная задача', on_delete=django.db.models.deletion.CASCADE, related_name='social_media_posts', to='tasks.task')),
            ],
            options={
                'verbose_name': 'Публикация в соцсетях',
                'verbose_name_plural': 'Публикации в соцсетях',
                'db_table': 'social_media_posts',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='socialmediapost',
            index=models.Index(fields=['task', 'platform'], name='social_medi_task_id_8f4c5a_idx'),
        ),
        migrations.AddIndex(
            model_name='socialmediapost',
            index=models.Index(fields=['status'], name='social_medi_status_7a2b9c_idx'),
        ),
        migrations.AddIndex(
            model_name='socialmediapost',
            index=models.Index(fields=['created_at'], name='social_medi_created_4d8e1f_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='socialmediapost',
            unique_together={('task', 'platform')},
        ),
    ]

