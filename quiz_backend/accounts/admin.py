import sys
import logging
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q
from accounts.models import CustomUser, TelegramUser, TelegramAdmin, TelegramAdminGroup, DjangoAdmin, UserChannelSubscription, MiniAppUser

logger = logging.getLogger(__name__)

# Импортируем миксин для сводной информации
try:
    from .admin_overview import UserOverviewMixin
except ImportError:
    # Если файл не найден, создаем пустой миксин
    class UserOverviewMixin:
        pass


class SocialAccountInline(admin.TabularInline):
    """
    Inline-форма для отображения социальных аккаунтов пользователя.
    """
    from social_auth.models import SocialAccount
    
    model = SocialAccount
    extra = 0
    verbose_name = "Социальный аккаунт"
    verbose_name_plural = "Социальные аккаунты"
    readonly_fields = ['provider', 'provider_user_id', 'is_active', 'created_at', 'last_login_at']
    fields = ['provider', 'provider_user_id', 'username', 'is_active', 'created_at']
    
    def has_add_permission(self, request, obj=None):
        """Запрещаем создание социальных аккаунтов вручную."""
        return False


class TelegramAdminGroupInline(admin.TabularInline):
    """
    Inline-форма для связи TelegramAdmin с группами/каналами.
    """
    model = TelegramAdminGroup
    extra = 1
    verbose_name = "Группа/Канал"
    verbose_name_plural = "Группы/Каналы"
    fields = ['telegram_group']
    raw_id_fields = ['telegram_group']


from .telegram_admin_service import TelegramAdminService, run_async_function


class TelegramAdminAdmin(admin.ModelAdmin):
    """
    Админ-панель для TelegramAdmin с интеграцией Telegram Bot API.
    """
    list_display = ['telegram_id', 'username', 'language', 'is_active', 'photo', 'group_count']
    search_fields = ['telegram_id', 'username']
    list_filter = ['is_active', 'language']
    inlines = [TelegramAdminGroupInline]
    actions = [
        'make_active', 'make_inactive', 
        'remove_admin_rights_from_all_channels',
        'delete_admin_completely', 'check_bot_permissions_in_channels'
    ]

    def group_count(self, obj):
        """
        Подсчёт групп/каналов админа.
        """
        return obj.groups.count()
    group_count.short_description = 'Группы'



    def make_active(self, request, queryset):
        """
        Активировать админов.
        """
        queryset.update(is_active=True)
        self.message_user(request, f"Активировано {queryset.count()} админов.")
    make_active.short_description = "Активировать админов"

    def make_inactive(self, request, queryset):
        """
        Деактивировать админов.
        """
        queryset.update(is_active=False)
        self.message_user(request, f"Деактивировано {queryset.count()} админов.")
    make_inactive.short_description = "Деактивировать админов"



    def remove_admin_rights_from_all_channels(self, request, queryset):
        """
        Удаляет права администратора из всех каналов с детальным отчетом.
        """
        total_removed = 0
        total_admins = queryset.count()
        
        self.message_user(request, f"🔄 Начинаем удаление прав администратора для {total_admins} пользователей...")
        
        for i, admin in enumerate(queryset, 1):
            self.message_user(request, f"📋 Обрабатываем администратора {i}/{total_admins}: {admin.username or admin.telegram_id}")
            
            # Получаем все каналы админа
            admin_groups = list(admin.groups.all())
            channel_ids = [group.group_id for group in admin_groups]
            
            if not channel_ids:
                self.message_user(request, f"⚠️ Администратор {admin.username or admin.telegram_id} не имеет связанных каналов", level='WARNING')
                continue
            
            service = TelegramAdminService()
            try:
                success_count, messages = run_async_function(
                    service.remove_admin_from_all_channels,
                    admin.telegram_id,
                    channel_ids
                )
                total_removed += success_count
                
                # Показываем детальные сообщения
                successful_channels = []
                failed_channels = []
                
                for message in messages:
                    if "✅" in message or "🎉" in message:
                        self.message_user(request, message, level='SUCCESS')
                        # Извлекаем ID канала из успешного сообщения
                        if "Канал " in message and ":" in message:
                            try:
                                channel_id_str = message.split("Канал ")[1].split(":")[0].strip()
                                successful_channels.append(int(channel_id_str))
                            except (ValueError, IndexError):
                                pass
                    elif "⚠️" in message:
                        self.message_user(request, message, level='WARNING')
                    elif "❌" in message:
                        self.message_user(request, message, level='ERROR')
                        # Извлекаем ID канала из неуспешного сообщения
                        if "Канал " in message and ":" in message:
                            try:
                                channel_id_str = message.split("Канал ")[1].split(":")[0].strip()
                                failed_channels.append(int(channel_id_str))
                            except (ValueError, IndexError):
                                pass
                    else:
                        self.message_user(request, message)
                
                # Удаляем связи только для успешно удаленных каналов
                if successful_channels:
                    removed_relations = 0
                    for group in admin_groups:
                        if group.group_id in successful_channels:
                            # Удаляем связь только для успешно удаленного канала
                            TelegramAdminGroup.objects.filter(
                                telegram_admin=admin,
                                telegram_group=group
                            ).delete()
                            removed_relations += 1
                    
                    self.message_user(
                        request, 
                        f"🗑️ Удалено {removed_relations} связей из базы данных для успешно удаленных каналов",
                        level='SUCCESS'
                    )
                
                # Показываем информацию о неудаленных каналах
                if failed_channels:
                    failed_group_names = []
                    for group in admin_groups:
                        if group.group_id in failed_channels:
                            failed_group_names.append(group.group_name or f"канал {group.group_id}")
                    
                    if failed_group_names:
                        self.message_user(
                            request,
                            f"⚠️ Связи сохранены для каналов, где удаление не удалось: {', '.join(failed_group_names)}",
                            level='WARNING'
                        )
                        
                # Отправляем уведомление пользователю только о успешно удаленных каналах
                if successful_channels:
                    try:
                        # Получаем информацию только об успешно удаленных каналах
                        channel_names = []
                        for group in admin_groups:
                            if group.group_id in successful_channels:
                                if group.group_name:
                                    if group.username:
                                        channel_link = f"https://t.me/{group.username}"
                                        channel_names.append(f"<a href='{channel_link}'>{group.group_name}</a>")
                                    else:
                                        channel_names.append(f"<b>{group.group_name}</b>")
                                else:
                                    channel_names.append(f"<b>канал {group.group_id}</b>")
                        
                        if channel_names:
                            channels_list = "\n".join([f"• {name}" for name in channel_names])
                            
                            notification_message = f"""
📢 <b>Уведомление</b>

Ваши права администратора были отозваны в следующих каналах:

{channels_list}

Вы больше не можете:
• Управлять сообщениями
• Удалять сообщения
• Приглашать пользователей
• Ограничивать участников
• Закреплять сообщения

Если у вас есть вопросы, обратитесь к владельцам каналов.
                            """.strip()
                            
                            # Отправляем уведомление
                            message_service = TelegramAdminService()
                            try:
                                message_sent, message_result = run_async_function(
                                    message_service.send_message_to_user,
                                    admin.telegram_id,
                                    notification_message
                                )
                                
                                if message_sent:
                                    logger.info(f"Уведомление об удалении прав отправлено администратору {admin.telegram_id}")
                                else:
                                    logger.warning(f"Не удалось отправить уведомление администратору {admin.telegram_id}: {message_result}")
                            finally:
                                message_service.close()
                                
                    except Exception as e:
                        logger.warning(f"Ошибка при отправке уведомления администратору {admin.telegram_id}: {e}")
                        
            except Exception as e:
                error_msg = f"❌ Ошибка при обработке администратора {admin.username or admin.telegram_id}: {str(e)}"
                self.message_user(request, error_msg, level='ERROR')
            finally:
                service.close()
        
        # Итоговое сообщение
        if total_removed > 0:
            self.message_user(
                request, 
                f"✅ Завершено! Удалены права администратора у {total_removed} пользователей из каналов. Связи в базе данных удалены только для успешно обработанных каналов.",
                level='SUCCESS'
            )
        else:
            self.message_user(
                request, 
                f"⚠️ Завершено! Не удалось удалить права администратора ни у одного пользователя. Проверьте права бота и статус администраторов.",
                level='WARNING'
            )
    remove_admin_rights_from_all_channels.short_description = "👤 Убрать права админа из всех каналов"



    def delete_admin_completely(self, request, queryset):
        """
        Полностью удаляет админов: убирает права из Telegram + удаляет из таблицы админов.
        """
        total_removed = 0
        total_admins = queryset.count()
        
        self.message_user(request, f"🔄 Начинаем полное удаление {total_admins} администраторов...")
        
        for i, admin in enumerate(queryset, 1):
            self.message_user(request, f"📋 Обрабатываем администратора {i}/{total_admins}: {admin.username or admin.telegram_id}")
            
            channel_ids = [group.group_id for group in admin.groups.all()]
            if not channel_ids:
                self.message_user(request, f"⚠️ Администратор {admin.username or admin.telegram_id} не имеет связанных каналов", level='WARNING')
                continue
            
            service = TelegramAdminService()
            try:
                success_count, messages = run_async_function(
                    service.remove_admin_from_all_channels,
                    admin.telegram_id,
                    channel_ids
                )
                total_removed += success_count
                
                # Показываем детальные сообщения
                for message in messages:
                    if "✅" in message or "🎉" in message:
                        self.message_user(request, message, level='SUCCESS')
                    elif "⚠️" in message:
                        self.message_user(request, message, level='WARNING')
                    elif "❌" in message:
                        self.message_user(request, message, level='ERROR')
                    else:
                        self.message_user(request, message)
                        
                # Отправляем уведомление пользователю о полном удалении
                if success_count > 0:
                    try:
                        # Получаем информацию о каналах для уведомления
                        channel_names = []
                        for group in admin.groups.all():
                            if group.group_name:
                                if group.username:
                                    channel_link = f"https://t.me/{group.username}"
                                    channel_names.append(f"<a href='{channel_link}'>{group.group_name}</a>")
                                else:
                                    channel_names.append(f"<b>{group.group_name}</b>")
                            else:
                                channel_names.append(f"<b>канал {group.group_id}</b>")
                        
                        if channel_names:
                            channels_list = "\n".join([f"• {name}" for name in channel_names])
                            
                            notification_message = f"""
🚫 <b>Важные изменения</b>

Вы были полностью удалены из следующих каналов:

{channels_list}

Это означает, что:
• Ваши права администратора отозваны
• Вы удалены из каналов
• Ваша запись администратора удалена из системы

Если это произошло по ошибке, обратитесь к владельцам каналов.
                            """.strip()
                            
                            # Отправляем уведомление
                            message_service = TelegramAdminService()
                            try:
                                message_sent, message_result = run_async_function(
                                    message_service.send_message_to_user,
                                    admin.telegram_id,
                                    notification_message
                                )
                                
                                if message_sent:
                                    logger.info(f"Уведомление о полном удалении отправлено администратору {admin.telegram_id}")
                                else:
                                    logger.warning(f"Не удалось отправить уведомление администратору {admin.telegram_id}: {message_result}")
                            finally:
                                message_service.close()
                                
                    except Exception as e:
                        logger.warning(f"Ошибка при отправке уведомления администратору {admin.telegram_id}: {e}")
                        
            except Exception as e:
                error_msg = f"❌ Ошибка при обработке администратора {admin.username or admin.telegram_id}: {str(e)}"
                self.message_user(request, error_msg, level='ERROR')
            finally:
                service.close()
        
        # Полностью удаляем админов из базы данных
        admin_count = queryset.count()
        queryset.delete()
        
        # Итоговое сообщение
        if total_removed > 0:
            self.message_user(
                request, 
                f"✅ Завершено! Полностью удалено {admin_count} администраторов: права убраны из Telegram ({total_removed} успешно), записи удалены из базы данных.",
                level='SUCCESS'
            )
        else:
            self.message_user(
                request, 
                f"⚠️ Завершено! Удалено {admin_count} администраторов из базы данных, но не удалось убрать права из Telegram. Проверьте права бота.",
                level='WARNING'
            )
    delete_admin_completely.short_description = "🗑️ Полностью удалить админа (Telegram + БД)"





    def check_bot_permissions_in_channels(self, request, queryset):
        """
        Проверяет права бота в каналах админов.
        """
        service = TelegramAdminService()
        checked_channels = set()
        
        for admin in queryset:
            for group in admin.groups.all():
                if group.group_id not in checked_channels:
                    try:
                        has_permissions, message = run_async_function(
                            service.check_bot_permissions,
                            group.group_id
                        )
                        if has_permissions:
                            self.message_user(request, f"✅ {group.group_name}: {message}", level='SUCCESS')
                        else:
                            self.message_user(request, f"❌ {group.group_name}: {message}", level='ERROR')
                        checked_channels.add(group.group_id)
                    except Exception as e:
                        self.message_user(request, f"❌ {group.group_name}: Ошибка проверки прав: {e}", level='ERROR')
        
        service.close()
        self.message_user(request, f"Проверено {len(checked_channels)} каналов.")
    check_bot_permissions_in_channels.short_description = "🔍 Проверить права бота в каналах (админ)"


class DjangoAdminAdmin(admin.ModelAdmin):
    """
    Админ-панель для DjangoAdmin: только просмотр основных статусов, без редактирования данных.
    """
    list_display = ['username', 'is_active', 'is_django_admin', 'last_login', 'custom_user_status']
    search_fields = ['username']
    list_filter = ['is_django_admin', 'is_active']
    actions = ['make_staff', 'remove_staff', 'make_superuser', 'remove_superuser', 'delete_django_admin', 'sync_with_custom_user']
    readonly_fields = ['username', 'is_active', 'is_django_admin', 'last_login', 'custom_user_status', 'user_groups', 'individual_permissions', 'group_permissions']
    fieldsets = (
        (None, {'fields': ('username',)}),
        ('Статус', {'fields': ('is_active', 'is_django_admin', 'last_login', 'custom_user_status')}),
        ('Группы пользователя', {'fields': ('user_groups',)}),
        ('Индивидуальные права', {'fields': ('individual_permissions',), 'classes': ('collapse',)}),
        ('Права через группы', {'fields': ('group_permissions',), 'classes': ('collapse',)}),
    )

    def user_groups(self, obj):
        """
        Отображает группы, в которых состоит пользователь.
        """
        try:
            custom_user = CustomUser.objects.get(username=obj.username)
            groups = custom_user.groups.all()
            if groups:
                return ', '.join([group.name for group in groups])
            else:
                return 'Не состоит ни в одной группе'
        except CustomUser.DoesNotExist:
            return 'Пользователь не найден'
    user_groups.short_description = 'Группы пользователя'

    def individual_permissions(self, obj):
        """
        Отображает индивидуальные права пользователя с группировкой по приложениям.
        """
        try:
            custom_user = CustomUser.objects.get(username=obj.username)
            permissions = custom_user.user_permissions.all()
            
            if not permissions:
                return 'Нет индивидуальных прав'
            
            # Группируем разрешения по приложениям
            app_permissions = {}
            for perm in permissions:
                app_name = perm.content_type.app_label
                if app_name not in app_permissions:
                    app_permissions[app_name] = []
                app_permissions[app_name].append(perm)
            
            # Формируем красивый вывод
            result = []
            for app_name, perms in sorted(app_permissions.items()):
                app_display = self._get_app_display_name(app_name)
                result.append(f"<strong>{app_display}:</strong>")
                
                for perm in sorted(perms, key=lambda x: x.codename):
                    action = self._get_action_display_name(perm.codename)
                    model_name = self._get_model_display_name(perm.content_type.model)
                    result.append(f"  • {action} {model_name}")
                
                result.append("")  # Пустая строка между приложениями
            
            from django.utils.safestring import mark_safe
            return mark_safe("<br>".join(result))
            
        except CustomUser.DoesNotExist:
            return 'Пользователь не найден'
    individual_permissions.short_description = 'Индивидуальные права'

    def group_permissions(self, obj):
        """
        Отображает права, полученные через группы, с группировкой по приложениям.
        """
        try:
            custom_user = CustomUser.objects.get(username=obj.username)
            group_permissions = set()
            
            for group in custom_user.groups.all():
                for perm in group.permissions.all():
                    group_permissions.add(perm)
            
            if not group_permissions:
                return 'Нет прав через группы'
            
            # Группируем разрешения по приложениям
            app_permissions = {}
            for perm in group_permissions:
                app_name = perm.content_type.app_label
                if app_name not in app_permissions:
                    app_permissions[app_name] = []
                app_permissions[app_name].append(perm)
            
            # Формируем красивый вывод
            result = []
            for app_name, perms in sorted(app_permissions.items()):
                app_display = self._get_app_display_name(app_name)
                result.append(f"<strong>{app_display}:</strong>")
                
                for perm in sorted(perms, key=lambda x: x.codename):
                    action = self._get_action_display_name(perm.codename)
                    model_name = self._get_model_display_name(perm.content_type.model)
                    result.append(f"  • {action} {model_name}")
                
                result.append("")  # Пустая строка между приложениями
            
            from django.utils.safestring import mark_safe
            return mark_safe("<br>".join(result))
            
        except CustomUser.DoesNotExist:
            return 'Пользователь не найден'
    group_permissions.short_description = 'Права через группы'

    def custom_user_status(self, obj):
        """
        Отображает статус связанного CustomUser.
        """
        from django.utils.safestring import mark_safe
        
        try:
            custom_user = CustomUser.objects.get(username=obj.username)
            if custom_user.is_staff or custom_user.is_superuser:
                return mark_safe('<span style="color: green;">✅ Права есть</span>')
            else:
                return mark_safe('<span style="color: red;">❌ Без прав</span>')
        except CustomUser.DoesNotExist:
            return mark_safe('<span style="color: orange;">⚠️ Пользователь не найден</span>')
    custom_user_status.short_description = 'Статус CustomUser'

    def make_staff(self, request, queryset):
        """
        Дать права персонала.
        """
        updated_count = 0
        for admin in queryset:
            try:
                custom_user = CustomUser.objects.get(username=admin.username)
                if not custom_user.is_staff:
                    custom_user.is_staff = True
                    custom_user.save()  # Сигнал обновит DjangoAdmin
                    updated_count += 1
                    self.message_user(
                        request, 
                        f"✅ Пользователь {admin.username} получил права staff.",
                        level='SUCCESS'
                    )
                else:
                    self.message_user(
                        request, 
                        f"ℹ️ Пользователь {admin.username} уже имеет права staff.",
                        level='INFO'
                    )
            except CustomUser.DoesNotExist:
                self.message_user(
                    request, 
                    f"❌ Пользователь {admin.username} не найден в CustomUser.",
                    level='ERROR'
                )
        
        if updated_count > 0:
            self.message_user(
                request, 
                f"🎉 {updated_count} пользователей получили права staff.",
                level='SUCCESS'
            )
    make_staff.short_description = "Сделать персоналом"

    def remove_staff(self, request, queryset):
        """
        Убрать права персонала.
        """
        updated_count = 0
        for admin in queryset:
            try:
                custom_user = CustomUser.objects.get(username=admin.username)
                if custom_user.is_staff:
                    custom_user.is_staff = False
                    custom_user.save()  # Сигнал удалит из DjangoAdmin
                    updated_count += 1
                    self.message_user(
                        request, 
                        f"✅ Пользователь {admin.username} потерял права staff.",
                        level='SUCCESS'
                    )
                else:
                    self.message_user(
                        request, 
                        f"ℹ️ Пользователь {admin.username} уже не имеет прав staff.",
                        level='INFO'
                    )
            except CustomUser.DoesNotExist:
                self.message_user(
                    request, 
                    f"❌ Пользователь {admin.username} не найден в CustomUser.",
                    level='ERROR'
                )
        
        if updated_count > 0:
            self.message_user(
                request, 
                f"🗑️ {updated_count} пользователей потеряли права staff.",
                level='SUCCESS'
            )
    remove_staff.short_description = "Убрать права персонала"

    def make_superuser(self, request, queryset):
        """
        Дать права суперпользователя.
        """
        updated_count = 0
        for admin in queryset:
            try:
                custom_user = CustomUser.objects.get(username=admin.username)
                if not custom_user.is_superuser:
                    custom_user.is_superuser = True
                    custom_user.is_staff = True  # Суперпользователь должен быть staff
                    custom_user.save()  # Сигнал обновит DjangoAdmin
                    updated_count += 1
                    self.message_user(
                        request, 
                        f"✅ Пользователь {admin.username} получил права суперпользователя.",
                        level='SUCCESS'
                    )
                else:
                    self.message_user(
                        request, 
                        f"ℹ️ Пользователь {admin.username} уже является суперпользователем.",
                        level='INFO'
                    )
            except CustomUser.DoesNotExist:
                self.message_user(
                    request, 
                    f"❌ Пользователь {admin.username} не найден в CustomUser.",
                    level='ERROR'
                )
        
        if updated_count > 0:
            self.message_user(
                request, 
                f"🎉 {updated_count} пользователей получили права суперпользователя.",
                level='SUCCESS'
            )
    make_superuser.short_description = "Сделать суперпользователем"

    def remove_superuser(self, request, queryset):
        """
        Убрать права суперпользователя.
        """
        updated_count = 0
        for admin in queryset:
            try:
                custom_user = CustomUser.objects.get(username=admin.username)
                if custom_user.is_superuser:
                    custom_user.is_superuser = False
                    # Если нет других прав staff, убираем и их
                    if not custom_user.is_staff:
                        custom_user.is_staff = False
                    custom_user.save()  # Сигнал обновит/удалит DjangoAdmin
                    updated_count += 1
                    self.message_user(
                        request, 
                        f"✅ Пользователь {admin.username} потерял права суперпользователя.",
                        level='SUCCESS'
                    )
                else:
                    self.message_user(
                        request, 
                        f"ℹ️ Пользователь {admin.username} уже не является суперпользователем.",
                        level='INFO'
                    )
            except CustomUser.DoesNotExist:
                self.message_user(
                    request, 
                    f"❌ Пользователь {admin.username} не найден в CustomUser.",
                    level='ERROR'
                )
        
        if updated_count > 0:
            self.message_user(
                request, 
                f"🗑️ {updated_count} пользователей потеряли права суперпользователя.",
                level='SUCCESS'
            )
    remove_superuser.short_description = "Убрать права суперпользователя"

    def delete_django_admin(self, request, queryset):
        """
        Удаляет выбранных Django администраторов.
        Пользователи остаются в CustomUser, но теряют права администратора.
        """
        deleted_count = 0
        for admin in queryset:
            try:
                custom_user = CustomUser.objects.get(username=admin.username)
                # Убираем права администратора
                custom_user.is_staff = False
                custom_user.is_superuser = False
                custom_user.save()  # Сигнал удалит из DjangoAdmin
                
                # Дополнительно удаляем запись DjangoAdmin
                admin.delete()
                deleted_count += 1
                self.message_user(
                    request, 
                    f"✅ Django администратор {admin.username} удален. Пользователь остался в системе.",
                    level='SUCCESS'
                )
            except CustomUser.DoesNotExist:
                # Если CustomUser не найден, просто удаляем DjangoAdmin
                admin.delete()
                deleted_count += 1
                self.message_user(
                    request, 
                    f"✅ Django администратор {admin.username} удален (CustomUser не найден).",
                    level='SUCCESS'
                )
        
        if deleted_count > 0:
            self.message_user(
                request, 
                f"🗑️ {deleted_count} Django администраторов удалено.",
                level='SUCCESS'
            )
    delete_django_admin.short_description = "Удалить Django администратора"

    def sync_with_custom_user(self, request, queryset):
        """
        Синхронизирует данные DjangoAdmin с CustomUser.
        """
        synced_count = 0
        for admin in queryset:
            try:
                custom_user = CustomUser.objects.get(username=admin.username)
                # Обновляем данные DjangoAdmin из CustomUser
                admin.email = custom_user.email
                admin.password = custom_user.password
                admin.is_staff = custom_user.is_staff
                admin.is_superuser = custom_user.is_superuser
                admin.is_active = custom_user.is_active
                admin.language = custom_user.language or 'en'
                admin.first_name = custom_user.first_name
                admin.last_name = custom_user.last_name
                admin.last_login = custom_user.last_login
                admin.save()
                
                synced_count += 1
                self.message_user(
                    request, 
                    f"✅ Данные {admin.username} синхронизированы с CustomUser.",
                    level='SUCCESS'
                )
            except CustomUser.DoesNotExist:
                self.message_user(
                    request, 
                    f"❌ Пользователь {admin.username} не найден в CustomUser.",
                    level='ERROR'
                )
        
        if synced_count > 0:
            self.message_user(
                request, 
                f"🔄 {synced_count} записей синхронизировано с CustomUser.",
                level='SUCCESS'
            )
    sync_with_custom_user.short_description = "Синхронизировать с CustomUser"

    def _get_app_display_name(self, app_name):
        """
        Возвращает красивое название приложения.
        """
        app_names = {
            'auth': '🔐 Аутентификация',
            'accounts': '👥 Пользователи',
            'blog': '📝 Блог',
            'feedback': '💬 Обратная связь',
            'donation': '💰 Пожертвования',
            'platforms': '📱 Платформы',
            'tasks': '📋 Задачи',
            'topics': '🏷️ Темы',
            'webhooks': '🔗 Вебхуки',
            'social_auth': '🔗 Социальная аутентификация',
            'contenttypes': '📄 Типы содержимого',
            'sessions': '🕐 Сессии',
            'sites': '🌐 Сайты',
            'admin': '⚙️ Администрирование',
            'silk': '🔍 Профилирование',
        }
        return app_names.get(app_name, f"📦 {app_name.title()}")

    def _get_action_display_name(self, codename):
        """
        Возвращает красивое название действия.
        """
        action_names = {
            'add': 'Создавать',
            'change': 'Редактировать',
            'delete': 'Удалять',
            'view': 'Просматривать',
        }
        return action_names.get(codename, codename)

    def _get_model_display_name(self, model_name):
        """
        Возвращает красивое название модели.
        """
        model_names = {
            'customuser': 'пользователей',
            'telegramuser': 'Telegram пользователей',
            'telegramadmin': 'Telegram администраторов',
            'djangoadmin': 'Django администраторов',
            'miniappuser': 'Mini App пользователей',
            'post': 'посты',
            'category': 'категории',
            'testimonial': 'отзывы',
            'project': 'проекты',
            'feedbackmessage': 'сообщения',
            'feedbackreply': 'ответы',
            'donation': 'пожертвования',
            'telegramgroup': 'Telegram группы',
            'task': 'задачи',
            'topic': 'темы',
            'webhook': 'вебхуки',
            'socialaccount': 'социальные аккаунты',
            'group': 'группы',
            'permission': 'разрешения',
            'contenttype': 'типы содержимого',
            'session': 'сессии',
            'site': 'сайты',
            'logentry': 'записи журнала',
        }
        return model_names.get(model_name, model_name)


class CustomUserAdmin(UserOverviewMixin, UserAdmin):
    """
    Админ-панель для CustomUser с интеграцией социальных аккаунтов и действием для создания DjangoAdmin.
    """
    model = CustomUser
    list_display = [
        'username', 'email', 'is_active', 'is_staff', 'telegram_id', 
        'subscription_status', 'django_admin_status', 'social_accounts_display', 'created_at'
    ]
    search_fields = ['username', 'email', 'telegram_id']
    list_filter = [
        'is_active', 'is_staff', 'subscription_status', 'language',
        'social_accounts__provider', 'social_accounts__is_active'
    ]
    inlines = [SocialAccountInline]
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Персональная информация', {'fields': ('email', 'telegram_id', 'avatar', 'bio', 'location', 'birth_date', 'website')}),
        ('Социальные сети', {'fields': ('telegram', 'github', 'instagram', 'facebook', 'linkedin', 'youtube')}),
        ('Статистика', {'fields': ('total_points', 'quizzes_completed', 'average_score', 'favorite_category')}),
        ('Настройки', {'fields': ('language', 'is_telegram_user', 'email_notifications', 'is_public', 'theme_preference')}),
        ('Разрешения', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'date_joined', 'deactivated_at', 'last_seen')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'telegram_id', 'password1', 'password2', 'is_active', 'is_staff'),
        }),
    )
    actions = ['make_django_admin', 'remove_django_admin', 'link_social_accounts', 'show_user_overview', 'show_user_details']
    
    def django_admin_status(self, obj):
        """
        Отображает статус Django администратора.
        """
        from django.utils.safestring import mark_safe
        
        # Проверяем, есть ли запись в DjangoAdmin
        django_admin = DjangoAdmin.objects.filter(username=obj.username).first()
        
        if obj.is_staff or obj.is_superuser:
            if django_admin and django_admin.is_active:
                return mark_safe('<span style="color: green;">✅ Django Админ</span>')
            elif django_admin and not django_admin.is_active:
                return mark_safe('<span style="color: orange;">⚠️ Django Админ (неактивен)</span>')
            else:
                return mark_safe('<span style="color: blue;">🔧 Права есть, но не в DjangoAdmin</span>')
        else:
            if django_admin:
                return mark_safe('<span style="color: red;">❌ Django Админ (без прав)</span>')
            else:
                return mark_safe('<span style="color: gray;">👤 Обычный пользователь</span>')
    django_admin_status.short_description = 'Django Админ'
    
    def social_accounts_display(self, obj):
        """
        Отображает социальные аккаунты пользователя.
        """
        accounts = obj.social_accounts.filter(is_active=True)
        if not accounts:
            return '-'
        
        providers = [account.provider for account in accounts]
        if len(providers) > 2:
            return f"{', '.join(providers[:2])} +{len(providers)-2}"
        return ', '.join(providers)
    social_accounts_display.short_description = 'Социальные аккаунты'
    
    def link_social_accounts(self, request, queryset):
        """
        Связывает социальные аккаунты пользователей с существующими системами.
        """
        linked_count = 0
        for user in queryset:
            for social_account in user.social_accounts.filter(is_active=True):
                try:
                    linked_count += social_account.auto_link_existing_users()
                except Exception as e:
                    self.message_user(
                        request, 
                        f"Ошибка при связывании аккаунта {social_account.provider_user_id}: {e}", 
                        level='ERROR'
                    )
        
        self.message_user(request, f"Связано {linked_count} социальных аккаунтов.")
    link_social_accounts.short_description = "Связать социальные аккаунты"

    def make_django_admin(self, request, queryset):
        """
        Создаёт DjangoAdmin из выбранных CustomUser.
        Теперь работает через сигналы - просто выставляет права.
        """
        updated_count = 0
        for user in queryset:
            if not user.is_staff:
                user.is_staff = True
                user.save()  # Сигнал автоматически создаст DjangoAdmin
                updated_count += 1
                self.message_user(
                    request, 
                    f"✅ Пользователь {user.username} получил права staff. DjangoAdmin создан автоматически.",
                    level='SUCCESS'
                )
            else:
                self.message_user(
                    request, 
                    f"ℹ️ Пользователь {user.username} уже имеет права staff.",
                    level='INFO'
                )
        
        if updated_count > 0:
            self.message_user(
                request, 
                f"🎉 {updated_count} пользователей получили права Django администратора.",
                level='SUCCESS'
            )
    make_django_admin.short_description = "Сделать Django-админом"

    def remove_django_admin(self, request, queryset):
        """
        Убирает права Django администратора у выбранных пользователей.
        Удаляет из таблицы DjangoAdmin и обновляет статус в CustomUser.
        """
        removed_count = 0
        for user in queryset:
            if user.is_staff or user.is_superuser:
                # Убираем права
                user.is_staff = False
                user.is_superuser = False
                user.save()  # Сигнал автоматически удалит из DjangoAdmin
                
                # Дополнительно удаляем из DjangoAdmin если запись существует
                try:
                    django_admin = DjangoAdmin.objects.get(username=user.username)
                    django_admin.delete()
                    self.message_user(
                        request, 
                        f"✅ Пользователь {user.username} удален из Django администраторов.",
                        level='SUCCESS'
                    )
                except DjangoAdmin.DoesNotExist:
                    pass
                
                removed_count += 1
            else:
                self.message_user(
                    request, 
                    f"ℹ️ Пользователь {user.username} не является Django администратором.",
                    level='INFO'
                )
        
        if removed_count > 0:
            self.message_user(
                request, 
                f"🗑️ {removed_count} пользователей удалены из Django администраторов.",
                level='SUCCESS'
            )
    remove_django_admin.short_description = "Убрать права Django-админа"


class TelegramUserAdmin(admin.ModelAdmin):
    """
    Админ-панель для TelegramUser.
    """
    list_display = ['telegram_id', 'username', 'first_name', 'last_name', 'subscription_status', 'language', 'is_premium', 'created_at']
    search_fields = ['telegram_id', 'username', 'first_name', 'last_name']
    list_filter = ['subscription_status', 'language', 'is_premium', 'created_at']
    actions = ['remove_user_from_all_channels', 'sync_with_telegram']
    
    def delete_queryset(self, request, queryset):
        """
        Переопределяем стандартное удаление, чтобы использовать нашу логику.
        """
        print(f"=== DEBUG: delete_queryset вызван для {queryset.count()} TelegramUser объектов ===", file=sys.stderr)
        self.remove_user_from_all_channels(request, queryset)
        # После удаления из Telegram, удаляем из базы данных
        super().delete_queryset(request, queryset)
    
    def delete_model(self, request, obj):
        """
        Переопределяем удаление одного объекта.
        """
        print(f"=== DEBUG: delete_model вызван для TelegramUser объекта {obj.id} ===", file=sys.stderr)
        self.remove_user_from_all_channels(request, [obj])
        # После удаления из Telegram, удаляем из базы данных
        super().delete_model(request, obj)

    def sync_with_telegram(self, request, queryset):
        """
        Синхронизирует данные пользователей с Telegram.
        """
        from accounts.telegram_admin_service import TelegramAdminService, run_async_function
        service = TelegramAdminService()
        synced_count = 0
        
        try:
            for user in queryset:
                try:
                    # Получаем актуальные данные пользователя из Telegram
                    user_info = run_async_function(
                        service.bot.get_chat,
                        user.telegram_id
                    )
                    
                    # Обновляем данные пользователя
                    user.username = user_info.username
                    user.first_name = user_info.first_name
                    user.last_name = user_info.last_name
                    user.is_premium = getattr(user_info, 'is_premium', False)
                    user.save()
                    
                    synced_count += 1
                    self.message_user(
                        request, 
                        f"✅ Синхронизирован пользователь {user.username or user.telegram_id}", 
                        level='SUCCESS'
                    )
                except Exception as e:
                    self.message_user(
                        request, 
                        f"❌ Ошибка синхронизации пользователя {user.telegram_id}: {e}", 
                        level='ERROR'
                    )
        finally:
            service.close()
        
        self.message_user(
            request, 
            f"Синхронизировано {synced_count} пользователей из {queryset.count()}"
        )
    sync_with_telegram.short_description = "🔄 Синхронизировать с Telegram"

    def remove_user_from_all_channels(self, request, queryset):
        """
        Полностью удаляет пользователей из всех их каналов (кикает).
        """
        from accounts.telegram_admin_service import TelegramAdminService, run_async_function
        total_removed = 0

        for user in queryset:
            # Получаем все каналы, где пользователь состоит
            channel_ids = [sub.channel.group_id for sub in user.channel_subscriptions.all()]
            if channel_ids:
                service = TelegramAdminService()
                try:
                    success_count, messages = run_async_function(
                        service.remove_user_from_all_channels,
                        user.telegram_id,
                        channel_ids
                    )
                    total_removed += success_count
                    for message in messages:
                        if "успешно" in message:
                            self.message_user(request, message, level='SUCCESS')
                        else:
                            self.message_user(request, message, level='ERROR')
                finally:
                    service.close()
        
        # Удаляем только связи из базы данных (самого пользователя удалит delete_queryset)
        for user in queryset:
            user.channel_subscriptions.all().delete()
        
        self.message_user(
            request,
            f"Удалено {total_removed} пользователей из каналов. Связи в базе данных очищены."
        )
    remove_user_from_all_channels.short_description = "🚫 Удалить из всех каналов (кик)"


class UserChannelSubscriptionAdmin(admin.ModelAdmin):
    """
    Админ-панель для подписок пользователей на каналы.
    """
    list_display = [
        'telegram_user', 'channel', 'subscription_status', 
        'subscribed_at', 'banned_status', 'user_admin_status', 'channel_admin_status'
    ]
    search_fields = [
        'telegram_user__username', 'telegram_user__first_name', 'telegram_user__last_name',
        'channel__group_name', 'channel__group_id'
    ]
    list_filter = [
        'subscription_status', 'subscribed_at', 'unsubscribed_at',
        'telegram_user__is_premium'
    ]
    raw_id_fields = ['telegram_user', 'channel']
    readonly_fields = [
        'subscribed_at', 'unsubscribed_at', 'banned_at', 'banned_until',
        'user_admin_status', 'channel_admin_status', 'user_links', 'banned_status'
    ]
    actions = ['remove_from_channel', 'ban_from_channel', 'unban_from_channel', 'sync_from_bot', 'promote_to_admin']
    
    def delete_queryset(self, request, queryset):
        """
        Переопределяем стандартное удаление, чтобы использовать нашу логику.
        """
        print(f"=== DEBUG: delete_queryset вызван для {queryset.count()} объектов ===", file=sys.stderr)
        self.remove_from_channel(request, queryset)
    
    def delete_model(self, request, obj):
        """
        Переопределяем удаление одного объекта.
        """
        print(f"=== DEBUG: delete_model вызван для объекта {obj.id} ===", file=sys.stderr)
        self.remove_from_channel(request, [obj])
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('telegram_user', 'channel', 'subscription_status')
        }),
        ('Даты', {
            'fields': ('subscribed_at', 'unsubscribed_at'),
            'classes': ('collapse',)
        }),
        ('Дополнительная информация', {
            'fields': ('user_admin_status', 'channel_admin_status', 'user_links'),
            'classes': ('collapse',)
        }),
    )

    def user_admin_status(self, obj):
        """
        Отображает статус админа пользователя.
        """
        if obj.telegram_user:
            # Проверяем, является ли пользователь админом этого канала
            from accounts.models import TelegramAdmin
            admin = TelegramAdmin.objects.filter(
                telegram_id=obj.telegram_user.telegram_id,
                groups__group_id=obj.channel.group_id
            ).first()
            if admin:
                return "✅ Админ канала"
            
            # Проверяем, является ли пользователь Django админом
            from accounts.models import DjangoAdmin
            django_admin = DjangoAdmin.objects.filter(
                username=obj.telegram_user.username
            ).first()
            if django_admin:
                return "✅ Django админ"
        
        return "❌ Не админ"
    user_admin_status.short_description = 'Статус админа'

    def channel_admin_status(self, obj):
        """
        Отображает информацию о канале и его админах.
        """
        if obj.channel:
            # Подсчитываем количество админов канала
            from accounts.models import TelegramAdmin
            admin_count = TelegramAdmin.objects.filter(
                groups__group_id=obj.channel.group_id
            ).count()
            return f"👥 {admin_count} админов"
        return "-"
    channel_admin_status.short_description = 'Админы канала'

    def user_links(self, obj):
        """
        Отображает ссылки на связанные записи пользователя.
        """
        links = []
        
        if obj.telegram_user:
            # Ссылка на TelegramUser
            from django.urls import reverse
            url = reverse('admin:accounts_telegramuser_change', args=[obj.telegram_user.id])
            links.append(f'<a href="{url}">Telegram User</a>')
            
            # Ссылка на TelegramAdmin если есть
            from accounts.models import TelegramAdmin
            admin = TelegramAdmin.objects.filter(
                telegram_id=obj.telegram_user.telegram_id
            ).first()
            if admin:
                url = reverse('admin:accounts_telegramadmin_change', args=[admin.id])
                links.append(f'<a href="{url}">Telegram Admin</a>')
            
            # Ссылка на DjangoAdmin если есть
            from accounts.models import DjangoAdmin
            django_admin = DjangoAdmin.objects.filter(
                username=obj.telegram_user.username
            ).first()
            if django_admin:
                url = reverse('admin:accounts_djangoadmin_change', args=[django_admin.id])
                links.append(f'<a href="{url}">Django Admin</a>')
        
        if not links:
            return '-'
        
        from django.utils.safestring import mark_safe
        return mark_safe(' | '.join(links))
    user_links.short_description = 'Ссылки на пользователя'

    def banned_status(self, obj):
        """
        Показывает статус блокировки пользователя.
        """
        from django.utils.safestring import mark_safe
        from django.utils import timezone
        
        if obj.subscription_status == 'banned':
            if obj.banned_until:
                now = timezone.now()
                if obj.banned_until > now:
                    # Еще заблокирован
                    remaining = obj.banned_until - now
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    return mark_safe(f'<span style="color: red;">🚫 Заблокирован ({hours}ч {minutes}м)</span>')
                else:
                    # Время блокировки истекло
                    return mark_safe('<span style="color: orange;">⚠️ Блокировка истекла</span>')
            else:
                return mark_safe('<span style="color: red;">🚫 Заблокирован</span>')
        else:
            return mark_safe('<span style="color: green;">✅ Активен</span>')
    banned_status.short_description = 'Статус блокировки'

    def remove_from_channel(self, request, queryset):
        """
        Удаляет пользователей из каналов (кикает).
        """
        from accounts.telegram_admin_service import TelegramAdminService, run_async_function
        import logging
        import sys
        import asyncio
        
        # Настраиваем логирование для отладки
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        
        # Выводим в консоль для отладки
        print(f"=== DEBUG: Начинаем массовое удаление {queryset.count()} подписок ===", file=sys.stderr)
        logger.info(f"Начинаем массовое удаление {queryset.count()} подписок")
        
        removed_count = 0
        
        try:
            for subscription in queryset:
                try:
                    print(f"=== DEBUG: Обрабатываем подписку {subscription.id} ===", file=sys.stderr)
                    logger.info(f"Обрабатываем подписку {subscription.id}: пользователь {subscription.telegram_user.telegram_id} в канале {subscription.channel.group_id}")
                    
                    # Проверяем, что у нас есть все необходимые данные
                    if not subscription.channel or not subscription.telegram_user:
                        error_msg = f"❌ Отсутствуют данные для подписки {subscription.id}"
                        print(f"=== DEBUG: {error_msg} ===", file=sys.stderr)
                        logger.error(error_msg)
                        self.message_user(request, error_msg, level='ERROR')
                        continue
                    
                    # Создаем новый сервис для каждой операции
                    service = TelegramAdminService()
                    try:
                        # Удаляем пользователя из канала
                        print(f"=== DEBUG: Вызываем remove_user_from_channel для пользователя {subscription.telegram_user.telegram_id} в канале {subscription.channel.group_id} ===", file=sys.stderr)
                        logger.info(f"Вызываем remove_user_from_channel для пользователя {subscription.telegram_user.telegram_id} в канале {subscription.channel.group_id}")
                        success, message = run_async_function(
                            service.remove_user_from_channel,
                            subscription.channel.group_id,
                            subscription.telegram_user.telegram_id
                        )
                        
                        print(f"=== DEBUG: Результат удаления: success={success}, message={message} ===", file=sys.stderr)
                        logger.info(f"Результат удаления: success={success}, message={message}")
                        
                        if success:
                            removed_count += 1
                            subscription.delete()  # Удаляем подписку из базы данных
                            print(f"=== DEBUG: Подписка {subscription.id} удалена из базы данных ===", file=sys.stderr)
                            logger.info(f"Подписка {subscription.id} удалена из базы данных")
                            self.message_user(
                                request, 
                                f"✅ {message}", 
                                level='SUCCESS'
                            )
                        else:
                            print(f"=== DEBUG: Не удалось удалить пользователя: {message} ===", file=sys.stderr)
                            logger.error(f"Не удалось удалить пользователя: {message}")
                            self.message_user(
                                request, 
                                f"❌ {message}", 
                                level='ERROR'
                            )
                    finally:
                        service.close()
                        
                except Exception as e:
                    error_msg = f"❌ Ошибка удаления пользователя {subscription.telegram_user.telegram_id} из канала {subscription.channel.group_id}: {e}"
                    print(f"=== DEBUG: {error_msg} ===", file=sys.stderr)
                    logger.error(error_msg, exc_info=True)
                    self.message_user(request, error_msg, level='ERROR')
        except Exception as e:
            print(f"=== DEBUG: Общая ошибка: {e} ===", file=sys.stderr)
            logger.error(f"Общая ошибка: {e}", exc_info=True)
        
        print(f"=== DEBUG: Завершено массовое удаление. Удалено {removed_count} из {queryset.count()} ===", file=sys.stderr)
        logger.info(f"Завершено массовое удаление. Удалено {removed_count} из {queryset.count()}")
        
        self.message_user(
            request, 
            f"Удалено {removed_count} пользователей из каналов из {queryset.count()}"
        )
    remove_from_channel.short_description = "🚫 Удалить из канала"

    def sync_from_bot(self, request, queryset):
        """
        Синхронизирует подписки из SQLAlchemy базы данных бота.
        """
        # Здесь можно добавить логику синхронизации
        self.message_user(request, "Функция синхронизации будет реализована позже.")
    sync_from_bot.short_description = "Синхронизировать из бота"

    def ban_from_channel(self, request, queryset):
        """
        Отмечает подписчиков как заблокированных в базе данных.
        """
        from django.utils import timezone
        from datetime import datetime, timedelta
        
        service = TelegramAdminService()
        total_banned = 0
        
        for subscription in queryset:
            if subscription.channel and subscription.telegram_user:
                success, message = run_async_function(
                    service.ban_user_from_channel,
                    subscription.channel.group_id,
                    subscription.telegram_user.telegram_id
                )
                if success:
                    # Обновляем статус в базе данных
                    subscription.subscription_status = 'banned'
                    subscription.banned_at = timezone.now()
                    subscription.banned_until = timezone.now() + timedelta(hours=24)
                    subscription.save()
                    
                    total_banned += 1
                    self.message_user(request, message, level='SUCCESS')
                else:
                    self.message_user(request, message, level='ERROR')
        
        service.close()
        self.message_user(request, f"Заблокировано {total_banned} подписчиков в каналах.")
    ban_from_channel.short_description = "🚫 Заблокировать в системе (24 часа)"

    def unban_from_channel(self, request, queryset):
        """
        Отмечает подписчиков как разблокированных в базе данных.
        """
        service = TelegramAdminService()
        total_unbanned = 0
        
        for subscription in queryset:
            if subscription.channel and subscription.telegram_user:
                success, message = run_async_function(
                    service.unban_user_from_channel,
                    subscription.channel.group_id,
                    subscription.telegram_user.telegram_id
                )
                if success:
                    # Обновляем статус в базе данных
                    subscription.subscription_status = 'active'
                    subscription.banned_at = None
                    subscription.banned_until = None
                    subscription.save()
                    
                    total_unbanned += 1
                    self.message_user(request, message, level='SUCCESS')
                else:
                    self.message_user(request, message, level='ERROR')
        
        service.close()
        self.message_user(request, f"Разблокировано {total_unbanned} подписчиков в каналах.")
    unban_from_channel.short_description = "✅ Разблокировать в системе"

    def promote_to_admin(self, request, queryset):
        """
        Назначает пользователей администраторами в их каналах.
        """
        from accounts.telegram_admin_service import TelegramAdminService, run_async_function
        from accounts.models import TelegramAdmin, TelegramAdminGroup
        from platforms.models import TelegramGroup
        import logging
        logger = logging.getLogger(__name__)
        
        total_promoted = 0
        
        for subscription in queryset:
            user = subscription.telegram_user
            channel = subscription.channel
            
            # Проверяем, не является ли пользователь уже админом этого канала
            existing_admin = TelegramAdmin.objects.filter(
                telegram_id=user.telegram_id,
                groups__group_id=channel.group_id
            ).first()
            
            if existing_admin:
                self.message_user(
                    request, 
                    f"⚠️ Пользователь {user.username or user.telegram_id} уже является админом канала {channel.group_name}", 
                    level='WARNING'
                )
                continue
            
            service = TelegramAdminService()
            try:
                # Назначаем админом в Telegram
                success, message = run_async_function(
                    service.promote_user_to_admin,
                    channel.group_id,
                    user.telegram_id
                )
                
                if success:
                    # Создаем или получаем запись TelegramAdmin
                    admin, created = TelegramAdmin.objects.get_or_create(
                        telegram_id=user.telegram_id,
                        defaults={
                            'username': user.username,
                            'language': user.language,
                            'is_active': True
                        }
                    )
                    
                    # Если запись уже существовала, обновляем данные
                    if not created:
                        admin.username = user.username
                        admin.language = user.language
                        admin.save()
                    
                    # Связываем админа с каналом
                    admin_group, created = TelegramAdminGroup.objects.get_or_create(
                        telegram_admin=admin,
                        telegram_group=channel
                    )
                    
                    # Отправляем сообщение пользователю
                    channel_name = channel.group_name or f"канал {channel.group_id}"
                    
                    # Формируем ссылку на канал
                    if channel.username:
                        channel_link = f"https://t.me/{channel.username}"
                        channel_display = f"<a href='{channel_link}'>{channel_name}</a>"
                    else:
                        # Если нет username, используем просто название
                        channel_display = f"<b>{channel_name}</b>"
                    
                    notification_message = f"""
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
                    
                    # Создаем новый сервис для отправки сообщения
                    message_service = TelegramAdminService()
                    try:
                        message_sent, message_result = run_async_function(
                            message_service.send_message_to_user,
                            user.telegram_id,
                            notification_message
                        )
                        
                        if message_sent:
                            logger.info(f"Уведомление отправлено пользователю {user.telegram_id}")
                        else:
                            logger.warning(f"Не удалось отправить уведомление пользователю {user.telegram_id}: {message_result}")
                    finally:
                        message_service.close()
                    
                    total_promoted += 1
                    
                    self.message_user(
                        request, 
                        f"✅ {message}", 
                        level='SUCCESS'
                    )
                else:
                    self.message_user(
                        request, 
                        f"❌ {message}", 
                        level='ERROR'
                    )
                    
            finally:
                service.close()
        
        self.message_user(
            request, 
            f"Назначено {total_promoted} администраторов из {queryset.count()} подписок"
        )
    promote_to_admin.short_description = "👑 Назначить админом"


class IsAdminFilter(admin.SimpleListFilter):
    """
    Кастомный фильтр для фильтрации админов мини-аппа.
    """
    title = 'Является админом'
    parameter_name = 'is_admin'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Да'),
            ('no', 'Нет'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(
                Q(telegram_admin__isnull=False) | Q(django_admin__isnull=False)
            )
        if self.value() == 'no':
            return queryset.filter(telegram_admin__isnull=True, django_admin__isnull=True)
        return queryset


class MiniAppUserAdmin(admin.ModelAdmin):
    """
    Админ-панель для MiniAppUser.
    """
    list_display = ['telegram_id', 'username', 'full_name', 'language', 'grade', 'is_admin', 'admin_type', 'created_at', 'last_seen']
    search_fields = ['telegram_id', 'username', 'first_name', 'last_name']
    list_filter = ['language', 'grade', IsAdminFilter, 'created_at', 'last_seen']
    readonly_fields = ['created_at', 'last_seen', 'is_admin', 'admin_type', 'full_name']
    raw_id_fields = ['telegram_user', 'telegram_admin', 'django_admin', 'programming_language']
    filter_horizontal = ['programming_languages']
    fieldsets = (
        ('Основная информация', {
            'fields': ('telegram_id', 'username', 'first_name', 'last_name', 'language', 'avatar', 'telegram_photo_url')
        }),
        ('Профессиональная информация', {
            'fields': ('grade', 'programming_language', 'programming_languages', 'gender', 'birth_date')
        }),
        ('Социальные сети', {
            'fields': ('website', 'telegram', 'github', 'instagram', 'facebook', 'linkedin', 'youtube'),
            'classes': ('collapse',)
        }),
        ('Связи с другими пользователями', {
            'fields': ('telegram_user', 'telegram_admin', 'django_admin', 'linked_custom_user'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'last_seen', 'is_admin', 'admin_type', 'full_name'),
            'classes': ('collapse',)
        }),
    )
    actions = ['update_last_seen', 'link_to_existing_users', 'merge_statistics_with_custom_user']

    def update_last_seen(self, request, queryset):
        """
        Обновляет время последнего визита для выбранных пользователей.
        """
        for user in queryset:
            user.update_last_seen()
        self.message_user(request, f"Время последнего визита обновлено для {queryset.count()} пользователей.")
    update_last_seen.short_description = "Обновить время последнего визита"

    def link_to_existing_users(self, request, queryset):
        """
        Автоматически связывает MiniAppUser с существующими пользователями.
        """
        linked_count = 0
        for mini_app_user in queryset:
            try:
                # Пытаемся связать с TelegramUser
                telegram_user = TelegramUser.objects.filter(telegram_id=mini_app_user.telegram_id).first()
                if telegram_user and not mini_app_user.telegram_user:
                    mini_app_user.link_to_telegram_user(telegram_user)
                    linked_count += 1
                
                # Пытаемся связать с TelegramAdmin
                telegram_admin = TelegramAdmin.objects.filter(telegram_id=mini_app_user.telegram_id).first()
                if telegram_admin and not mini_app_user.telegram_admin:
                    mini_app_user.link_to_telegram_admin(telegram_admin)
                    linked_count += 1
                
                # Пытаемся связать с DjangoAdmin (по username)
                if mini_app_user.username:
                    django_admin = DjangoAdmin.objects.filter(username=mini_app_user.username).first()
                    if django_admin and not mini_app_user.django_admin:
                        mini_app_user.link_to_django_admin(django_admin)
                        linked_count += 1
                        
            except Exception as e:
                self.message_user(request, f"Ошибка при связывании пользователя {mini_app_user.telegram_id}: {e}", level='ERROR')
        
        self.message_user(request, f"Связано {linked_count} пользователей.")
    link_to_existing_users.short_description = "Связать с существующими пользователями"

    def merge_statistics_with_custom_user(self, request, queryset):
        """
        Объединяет статистику мини-аппа с основной статистикой CustomUser.
        """
        merged_count = 0
        errors = []
        
        for mini_app_user in queryset:
            try:
                # Ищем CustomUser по telegram_id
                custom_user = CustomUser.objects.filter(telegram_id=mini_app_user.telegram_id).first()
                
                if custom_user:
                    stats_merged = mini_app_user.merge_statistics_with_custom_user(custom_user)
                    merged_count += stats_merged
                    self.message_user(request, f"Объединено {stats_merged} записей статистики для пользователя {mini_app_user.telegram_id}")
                else:
                    errors.append(f"CustomUser с telegram_id {mini_app_user.telegram_id} не найден")
                    
            except Exception as e:
                errors.append(f"Ошибка при объединении статистики для {mini_app_user.telegram_id}: {e}")
        
        if merged_count > 0:
            self.message_user(request, f"Всего объединено {merged_count} записей статистики.")
        
        if errors:
            for error in errors:
                self.message_user(request, error, level='ERROR')
    
    merge_statistics_with_custom_user.short_description = "Объединить статистику с CustomUser"


# Регистрация моделей
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(TelegramUser, TelegramUserAdmin)
admin.site.register(TelegramAdmin, TelegramAdminAdmin)
admin.site.register(DjangoAdmin, DjangoAdminAdmin)
admin.site.register(UserChannelSubscription, UserChannelSubscriptionAdmin)
admin.site.register(MiniAppUser, MiniAppUserAdmin)