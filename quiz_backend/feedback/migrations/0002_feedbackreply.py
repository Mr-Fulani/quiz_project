# Generated by Django 5.1.4 on 2025-07-19 16:25

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feedback', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FeedbackReply',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('reply_text', models.TextField(help_text='Текст ответа администратора', validators=[django.core.validators.MinLengthValidator(1)], verbose_name='Текст ответа')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Дата и время создания ответа', verbose_name='Дата создания')),
                ('is_sent_to_user', models.BooleanField(default=False, help_text='Было ли сообщение отправлено пользователю в Telegram', verbose_name='Отправлено пользователю')),
                ('sent_at', models.DateTimeField(blank=True, help_text='Дата и время отправки ответа пользователю', null=True, verbose_name='Дата отправки')),
                ('send_error', models.TextField(blank=True, help_text='Описание ошибки при отправке сообщения', null=True, verbose_name='Ошибка отправки')),
                ('admin', models.ForeignKey(help_text='Администратор, который дал ответ', on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Администратор')),
                ('feedback', models.ForeignKey(help_text='Сообщение, на которое дан ответ', on_delete=django.db.models.deletion.CASCADE, to='feedback.feedbackmessage', verbose_name='Сообщение поддержки')),
            ],
            options={
                'verbose_name': 'Ответ на сообщение поддержки',
                'verbose_name_plural': 'Ответы на сообщения поддержки',
                'db_table': 'feedback_replies',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['created_at'], name='feedback_re_created_0d2d40_idx'), models.Index(fields=['is_sent_to_user'], name='feedback_re_is_sent_94dca5_idx')],
            },
        ),
    ]
