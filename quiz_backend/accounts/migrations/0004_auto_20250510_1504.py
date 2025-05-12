from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0003_add_telegramadmingroup_and_groups'),
    ]

    operations = [
        # Удаляем ненужные поля из TelegramAdmin
        migrations.RemoveField(model_name='TelegramAdmin', name='password'),
        migrations.RemoveField(model_name='TelegramAdmin', name='email'),
        migrations.RemoveField(model_name='TelegramAdmin', name='first_name'),
        migrations.RemoveField(model_name='TelegramAdmin', name='last_name'),
        migrations.RemoveField(model_name='TelegramAdmin', name='is_staff'),
        migrations.RemoveField(model_name='TelegramAdmin', name='is_superuser'),
        migrations.RemoveField(model_name='TelegramAdmin', name='last_login'),
        migrations.RemoveField(model_name='TelegramAdmin', name='date_joined'),
        migrations.RemoveField(model_name='TelegramAdmin', name='phone_number'),
        migrations.RemoveField(model_name='TelegramAdmin', name='is_telegram_admin'),
        migrations.RemoveField(model_name='TelegramAdmin', name='is_django_admin'),
        migrations.RemoveField(model_name='TelegramAdmin', name='groups'),
        migrations.RemoveField(model_name='TelegramAdmin', name='user_permissions'),
        # Добавляем is_premium в TelegramUser
        migrations.AddField(
            model_name='TelegramUser',
            name='is_premium',
            field=models.BooleanField(default=False, verbose_name='Премиум аккаунт'),
        ),
    ]