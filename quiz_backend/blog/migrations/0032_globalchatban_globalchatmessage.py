from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0031_platformresource_description_en_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='GlobalChatBan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(blank=True, default='', verbose_name='Причина бана')),
                ('banned_until', models.DateTimeField(blank=True, null=True, verbose_name='Бан до')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('banned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='issued_global_chat_bans', to='accounts.customuser', verbose_name='Кем выдан бан')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='global_chat_bans', to='tenants.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='global_chat_bans', to='accounts.customuser')),
            ],
            options={
                'verbose_name': 'Бан в общем чате',
                'verbose_name_plural': 'Баны в общем чате',
                'constraints': [models.UniqueConstraint(fields=('tenant', 'user'), name='unique_global_chat_ban_per_tenant_user')],
            },
        ),
        migrations.CreateModel(
            name='GlobalChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(verbose_name='Текст сообщения')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False, verbose_name='Удалено')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата удаления')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='global_chat_messages', to='accounts.customuser')),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deleted_global_chat_messages', to='accounts.customuser', verbose_name='Кем удалено')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='global_chat_messages', to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'Сообщение общего чата',
                'verbose_name_plural': 'Сообщения общего чата',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='globalchatmessage',
            index=models.Index(fields=['tenant', 'id'], name='global_chat_tenant_id_idx'),
        ),
        migrations.AddIndex(
            model_name='globalchatmessage',
            index=models.Index(fields=['tenant', 'created_at'], name='global_chat_tenant_created_idx'),
        ),
    ]
