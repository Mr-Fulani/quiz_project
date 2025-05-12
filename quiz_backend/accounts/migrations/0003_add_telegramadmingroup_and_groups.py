from django.db import migrations, models
import django.db.models.deletion


def migrate_groups_to_telegramadmingroup(apps, schema_editor):
    TelegramAdmin = apps.get_model('accounts', 'TelegramAdmin')
    TelegramAdminGroup = apps.get_model('accounts', 'TelegramAdminGroup')
    TelegramGroup = apps.get_model('platforms', 'TelegramGroup')

    for admin in TelegramAdmin.objects.all():
        try:
            for group in admin.groups.all():
                try:
                    telegram_group = TelegramGroup.objects.get(group_id=group.id)
                    TelegramAdminGroup.objects.create(
                        telegram_admin=admin,
                        telegram_group=telegram_group,
                    )
                except TelegramGroup.DoesNotExist:
                    continue
        except AttributeError:
            continue


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_remove_is_super_admin_and_groups'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('platforms', '0004_alter_telegramgroup_topic_id'),
    ]
    operations = [
        migrations.AddField(
            model_name='TelegramAdmin',
            name='groups',
            field=models.ManyToManyField(
                blank=True,
                related_name='telegram_admins',
                through='accounts.TelegramAdminGroup',
                to='platforms.TelegramGroup',
                verbose_name='Telegram Группа/Канал',
            ),
        ),
        migrations.RunPython(migrate_groups_to_telegramadmingroup, reverse_code=migrations.RunPython.noop),
    ]