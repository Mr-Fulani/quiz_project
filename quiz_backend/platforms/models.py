from django.db import models





class TelegramChannel(models.Model):
    """
    Модель для Telegram каналов и групп.
    """
    class Meta:
        db_table = 'groups'
        verbose_name = 'Telegram канал'
        verbose_name_plural = 'Telegram каналы'

    id = models.AutoField(primary_key=True)
    group_name = models.CharField(
        max_length=255,
        null=False,
        help_text='Имя группы/канала'
    )
    group_id = models.BigIntegerField(
        unique=True,
        null=False,
        db_index=True,
        help_text='Telegram ID группы/канала'
    )
    topic_id = models.IntegerField(
        null=False,
        help_text='ID связанной темы'
    )
    language = models.CharField(
        max_length=50,
        null=False,
        help_text='Язык группы/канала'
    )
    location_type = models.CharField(
        max_length=50,
        choices=[
            ('group', 'Group'), 
            ('channel', 'Channel'),
            ('web', 'Website')
        ],
        default='group',
        help_text='Тип: группа, канал или веб-сайт'
    )
    username = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='Username группы/канала'
    )

    def __str__(self):
        return f"{self.group_name} ({self.group_id})"
