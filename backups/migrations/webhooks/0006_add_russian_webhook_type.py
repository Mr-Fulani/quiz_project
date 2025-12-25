# Generated manually for adding russian_only webhook type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("webhooks", "0003_globalwebhooklink"),
    ]

    operations = [
        migrations.AlterField(
            model_name="webhook",
            name="webhook_type",
            field=models.CharField(
                choices=[
                    ("social_media", "Социальные сети"),
                    ("russian_only", "Только русский язык"),
                    ("other", "Другое"),
                ],
                default="other",
                help_text="Тип webhook",
                max_length=50,
                verbose_name="Тип webhook",
            ),
        ),
    ]
