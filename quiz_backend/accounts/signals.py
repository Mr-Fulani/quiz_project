from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import TelegramAdmin, TelegramAdminGroup, CustomUser, DjangoAdmin
from aiogram import Bot
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CustomUser)
def sync_custom_user_with_django_admin(sender, instance, created, **kwargs):
    """
    Автоматически синхронизирует CustomUser с DjangoAdmin при изменении прав администратора.
    
    Логика:
    - Если пользователь получает права staff/superuser → создает/обновляет DjangoAdmin
    - Если пользователь теряет права staff → удаляет DjangoAdmin (не деактивирует)
    - Сохраняет связь между разными типами пользователей в системе
    
    Args:
        sender: Модель CustomUser
        instance: Экземпляр CustomUser
        created: True если создается новый пользователь
        **kwargs: Дополнительные параметры
    """
    try:
        # Проверяем, есть ли у пользователя права администратора
        has_admin_rights = instance.is_staff or instance.is_superuser
        
        if has_admin_rights:
            # Пользователь имеет права администратора - создаем/обновляем DjangoAdmin
            django_admin, created_django_admin = DjangoAdmin.objects.get_or_create(
                username=instance.username,
                defaults={
                    'email': instance.email,
                    'password': instance.password,
                    'is_django_admin': True,
                    'is_staff': instance.is_staff,
                    'is_superuser': instance.is_superuser,
                    'is_active': instance.is_active,
                    'language': instance.language or 'ru',
                    'phone_number': None,
                    'first_name': instance.first_name,
                    'last_name': instance.last_name,
                    'date_joined': instance.date_joined,
                    'last_login': instance.last_login
                }
            )
            
            if not created_django_admin:
                # Обновляем существующую запись DjangoAdmin
                django_admin.email = instance.email
                django_admin.password = instance.password
                django_admin.is_staff = instance.is_staff
                django_admin.is_superuser = instance.is_superuser
                django_admin.is_active = instance.is_active
                django_admin.language = instance.language or 'en'
                django_admin.first_name = instance.first_name
                django_admin.last_name = instance.last_name
                django_admin.last_login = instance.last_login
                django_admin.save()
                
                logger.info(f"Обновлена запись DjangoAdmin для пользователя {instance.username}")
            else:
                logger.info(f"Создана новая запись DjangoAdmin для пользователя {instance.username}")
                
        else:
            # Пользователь не имеет прав администратора - удаляем DjangoAdmin
            try:
                django_admin = DjangoAdmin.objects.get(username=instance.username)
                django_admin.delete()
                logger.info(f"Удалена запись DjangoAdmin для пользователя {instance.username}")
            except DjangoAdmin.DoesNotExist:
                # Записи DjangoAdmin не существует - ничего не делаем
                pass
                
    except Exception as e:
        logger.error(f"Ошибка синхронизации CustomUser {instance.username} с DjangoAdmin: {e}")


# Импортируем notify_admin только для TelegramAdmin сигналов
try:
    from .utils_folder.telegram_notifications import notify_admin
except ImportError:
    # Если модуль не найден, создаем заглушку
    def notify_admin(action, instance, groups):
        logger.warning(f"notify_admin не импортирован, пропускаем уведомление для {action} {instance}")
    logger.warning("Модуль telegram_notifications не найден, уведомления отключены")

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