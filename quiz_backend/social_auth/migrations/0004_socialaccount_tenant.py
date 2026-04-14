# Generated manually - adds tenant FK to SocialAccount model

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("social_auth", "0003_socialauthsettings_tenant"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        # Шаг 1: Убираем старый unique_together без tenant
        migrations.AlterUniqueTogether(
            name="socialaccount",
            unique_together=set(),
        ),
        # Шаг 2: Добавляем поле tenant в SocialAccount (nullable для совместимости)
        migrations.AddField(
            model_name="socialaccount",
            name="tenant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="social_accounts",
                to="tenants.tenant",
                verbose_name="Тенант",
            ),
        ),
        # Шаг 3: Новый unique_together с tenant — разные тенанты могут иметь
        # одного и того же провайдер-юзера (мультитенантность)
        migrations.AlterUniqueTogether(
            name="socialaccount",
            unique_together={("tenant", "provider", "provider_user_id")},
        ),
    ]
