# Generated manually for adding english_only webhook type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("webhooks", "0006_add_russian_webhook_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="webhook",
            name="webhook_type",
            field=models.CharField(
                choices=[
                    ("social_media", "Социальные сети"),
                    ("russian_only", "Только русский язык"),
                    ("english_only", "Только английский язык"),
                    ("other", "Другое"),
                ],
                default="other",
                help_text="Тип webhook",
                max_length=50,
                verbose_name="Тип webhook",
            ),
        ),
    ]
