# quiz_project/tasks/migrations/0005_add_indexes_again.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('tasks', '0004_remove_task_task_filter_idx_and_more'),
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