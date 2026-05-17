from django.db import migrations, models
import django.db.models.deletion


def forwards_create_translations(apps, schema_editor):
    Topic = apps.get_model('topics', 'Topic')
    Subtopic = apps.get_model('topics', 'Subtopic')
    TopicTranslation = apps.get_model('topics', 'TopicTranslation')
    SubtopicTranslation = apps.get_model('topics', 'SubtopicTranslation')

    for topic in Topic.objects.select_related('tenant').all():
        language_code = ((getattr(topic.tenant, 'default_language', None) or 'en').strip().lower())
        TopicTranslation.objects.get_or_create(
            topic=topic,
            language_code=language_code,
            defaults={
                'name': topic.name,
                'description': topic.description,
            },
        )

    for subtopic in Subtopic.objects.select_related('topic__tenant').all():
        tenant = getattr(subtopic.topic, 'tenant', None)
        language_code = ((getattr(tenant, 'default_language', None) or 'en').strip().lower())
        SubtopicTranslation.objects.get_or_create(
            subtopic=subtopic,
            language_code=language_code,
            defaults={
                'name': subtopic.name,
                'description': None,
            },
        )


def backwards_delete_translations(apps, schema_editor):
    TopicTranslation = apps.get_model('topics', 'TopicTranslation')
    SubtopicTranslation = apps.get_model('topics', 'SubtopicTranslation')
    TopicTranslation.objects.all().delete()
    SubtopicTranslation.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('topics', '0007_topic_icon_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='TopicTranslation',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('language_code', models.CharField(help_text='Код языка перевода', max_length=10)),
                ('name', models.CharField(help_text='Локализованное название темы', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Локализованное описание темы', null=True)),
                ('topic', models.ForeignKey(help_text='Связанная тема', on_delete=django.db.models.deletion.CASCADE, related_name='translations', to='topics.topic')),
            ],
            options={
                'db_table': 'topic_translations',
                'verbose_name': 'Перевод темы',
                'verbose_name_plural': 'Переводы тем',
            },
        ),
        migrations.CreateModel(
            name='SubtopicTranslation',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('language_code', models.CharField(help_text='Код языка перевода', max_length=10)),
                ('name', models.CharField(help_text='Локализованное название подтемы', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Локализованное описание подтемы', null=True)),
                ('subtopic', models.ForeignKey(help_text='Связанная подтема', on_delete=django.db.models.deletion.CASCADE, related_name='translations', to='topics.subtopic')),
            ],
            options={
                'db_table': 'subtopic_translations',
                'verbose_name': 'Перевод подтемы',
                'verbose_name_plural': 'Переводы подтем',
            },
        ),
        migrations.AddIndex(
            model_name='topictranslation',
            index=models.Index(fields=['language_code'], name='topic_transl_language_7e0b4b_idx'),
        ),
        migrations.AddIndex(
            model_name='subtopictranslation',
            index=models.Index(fields=['language_code'], name='subtopic_tr_language_1883d3_idx'),
        ),
        migrations.AddConstraint(
            model_name='topictranslation',
            constraint=models.UniqueConstraint(fields=('topic', 'language_code'), name='unique_topic_translation_per_language'),
        ),
        migrations.AddConstraint(
            model_name='subtopictranslation',
            constraint=models.UniqueConstraint(fields=('subtopic', 'language_code'), name='unique_subtopic_translation_per_language'),
        ),
        migrations.RunPython(forwards_create_translations, backwards_delete_translations),
    ]
