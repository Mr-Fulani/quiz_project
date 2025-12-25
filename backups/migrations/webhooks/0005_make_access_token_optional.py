# Generated manually to make access_token optional for browser automation platforms

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("webhooks", "0004_add_browser_automation_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="socialmediacredentials",
            name="access_token",
            field=models.TextField(
                blank=True,
                help_text="Access token для API (не требуется для браузерной автоматизации)",
                null=True,
            ),
        ),
    ]

