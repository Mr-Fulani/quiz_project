from django.db import migrations, models

class Migration(migrations.Migration):
    """
    Миграция для исправления полей username и language в telegram_admins.
    Делает их nullable, меняет max_length для username и безопасно убирает уникальные индексы.
    """
    dependencies = [
        ('accounts', '0004_auto_20250510_1504'),
    ]

    operations = [
        # Удаляем уникальные индексы и ограничения для username
        migrations.RunSQL(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'admins_username_key'
                ) THEN
                    ALTER TABLE telegram_admins
                    DROP CONSTRAINT admins_username_key;
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM pg_indexes
                    WHERE indexname = 'admins_username_6f424f9e_like'
                ) THEN
                    DROP INDEX admins_username_6f424f9e_like;
                END IF;
            END $$;
            """,
            reverse_sql="""
            ALTER TABLE telegram_admins
            ADD CONSTRAINT admins_username_key UNIQUE (username);
            CREATE INDEX admins_username_6f424f9e_like
            ON telegram_admins (username varchar_pattern_ops);
            """
        ),
        # Делаем username nullable и увеличиваем max_length до 255
        migrations.AlterField(
            model_name='TelegramAdmin',
            name='username',
            field=models.CharField(
                max_length=255, null=True, blank=True, verbose_name="Username"
            ),
        ),
        # Делаем language nullable
        migrations.AlterField(
            model_name='TelegramAdmin',
            name='language',
            field=models.CharField(
                max_length=10, default='ru', null=True, verbose_name="Язык"
            ),
        ),
    ]