from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0016_notification_tenant'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DROP INDEX IF EXISTS unique_user_email_not_null;
            CREATE UNIQUE INDEX unique_user_email_tenant_not_null 
            ON users (email, tenant_id) 
            WHERE email IS NOT NULL AND email != '';
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS unique_user_email_tenant_not_null;
            CREATE UNIQUE INDEX unique_user_email_not_null 
            ON users (email) 
            WHERE email IS NOT NULL AND email != '';
            """
        ),
    ]
