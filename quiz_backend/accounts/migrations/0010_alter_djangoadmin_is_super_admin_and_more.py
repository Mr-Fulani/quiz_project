# Generated by Django 5.1.4 on 2025-02-13 23:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_delete_usersettings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='djangoadmin',
            name='is_super_admin',
            field=models.BooleanField(blank=True, default=False, null=True, verbose_name='Super Admin'),
        ),
        migrations.AlterField(
            model_name='djangoadmin',
            name='is_telegram_admin',
            field=models.BooleanField(blank=True, default=False, null=True, verbose_name='Telegram Admin'),
        ),
        migrations.AlterField(
            model_name='superadmin',
            name='is_super_admin',
            field=models.BooleanField(blank=True, default=False, null=True, verbose_name='Super Admin'),
        ),
        migrations.AlterField(
            model_name='superadmin',
            name='is_telegram_admin',
            field=models.BooleanField(blank=True, default=False, null=True, verbose_name='Telegram Admin'),
        ),
        migrations.AlterField(
            model_name='telegramadmin',
            name='is_super_admin',
            field=models.BooleanField(blank=True, default=False, null=True, verbose_name='Super Admin'),
        ),
        migrations.AlterField(
            model_name='telegramadmin',
            name='is_telegram_admin',
            field=models.BooleanField(blank=True, default=False, null=True, verbose_name='Telegram Admin'),
        ),
    ]
