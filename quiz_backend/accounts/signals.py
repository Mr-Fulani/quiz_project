from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import TelegramAdmin, TelegramAdminGroup
from .utils.telegram_notifications import notify_admin
from aiogram import Bot
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=TelegramAdmin)
def notify_telegram_admin_save(sender, instance, created, **kwargs):
    """
    Уведомляет Telegram-бота о создании или обновлении администратора.
    """
    action = 'added' if created else 'updated'
    notify_admin(action, instance, instance.groups.all())


@receiver(post_delete, sender=TelegramAdmin)
def notify_telegram_admin_delete(sender, instance, **kwargs):
    """
    Уведомляет Telegram-бота об удалении администратора.
    """
    notify_admin('deleted', instance, instance.groups.all())


@receiver(post_save, sender=TelegramAdminGroup)
async def promote_telegram_admin(sender, instance, created, **kwargs):
    """
    Назначает Telegram-админа в группе при добавлении связи TelegramAdminGroup.
    """
    if created:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        try:
            await bot.promote_chat_member(
                chat_id=instance.telegram_group.group_id,
                user_id=instance.telegram_admin.telegram_id,
                can_manage_chat=True,
                can_post_messages=True,
                can_edit_messages=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_promote_members=False
            )
            logger.info(f"Админ {instance.telegram_admin.telegram_id} назначен в группе {instance.telegram_group.group_id}")
        except Exception as e:
            logger.error(f"Ошибка назначения админа в группе {instance.telegram_group.group_id}: {e}")
        finally:
            await bot.session.close()