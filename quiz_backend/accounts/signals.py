from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import TelegramAdmin, TelegramAdminGroup, CustomUser, DjangoAdmin
from aiogram import Bot
from django.conf import settings
from html import escape
import logging
import asyncio

logger = logging.getLogger(__name__)


def _format_channel_link(channel) -> str:
    """
    Возвращает HTML-ссылку на канал. Если username отсутствует, используем tg://openmessage.
    """
    safe_name = escape(channel.group_name or f"канал {channel.group_id}")

    if channel.username:
        username = channel.username.lstrip('@')
        link = f"https://t.me/{username}"
    else:
        link = f"tg://openmessage?chat_id={channel.group_id}"

    return f"<a href='{link}'>{safe_name}</a>"


def _build_admin_added_message(channel) -> str:
    channel_display = _format_channel_link(channel)
    return f"""
🎉 <b>Поздравляем!</b>

Вас назначили администратором в канале {channel_display}

Теперь у вас есть права на:
• Управление сообщениями
• Удаление сообщений
• Приглашение пользователей
• Ограничение участников
• Закрепление сообщений

Спасибо за вашу помощь в модерации! 🙏
""".strip()


def _build_admin_removed_message(channel) -> str:
    channel_display = _format_channel_link(channel)
    return f"""
⚠️ <b>Изменение прав</b>

Ваши права администратора были сняты в канале {channel_display}.

Если вы считаете, что это произошло по ошибке, свяжитесь с владельцем канала.
""".strip()

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
    from .utils_folder.telegram_notifications import notify_admin as notify_admin_async
except ImportError:
    # Если модуль не найден, создаем заглушку
    async def notify_admin_async(action, instance, groups):
        logger.warning(f"notify_admin не импортирован, пропускаем уведомление для {action} {instance}")
    logger.warning("Модуль telegram_notifications не найден, уведомления отключены")


def _run_notify_admin(action, instance, groups):
    """
    Синхронная обертка для async функции notify_admin.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(notify_admin_async(action, instance, groups))
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Ошибка при запуске async функции notify_admin: {e}")


@receiver(post_save, sender=TelegramAdmin)
def notify_telegram_admin_save(sender, instance, created, **kwargs):
    """
    Уведомляет Telegram-бота о создании или обновлении администратора.
    """
    action = 'added' if created else 'updated'
    _run_notify_admin(action, instance, instance.groups.all())


@receiver(post_delete, sender=TelegramAdmin)
def notify_telegram_admin_delete(sender, instance, **kwargs):
    """
    Уведомляет Telegram-бота об удалении администратора.
    """
    _run_notify_admin('deleted', instance, instance.groups.all())


async def _promote_telegram_admin_async(instance):
    """
    Асинхронная функция для назначения Telegram-админа в группе.
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        # Пытаемся назначить админа в Telegram
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
        except Exception as promote_error:
            # Логируем ошибку, но продолжаем отправлять уведомление
            logger.warning(
                f"Не удалось назначить админа {instance.telegram_admin.telegram_id} "
                f"в группе {instance.telegram_group.group_id}: {promote_error}. "
                f"Уведомление все равно будет отправлено."
            )

        # Отправляем уведомление независимо от результата promote_chat_member
        try:
            await bot.send_message(
                chat_id=instance.telegram_admin.telegram_id,
                text=_build_admin_added_message(instance.telegram_group),
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            logger.info(f"Уведомление о назначении отправлено пользователю {instance.telegram_admin.telegram_id}")
        except Exception as notification_error:
            logger.warning(
                f"Не удалось отправить уведомление пользователю {instance.telegram_admin.telegram_id}: {notification_error}"
            )
    except Exception as e:
        logger.error(f"Критическая ошибка при обработке назначения админа в группе {instance.telegram_group.group_id}: {e}")
    finally:
        await bot.session.close()


@receiver(post_save, sender=TelegramAdminGroup)
def promote_telegram_admin(sender, instance, created, **kwargs):
    """
    Назначает Telegram-админа в группе при добавлении связи TelegramAdminGroup.
    """
    if created:
        try:
            # Запускаем async функцию в новом event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_promote_telegram_admin_async(instance))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Ошибка при запуске async функции для назначения админа: {e}")


async def _notify_admin_rights_removed_async(instance):
    """
    Асинхронная функция для уведомления пользователя о снятии прав администратора.
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=instance.telegram_admin.telegram_id,
            text=_build_admin_removed_message(instance.telegram_group),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        logger.info(
            f"Пользователь {instance.telegram_admin.telegram_id} уведомлён о снятии прав в канале {instance.telegram_group.group_id}"
        )
    except Exception as e:
        logger.warning(
            f"Не удалось отправить уведомление о снятии прав пользователю {instance.telegram_admin.telegram_id}: {e}"
        )
    finally:
        await bot.session.close()


@receiver(post_delete, sender=TelegramAdminGroup)
def notify_admin_rights_removed(sender, instance, **kwargs):
    """
    Уведомляет пользователя о снятии прав администратора при удалении связи TelegramAdminGroup.
    """
    try:
        # Запускаем async функцию в новом event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_notify_admin_rights_removed_async(instance))
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Ошибка при запуске async функции для уведомления о снятии прав: {e}")