# Generated manually for partial unique email constraint

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            # Создаем partial unique index только для непустых email
            sql="""
            CREATE UNIQUE INDEX unique_user_email_not_null 
            ON users (email) 
            WHERE email IS NOT NULL AND email != '';
            """,
            # Удаляем индекс при откате
            reverse_sql="""
            DROP INDEX IF EXISTS unique_user_email_not_null;
            """
        ),
    ] 