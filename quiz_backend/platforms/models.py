# platforms/models.py

from django.db import models
from django.utils.translation import gettext_lazy as _




class TelegramGroup(models.Model):
    """
    Модель для Telegram групп и каналов, аналогичная SQLAlchemy Group.
    """
    class Meta:
        db_table = 'telegram_groups'
        verbose_name = _('Telegram группа/канал')
        verbose_name_plural = _('Telegram группы/каналы')

    id = models.AutoField(primary_key=True)
    group_name = models.CharField(
        max_length=255,
        null=False,
        help_text=_('Имя группы или канала')
    )
    group_id = models.BigIntegerField(
        unique=True,
        null=False,
        db_index=True,
        help_text=_('Telegram ID группы или канала')
    )
    topic_id = models.ForeignKey(
        'topics.Topic',
        on_delete=models.CASCADE,
        null=False,
        help_text='Связанная тема'
    )
    language = models.CharField(
        max_length=50,
        null=False,
        help_text=_('Язык группы или канала')
    )
    location_type = models.CharField(
        max_length=50,
        choices=[
            ('group', 'Group'),
            ('channel', 'Channel'),
            ('web', 'Website')
        ],
        default='group',
        help_text=_('Тип: группа, канал или веб-сайт')
    )
    username = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_('Username группы или канала')
    )

    def __str__(self):
        return f"{self.group_name} ({self.group_id})"