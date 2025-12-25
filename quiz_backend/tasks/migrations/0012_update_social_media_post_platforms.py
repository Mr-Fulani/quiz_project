# Generated manually for browser automation support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0011_add_video_generation_logs"),
    ]

    operations = [
        migrations.AlterField(
            model_name="socialmediapost",
            name="platform",
            field=models.CharField(
                choices=[
                    ("pinterest", "Pinterest"),
                    ("instagram", "Instagram"),
                    ("instagram_reels", "Instagram Reels"),
                    ("instagram_stories", "Instagram Stories"),
                    ("tiktok", "TikTok"),
                    ("yandex_dzen", "Яндекс Дзен"),
                    ("youtube_shorts", "YouTube Shorts"),
                    ("facebook", "Facebook"),
                    ("facebook_stories", "Facebook Stories"),
                    ("facebook_reels", "Facebook Reels"),
                    ("twitter", "Twitter/X"),
                ],
                help_text="Платформа социальной сети",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="socialmediapost",
            name="method",
            field=models.CharField(
                choices=[
                    ("api", "Прямое API"),
                    ("webhook", "Webhook"),
                    ("browser", "Браузерная автоматизация"),
                ],
                default="api",
                help_text="Метод публикации (API или webhook)",
                max_length=20,
            ),
        ),
    ]


