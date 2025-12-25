# Generated manually for browser automation support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("webhooks", "0003_globalwebhooklink"),
    ]

    operations = [
        migrations.AlterField(
            model_name="socialmediacredentials",
            name="platform",
            field=models.CharField(
                choices=[
                    ("pinterest", "Pinterest"),
                    ("yandex_dzen", "Яндекс Дзен"),
                    ("facebook", "Facebook"),
                    ("instagram", "Instagram"),
                    ("tiktok", "TikTok"),
                    ("youtube_shorts", "YouTube Shorts"),
                    ("twitter", "Twitter/X"),
                ],
                help_text="Платформа социальной сети",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="socialmediacredentials",
            name="browser_type",
            field=models.CharField(
                blank=True,
                choices=[("playwright", "Playwright"), ("selenium", "Selenium")],
                help_text="Тип браузера для автоматизации (playwright/selenium)",
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="socialmediacredentials",
            name="headless_mode",
            field=models.BooleanField(
                default=True, help_text="Использовать headless режим браузера"
            ),
        ),
    ]

