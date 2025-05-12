from django.db import migrations

class Migration(migrations.Migration):
    """
    Миграция для удаления поля is_telegram_admin из django_admins.
    """
    dependencies = [
        ('accounts', '0006_alter_telegramadmin_managers_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE django_admins DROP COLUMN IF EXISTS is_telegram_admin;",
            reverse_sql="ALTER TABLE django_admins ADD COLUMN is_telegram_admin BOOLEAN NOT NULL DEFAULT FALSE;"
        )
    ]