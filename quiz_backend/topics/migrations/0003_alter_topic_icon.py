# Generated by Django 5.1.4 on 2025-04-18 06:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('topics', '0002_topic_icon'),
    ]

    operations = [
        migrations.AlterField(
            model_name='topic',
            name='icon',
            field=models.CharField(default='static/blog/images/icons/default-icon.png', help_text='Путь к иконке темы (например, blog/images/icons/java-icon.png)', max_length=255),
        ),
    ]
