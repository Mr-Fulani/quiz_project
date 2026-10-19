from django.db import migrations

# Значения, которые раньше были зашиты в код через сравнение slug.
TENANT_VALUES = {
    'quiz-code': {
        'author_name': 'Anvar Sh.',
        'contact_phone': '+90-552-582-1497',
        'social_profiles': '\n'.join([
            'https://www.youtube.com/@Mr_Fulani',
            'https://t.me/Mr_Fulani',
            'https://www.instagram.com/fulani_developer',
        ]),
        'is_author_site': True,
        'use_global_logo': True,
    },
    'iqro-forum': {
        'image_theme': 'islamic',
    },
}


def fill_values(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    for slug, values in TENANT_VALUES.items():
        Tenant.objects.filter(slug=slug).update(**values)


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0003_tenant_author_and_image_settings'),
    ]

    operations = [
        migrations.RunPython(fill_values, migrations.RunPython.noop),
    ]
