# Generated by Django 5.1.4 on 2025-06-08 14:58

import blog.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0009_alter_marqueetext_link_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='marqueetext',
            name='link_url',
            field=models.CharField(blank=True, help_text='URL для ссылки (например, https://example.com, tg://resolve?domain=@username или tg://resolve?domain@username)', max_length=200, validators=[blog.models.CustomURLValidator()], verbose_name='URL ссылки'),
        ),
    ]
