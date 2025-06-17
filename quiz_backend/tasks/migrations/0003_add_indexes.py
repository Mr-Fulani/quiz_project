# quiz_project/tasks/migrations/0003_add_indexes.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('tasks', '0002_taskstatistics_selected_answer'),  # Замени на имя последней миграции из showmigrations
    ]

    operations = [
        migrations.AddIndex(
            model_name='Task',
            index=models.Index(
                fields=['published', 'topic_id', 'subtopic_id', 'difficulty'],
                name='task_filter_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='TaskTranslation',
            index=models.Index(
                fields=['task_id', 'language'],
                name='task_trans_task_lang_idx',
            ),
        ),
    ]
