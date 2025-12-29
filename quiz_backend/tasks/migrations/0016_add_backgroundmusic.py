# Generated migration for BackgroundMusic model
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0015_add_video_generation_progress'),
    ]

    operations = [
        migrations.CreateModel(
            name='BackgroundMusic',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255, help_text='Название трека')),
                ('audio_file', models.FileField(upload_to='background_music/', help_text='Аудиофайл (поддерживается: mp3, wav, m4a, aac, ogg, flac)')),
                ('size', models.BigIntegerField(blank=True, null=True, help_text='Размер файла в байтах')),
                ('content_type', models.CharField(blank=True, max_length=100, null=True)),
                ('duration_seconds', models.IntegerField(blank=True, null=True, help_text='Длительность в секундах (вычисляется автоматически если возможно)')),
                ('is_active', models.BooleanField(default=True, help_text='Включен ли трек для автоматического выбора')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'background_music',
                'verbose_name': 'Фоновая музыка',
                'verbose_name_plural': 'Фоновая музыка',
            },
        ),
        migrations.AddIndex(
            model_name='backgroundmusic',
            index=models.Index(fields=['is_active'], name='tasks_bgmusic_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='backgroundmusic',
            index=models.Index(fields=['name'], name='tasks_bgmusic_name_idx'),
        ),
    ]

