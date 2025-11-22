from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import TelegramAdmin, TelegramAdminGroup, CustomUser, DjangoAdmin, MiniAppUser
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
    Также синхронизирует поля социальных сетей с MiniAppUser.
    
    Логика:
    - Если пользователь получает права staff/superuser → создает/обновляет DjangoAdmin
    - Если пользователь теряет права staff → удаляет DjangoAdmin (не деактивирует)
    - Сохраняет связь между разными типами пользователей в системе
    - Синхронизирует поля социальных сетей с MiniAppUser если есть связь
    
    Args:
        sender: Модель CustomUser
        instance: Экземпляр CustomUser
        created: True если создается новый пользователь
        **kwargs: Дополнительные параметры
    """
    try:
        # Синхронизируем поля с MiniAppUser
        # Это обеспечивает что данные подтягиваются везде где используется одна БД
        if hasattr(instance, 'mini_app_profile') and instance.mini_app_profile:
            try:
                mini_app_user = instance.mini_app_profile
                fields_updated = False
                
                # Список полей социальных сетей для синхронизации
                # Исключаем telegram, так как он управляется через SocialAccount
                social_fields = ['github', 'instagram', 'facebook', 'linkedin', 'youtube', 'website']
                
                # Список базовых полей для синхронизации
                # username не синхронизируется (уникален для каждой модели)
                basic_fields = ['first_name', 'last_name', 'bio', 'location', 'birth_date', 'language']
                
                changed_fields = []
                
                # Синхронизируем поля социальных сетей
                for field in social_fields:
                    custom_user_value = getattr(instance, field, None)
                    mini_app_value = getattr(mini_app_user, field, None)
                    
                    # Обновляем только если в CustomUser есть значение и оно отличается
                    if custom_user_value and custom_user_value.strip():
                        if not mini_app_value or mini_app_value.strip() != custom_user_value.strip():
                            setattr(mini_app_user, field, custom_user_value)
                            changed_fields.append(field)
                            fields_updated = True
                            logger.debug(f"Синхронизировано поле {field} для MiniAppUser (telegram_id={mini_app_user.telegram_id}) из CustomUser (id={instance.id})")
                
                # Синхронизируем базовые поля
                for field in basic_fields:
                    custom_user_value = getattr(instance, field, None)
                    mini_app_value = getattr(mini_app_user, field, None)
                    
                    # Для строковых полей проверяем на пустоту
                    if field in ['first_name', 'last_name', 'bio', 'location', 'language']:
                        if custom_user_value and custom_user_value.strip():
                            if not mini_app_value or mini_app_value.strip() != custom_user_value.strip():
                                setattr(mini_app_user, field, custom_user_value)
                                changed_fields.append(field)
                                fields_updated = True
                                logger.debug(f"Синхронизировано поле {field} для MiniAppUser (telegram_id={mini_app_user.telegram_id}) из CustomUser (id={instance.id})")
                    # Для birth_date проверяем на None
                    elif field == 'birth_date':
                        if custom_user_value:
                            if not mini_app_value or mini_app_value != custom_user_value:
                                setattr(mini_app_user, field, custom_user_value)
                                changed_fields.append(field)
                                fields_updated = True
                                logger.debug(f"Синхронизировано поле {field} для MiniAppUser (telegram_id={mini_app_user.telegram_id}) из CustomUser (id={instance.id})")
                
                # Синхронизируем avatar (приоритет у загруженного файла)
                if instance.avatar:
                    # Если в CustomUser есть загруженный avatar, используем его
                    if not mini_app_user.avatar or mini_app_user.avatar != instance.avatar:
                        mini_app_user.avatar = instance.avatar
                        changed_fields.append('avatar')
                        fields_updated = True
                        logger.debug(f"Синхронизирован avatar для MiniAppUser (telegram_id={mini_app_user.telegram_id}) из CustomUser (id={instance.id})")
                
                if fields_updated and changed_fields:
                    mini_app_user.save(update_fields=changed_fields)
                    logger.info(f"Синхронизированы поля для MiniAppUser (telegram_id={mini_app_user.telegram_id}) из CustomUser (id={instance.id}, username={instance.username}): {', '.join(changed_fields)}")
            except Exception as sync_error:
                logger.warning(f"Ошибка при синхронизации полей с MiniAppUser для CustomUser {instance.username}: {sync_error}")
        
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
        logger.error(f"Ошибка синхронизации CustomUser {instance.username} с DjangoAdmin и MiniAppUser: {e}")


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


@receiver(post_save, sender=MiniAppUser)
def sync_mini_app_user_with_custom_user(sender, instance, created, **kwargs):
    """
    Автоматически синхронизирует поля социальных сетей из MiniAppUser в CustomUser.
    
    Логика:
    - При обновлении MiniAppUser синхронизирует поля соцсетей в связанный CustomUser
    - Обеспечивает двустороннюю синхронизацию данных между сайтом и Mini App
    - Синхронизирует: telegram, github, instagram, facebook, linkedin, youtube, website
    
    Args:
        sender: Модель MiniAppUser
        instance: Экземпляр MiniAppUser
        created: True если создается новый пользователь
        **kwargs: Дополнительные параметры
    """
    try:
        # Синхронизируем поля из MiniAppUser в CustomUser
        # Это обеспечивает что данные подтягиваются везде где используется одна БД
        if hasattr(instance, 'linked_custom_user') and instance.linked_custom_user:
            try:
                custom_user = instance.linked_custom_user
                fields_updated = False
                changed_fields = []
                
                # Список полей социальных сетей для синхронизации
                # Исключаем telegram, так как он управляется через SocialAccount
                social_fields = ['github', 'instagram', 'facebook', 'linkedin', 'youtube', 'website']
                
                # Список базовых полей для синхронизации
                # username не синхронизируется (уникален для каждой модели)
                basic_fields = ['first_name', 'last_name', 'bio', 'location', 'birth_date', 'language']
                
                # Синхронизируем поля социальных сетей
                for field in social_fields:
                    mini_app_value = getattr(instance, field, None)
                    custom_user_value = getattr(custom_user, field, None)
                    
                    # Обновляем только если в MiniAppUser есть значение и оно отличается
                    if mini_app_value and mini_app_value.strip():
                        if not custom_user_value or custom_user_value.strip() != mini_app_value.strip():
                            setattr(custom_user, field, mini_app_value)
                            changed_fields.append(field)
                            fields_updated = True
                            logger.debug(f"Синхронизировано поле {field} для CustomUser (id={custom_user.id}) из MiniAppUser (telegram_id={instance.telegram_id})")
                
                # Синхронизируем базовые поля
                for field in basic_fields:
                    mini_app_value = getattr(instance, field, None)
                    custom_user_value = getattr(custom_user, field, None)
                    
                    # Для строковых полей проверяем на пустоту
                    if field in ['first_name', 'last_name', 'bio', 'location', 'language']:
                        if mini_app_value and mini_app_value.strip():
                            if not custom_user_value or custom_user_value.strip() != mini_app_value.strip():
                                setattr(custom_user, field, mini_app_value)
                                changed_fields.append(field)
                                fields_updated = True
                                logger.debug(f"Синхронизировано поле {field} для CustomUser (id={custom_user.id}) из MiniAppUser (telegram_id={instance.telegram_id})")
                    # Для birth_date проверяем на None
                    elif field == 'birth_date':
                        if mini_app_value:
                            if not custom_user_value or custom_user_value != mini_app_value:
                                setattr(custom_user, field, mini_app_value)
                                changed_fields.append(field)
                                fields_updated = True
                                logger.debug(f"Синхронизировано поле {field} для CustomUser (id={custom_user.id}) из MiniAppUser (telegram_id={instance.telegram_id})")
                
                # Синхронизируем avatar (приоритет у загруженного файла в MiniAppUser)
                if instance.avatar:
                    # Если в MiniAppUser есть загруженный avatar, используем его
                    if not custom_user.avatar or custom_user.avatar != instance.avatar:
                        custom_user.avatar = instance.avatar
                        changed_fields.append('avatar')
                        fields_updated = True
                        logger.debug(f"Синхронизирован avatar для CustomUser (id={custom_user.id}) из MiniAppUser (telegram_id={instance.telegram_id})")
                
                if fields_updated and changed_fields:
                    custom_user.save(update_fields=changed_fields)
                    logger.info(f"Синхронизированы поля для CustomUser (id={custom_user.id}, username={custom_user.username}) из MiniAppUser (telegram_id={instance.telegram_id}): {', '.join(changed_fields)}")
            except Exception as sync_error:
                logger.warning(f"Ошибка при синхронизации полей с CustomUser для MiniAppUser telegram_id={instance.telegram_id}: {sync_error}")
        
    except Exception as e:
        logger.error(f"Ошибка синхронизации MiniAppUser (telegram_id={instance.telegram_id}) с CustomUser: {e}")