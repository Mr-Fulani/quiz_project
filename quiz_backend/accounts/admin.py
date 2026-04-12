import sys
import logging
from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import BaseInlineFormSet
from django.http import JsonResponse
from django.urls import path
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone

from accounts.models import CustomUser, TelegramUser, TelegramAdmin, TelegramAdminGroup, DjangoAdmin, UserChannelSubscription, MiniAppUser, UserAvatar, Notification
from .telegram_admin_service import TelegramAdminService, run_async_function
import logging
from tenants.mixins import TenantFilteredAdminMixin

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


class TelegramAdminGroupInlineFormSet(BaseInlineFormSet):
    """
    Валидирует добавление администратора в каналы: пользователь обязан быть подписчиком.
    """

    def clean(self):
        """Проверяет каждую связь администратора с каналом."""
        super().clean()

        admin_instance = self.instance
        if not admin_instance or not admin_instance.telegram_id:
            return

        has_errors = False
        service = TelegramAdminService()
        try:
            for form in self.forms:
                if not hasattr(form, "cleaned_data"):
                    continue
                if form.instance.pk or form.cleaned_data.get('DELETE'):
                    continue

                group = form.cleaned_data.get('telegram_group')
                if not group:
                    continue

                member_info = run_async_function(
                    service.get_chat_member,
                    group.group_id,
                    admin_instance.telegram_id
                )

                if not member_info:
                    has_errors = True
                    form.add_error(
                        None,
                        ValidationError(
                            "Не удалось проверить участие пользователя в канале. "
                            "Убедитесь, что бот является администратором канала.",
                            code='membership_check_failed'
                        )
                    )
                    continue

                status = member_info.get('status', 'unknown')
                is_member = member_info.get('is_member', False)
                
                # Разрешаем назначение для создателей и администраторов
                if status in ('creator', 'administrator'):
                    # Создатели и администраторы автоматически валидны, но создаем подписку для истории
                    telegram_user = TelegramUser.objects.filter(telegram_id=admin_instance.telegram_id).first()
                    if telegram_user:
                        UserChannelSubscription.objects.update_or_create(
                            telegram_user=telegram_user,
                            channel=group,
                            defaults={
                                'subscription_status': 'active',
                                'subscribed_at': timezone.now(),
                                'unsubscribed_at': None,
                            }
                        )
                    continue  # Пропускаем дальнейшие проверки для создателей и администраторов

                # Для обычных участников проверяем статус
                if not is_member or status in ('left', 'kicked', 'restricted'):
                    status_display = {
                        'left': 'покинул канал',
                        'kicked': 'заблокирован в канале',
                        'restricted': 'ограничен в канале',
                        'unknown': 'неизвестен'
                    }.get(status, status)
                    
                    has_errors = True
                    form.add_error(
                        None,
                        ValidationError(
                            f"Пользователь {admin_instance.username or admin_instance.telegram_id} "
                            f"не является участником канала {group.group_name or group.group_id}. "
                            f"Текущий статус в Telegram: {status_display}.",
                            code='not_member_in_telegram'
                        )
                    )
                    continue

                # Для обычных участников проверяем локальную подписку
                subscribed = UserChannelSubscription.objects.filter(
                    telegram_user__telegram_id=admin_instance.telegram_id,
                    channel__group_id=group.group_id,
                    subscription_status='active'
                ).exists()

                if not subscribed:
                    telegram_user = TelegramUser.objects.filter(telegram_id=admin_instance.telegram_id).first()
                    if not telegram_user:
                        has_errors = True
                        form.add_error(
                            None,
                            ValidationError(
                                f"Пользователь {admin_instance.username or admin_instance.telegram_id} "
                                f"является участником канала {group.group_name or group.group_id} в Telegram "
                                f"(статус: {status}), но не найден в базе данных. "
                                f"Попросите его выполнить /start в боте и попробуйте снова.",
                                code='telegram_user_missing'
                            )
                        )
                        continue

                    # Автоматически создаем подписку для существующих участников
                    UserChannelSubscription.objects.update_or_create(
                        telegram_user=telegram_user,
                        channel=group,
                        defaults={
                            'subscription_status': 'active',
                            'subscribed_at': timezone.now(),
                            'unsubscribed_at': None,
                        }
                    )
        finally:
            service.close()

        if has_errors:
            raise ValidationError(
                "Назначение отменено: убедитесь, что пользователь состоит в выбранных каналах."
            )


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
    formset = TelegramAdminGroupInlineFormSet


class NotificationAdminForm(forms.ModelForm):
    """Кастомная форма для админки уведомлений."""
    
    class Meta:
        model = Notification
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Убеждаемся, что поле is_read редактируемое
        if 'is_read' in self.fields:
            self.fields['is_read'].widget.attrs.update({'class': 'is-read-checkbox'})
            self.fields['is_read'].required = False
            # Убеждаемся, что поле не в disabled состоянии
            self.fields['is_read'].disabled = False
    
    def clean_is_read(self):
        """Очистка и валидация поля is_read."""
        is_read = self.cleaned_data.get('is_read', False)
        return bool(is_read)


class UserSearchWidget(forms.TextInput):
    """
    Кастомный виджет для поиска пользователя с кнопкой лупы.
    """
    def render(self, name, value, attrs=None, renderer=None):
        html = super().render(name, value, attrs, renderer)
        # Добавляем кнопку с лупой сразу в HTML в контейнере для правильного отображения
        button_html = '''
        <div style="display: inline-block; margin-left: 5px; vertical-align: middle;">
            <button type="button" id="user-search-button" style="padding: 5px 10px; background: #417690; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 14px; line-height: 1;" title="Показать список подписчиков каналов">🔍</button>
        </div>
        <script>
        (function($) {
            if (!$) $ = django.jQuery || jQuery || window.jQuery;
            if (!$) return;
            
            // Глобальная функция для открытия модального окна (будет доступна и для внешнего JS)
            window.openSubscribersModal = function() {
                var $modal = $('#subscribers-modal-widget');
                var modalData = window.telegramAdminModalData = window.telegramAdminModalData || { currentPage: 1 };
                
                // Создаем модальное окно, если его нет
                if (!$modal.length) {
                    $modal = $('<div id="subscribers-modal-widget" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 10000;"><div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; border-radius: 8px; width: 85%; max-width: 900px; max-height: 85vh; overflow: hidden; box-shadow: 0 8px 32px rgba(0,0,0,0.4);"><div style="padding: 20px; border-bottom: 2px solid #417690; background: linear-gradient(135deg, #417690 0%, #3571a3 100%); color: white; display: flex; justify-content: space-between; align-items: center;"><h3 style="margin: 0; font-size: 18px; font-weight: 600;">📋 Список подписчиков каналов</h3><button type="button" class="close-modal-btn" style="background: transparent; border: none; color: white; font-size: 28px; cursor: pointer; padding: 0; width: 32px; height: 32px; line-height: 28px; border-radius: 4px; transition: background 0.2s;">×</button></div><div style="padding: 15px; border-bottom: 1px solid #e0e0e0; background: #f9f9f9;"><input type="text" id="modal-search-input" placeholder="🔍 Поиск по username или ID..." style="width: 100%; padding: 10px 12px; border: 2px solid #ddd; border-radius: 4px; font-size: 14px; transition: border-color 0.2s;"></div><div id="modal-content-widget" style="padding: 0; max-height: 60vh; overflow-y: auto; background: white;"><div style="text-align: center; padding: 40px; color: #666;">Загрузка...</div></div><div id="modal-pagination-widget" style="padding: 15px; border-top: 1px solid #e0e0e0; text-align: center; background: #f9f9f9;"></div></div></div>');
                    $('body').append($modal);
                    
                    $modal.find('.close-modal-btn').on('click', function() { $modal.hide(); });
                    $modal.find('.close-modal-btn').on('mouseenter', function() { $(this).css('background', 'rgba(255,255,255,0.2)'); });
                    $modal.find('.close-modal-btn').on('mouseleave', function() { $(this).css('background', 'transparent'); });
                    $modal.on('click', function(e) { if ($(e.target).is('#subscribers-modal-widget')) $modal.hide(); });
                    
                    $('#modal-search-input').on('focus', function() { $(this).css({'borderColor': '#417690', 'outline': 'none'}); });
                    $('#modal-search-input').on('blur', function() { $(this).css('borderColor', '#ddd'); });
                    $('#modal-search-input').on('input', function() {
                        modalData.currentPage = 1;
                        loadUsers();
                    });
                }
                
                function loadUsers() {
                    var query = $('#modal-search-input').val().trim();
                    $('#modal-content-widget').html('<div style="text-align: center; padding: 20px; color: #999;">Загрузка...</div>');
                    
                    $.ajax({
                        url: '/admin/accounts/telegramadmin/list-subscribers/',
                        data: { page: modalData.currentPage, search: query },
                        dataType: 'json',
                        success: function(data) {
                            if (!data.users || data.users.length === 0) {
                                $('#modal-content-widget').html('<div style="text-align: center; padding: 40px; color: #666; font-size: 14px;">🔍 Подписчики не найдены. Попробуйте изменить поисковый запрос.</div>');
                                $('#modal-pagination-widget').html('');
                                return;
                            }
                            
                            var html = '<table style="width: 100%; border-collapse: collapse; font-size: 14px; background: white;"><thead><tr style="background: #f8f9fa; border-bottom: 2px solid #417690;"><th style="padding: 12px 10px; text-align: left; font-weight: 600; color: #333; border-bottom: 2px solid #417690;">ID</th><th style="padding: 12px 10px; text-align: left; font-weight: 600; color: #333; border-bottom: 2px solid #417690;">Имя</th><th style="padding: 12px 10px; text-align: left; font-weight: 600; color: #333; border-bottom: 2px solid #417690;">Username</th><th style="padding: 12px 10px; text-align: center; font-weight: 600; color: #333; border-bottom: 2px solid #417690;">Действие</th></tr></thead><tbody>';
                            data.users.forEach(function(user) {
                                var name = (user.first_name || '') + ' ' + (user.last_name || '');
                                html += '<tr style="border-bottom: 1px solid #e0e0e0; background: white;"><td style="padding: 12px 10px; color: #000; font-weight: 500;">' + user.telegram_id + '</td><td style="padding: 12px 10px; color: #000;">' + (name.trim() || '<span style="color: #999;">—</span>') + '</td><td style="padding: 12px 10px; color: #417690; font-weight: 500;">' + (user.username ? '@' + user.username : '<span style="color: #999;">—</span>') + '</td><td style="padding: 12px 10px; text-align: center;"><button class="select-user-btn" data-id="' + user.telegram_id + '" data-username="' + (user.username || '') + '" data-name="' + (name.trim() || '') + '" data-lang="' + (user.language || 'ru') + '" style="background: #417690; color: white; border: none; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s; box-shadow: 0 2px 4px rgba(65,118,144,0.2);">Выбрать</button></td></tr>';
                            });
                            html += '</tbody></table>';
                            $('#modal-content-widget').html(html);
                            
                            $('.select-user-btn').on('click', function() {
                                var id = $(this).data('id');
                                var username = $(this).data('username');
                                var name = $(this).data('name');
                                var lang = $(this).data('lang');
                                
                                $('#id_telegram_id').val(id);
                                $('#id_username').val(username);
                                $('#id_language').val(lang);
                                $('#id_user_search').val(id + ' (@' + (username || 'без username') + ')');
                                $modal.hide();
                            }).on('mouseenter', function() {
                                $(this).css({
                                    'background': '#3571a3',
                                    'boxShadow': '0 3px 6px rgba(65,118,144,0.3)',
                                    'transform': 'translateY(-1px)'
                                });
                            }).on('mouseleave', function() {
                                $(this).css({
                                    'background': '#417690',
                                    'boxShadow': '0 2px 4px rgba(65,118,144,0.2)',
                                    'transform': 'translateY(0)'
                                });
                            });
                            
                            if (data.total > data.per_page) {
                                var pagHtml = '';
                                if (data.page > 1) pagHtml += '<button id="prev-btn" style="margin-right: 10px; padding: 8px 16px; background: #417690; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s; box-shadow: 0 2px 4px rgba(65,118,144,0.2);">← Назад</button>';
                                pagHtml += '<span style="margin: 0 15px; color: #333; font-size: 14px; font-weight: 500;">Страница ' + data.page + ' из ' + Math.ceil(data.total / data.per_page) + ' (всего: ' + data.total + ')</span>';
                                if (data.has_more) pagHtml += '<button id="next-btn" style="margin-left: 10px; padding: 8px 16px; background: #417690; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s; box-shadow: 0 2px 4px rgba(65,118,144,0.2);">Вперёд →</button>';
                                $('#modal-pagination-widget').html(pagHtml);
                                
                                $('#prev-btn').on('click', function() { if (modalData.currentPage > 1) { modalData.currentPage--; loadUsers(); } })
                                .on('mouseenter', function() { $(this).css({'background': '#3571a3', 'boxShadow': '0 3px 6px rgba(65,118,144,0.3)', 'transform': 'translateY(-1px)'}); })
                                .on('mouseleave', function() { $(this).css({'background': '#417690', 'boxShadow': '0 2px 4px rgba(65,118,144,0.2)', 'transform': 'translateY(0)'}); });
                                
                                $('#next-btn').on('click', function() { if (data.has_more) { modalData.currentPage++; loadUsers(); } })
                                .on('mouseenter', function() { $(this).css({'background': '#3571a3', 'boxShadow': '0 3px 6px rgba(65,118,144,0.3)', 'transform': 'translateY(-1px)'}); })
                                .on('mouseleave', function() { $(this).css({'background': '#417690', 'boxShadow': '0 2px 4px rgba(65,118,144,0.2)', 'transform': 'translateY(0)'}); });
                            } else {
                                $('#modal-pagination-widget').html('<span style="color: #333; font-size: 14px; font-weight: 500;">Всего найдено: ' + data.total + ' подписчик' + (data.total === 1 ? '' : data.total < 5 ? 'а' : 'ов') + '</span>');
                            }
                        },
                        error: function() {
                            $('#modal-content-widget').html('<div style="text-align: center; padding: 40px; color: #dc3545; font-size: 14px; font-weight: 500;">❌ Ошибка загрузки списка подписчиков</div>');
                        }
                    });
                }
                
                modalData.currentPage = 1;
                $modal.show();
                loadUsers();
            };
            
            // Ждем загрузки DOM и jQuery
            function initButton() {
                if (typeof $ !== 'undefined') {
                    $('#user-search-button').on('click', function(e) {
                        e.preventDefault();
                        window.openSubscribersModal();
                    });
                } else {
                    setTimeout(initButton, 100);
                }
            }
            
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initButton);
            } else {
                initButton();
            }
        })(django.jQuery || jQuery || window.jQuery);
        </script>
        '''
        return mark_safe(html + button_html)


class TelegramAdminForm(forms.ModelForm):
    """
    Кастомная форма для TelegramAdmin с поиском пользователей.
    """
    user_search = forms.CharField(
        label='🔍 Поиск пользователя',
        required=False,
        help_text='Введите Telegram ID или @username для поиска, или нажмите на лупу для просмотра списка подписчиков каналов.',
        widget=UserSearchWidget(attrs={
            'placeholder': 'Введите Telegram ID (например: 123456789) или @username',
            'class': 'vTextField',
            'style': 'width: 400px;',
            'autocomplete': 'off',
            'id': 'id_user_search'
        })
    )
    
    class Meta:
        model = TelegramAdmin
        fields = ['telegram_id', 'username', 'language', 'is_active', 'photo']
        widgets = {
            'telegram_id': forms.NumberInput(attrs={'class': 'vIntegerField'}),
            'username': forms.TextInput(attrs={'class': 'vTextField'}),
            'language': forms.TextInput(attrs={'class': 'vTextField'}),
            'photo': forms.TextInput(attrs={'class': 'vTextField'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Если редактируем существующего админа, показываем его данные
        if self.instance.pk:
            self.fields['user_search'].initial = f"{self.instance.telegram_id} ({self.instance.username or 'без username'})"
            self.fields['user_search'].widget.attrs['readonly'] = True
            self.fields['user_search'].widget.attrs['style'] = 'width: 300px; background-color: #f5f5f5;'
    
    class Media:
        # JS файл отключен, так как вся логика встроена в виджет UserSearchWidget
        pass
        # js = ('admin/js/telegram_admin_search.js',)


class TelegramAdminAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    """
    Админ-панель для TelegramAdmin с интеграцией Telegram Bot API и поиском пользователей.
    """
    form = TelegramAdminForm
    list_display = ['telegram_id', 'username', 'language', 'is_active', 'photo', 'group_count']
    search_fields = ['telegram_id', 'username']
    list_filter = ['is_active', 'language']
    inlines = [TelegramAdminGroupInline]
    fieldsets = (
        ('Поиск пользователя', {
            'fields': ('user_search',),
            'description': 'Используйте поле поиска для автоматического заполнения данных пользователя'
        }),
        ('Основная информация', {
            'fields': ('telegram_id', 'username', 'language', 'photo', 'is_active')
        }),
    )
    actions = [
        'make_active', 'make_inactive', 
        'remove_admin_rights_from_all_channels',
        'delete_admin_completely', 'check_bot_permissions_in_channels'
    ]
    
    def get_urls(self):
        """Добавляем URL для AJAX поиска пользователей."""
        urls = super().get_urls()
        custom_urls = [
            path('search-user/', self.admin_site.admin_view(self.search_user_view), name='accounts_telegramadmin_search_user'),
            path('list-subscribers/', self.admin_site.admin_view(self.list_subscribers_view), name='accounts_telegramadmin_list_subscribers'),
        ]
        return custom_urls + urls
    
    def search_user_view(self, request):
        """
        AJAX endpoint для поиска пользователя по telegram_id или username.
        Ищет в TelegramUser, MiniAppUser, CustomUser.
        """
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse({'error': 'Пустой запрос'}, status=400)
        
        results = []
        
        # Удаляем @ если есть
        query_clean = query.lstrip('@')
        
        # Пытаемся понять, это ID или username
        try:
            telegram_id = int(query_clean)
            # Поиск по ID
            # TelegramUser
            telegram_users = TelegramUser.objects.filter(telegram_id=telegram_id)[:5]
            for user in telegram_users:
                results.append({
                    'telegram_id': user.telegram_id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'language': user.language or 'ru',
                    'source': 'TelegramUser'
                })
            
            # MiniAppUser
            mini_app_users = MiniAppUser.objects.filter(telegram_id=telegram_id)[:5]
            for user in mini_app_users:
                results.append({
                    'telegram_id': user.telegram_id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'language': user.language or 'ru',
                    'photo': user.telegram_photo_url or '',
                    'source': 'MiniAppUser'
                })
            
            # CustomUser
            custom_users = CustomUser.objects.filter(telegram_id=telegram_id)[:5]
            for user in custom_users:
                results.append({
                    'telegram_id': user.telegram_id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'language': user.language or 'ru',
                    'source': 'CustomUser'
                })
        except ValueError:
            # Поиск по username
            telegram_users = TelegramUser.objects.filter(username__icontains=query_clean)[:5]
            for user in telegram_users:
                results.append({
                    'telegram_id': user.telegram_id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'language': user.language or 'ru',
                    'source': 'TelegramUser'
                })
            
            mini_app_users = MiniAppUser.objects.filter(username__icontains=query_clean)[:5]
            for user in mini_app_users:
                results.append({
                    'telegram_id': user.telegram_id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'language': user.language or 'ru',
                    'photo': user.telegram_photo_url or '',
                    'source': 'MiniAppUser'
                })
            
            custom_users = CustomUser.objects.filter(username__icontains=query_clean)[:5]
            for user in custom_users:
                if user.telegram_id:
                    results.append({
                        'telegram_id': user.telegram_id,
                        'username': user.username or '',
                        'first_name': user.first_name or '',
                        'last_name': user.last_name or '',
                        'language': user.language or 'ru',
                        'source': 'CustomUser'
                    })
        
        # Удаляем дубликаты по telegram_id
        seen_ids = set()
        unique_results = []
        for result in results:
            if result['telegram_id'] not in seen_ids:
                seen_ids.add(result['telegram_id'])
                unique_results.append(result)
        
        return JsonResponse({'results': unique_results[:10]})
    
    def list_subscribers_view(self, request):
        """
        AJAX endpoint для получения списка подписчиков каналов с пагинацией.
        Возвращает последних активных подписчиков для производительности.
        """
        page = int(request.GET.get('page', 1))
        per_page = 50  # Лимит для производительности
        search_query = request.GET.get('search', '').strip()
        
        # Получаем уникальных пользователей из подписок (только активные подписки)
        subscriptions = UserChannelSubscription.objects.filter(
            subscription_status='active'
        ).select_related('telegram_user').order_by('-subscribed_at')
        
        # Если есть поиск, фильтруем по username или telegram_id
        if search_query:
            try:
                telegram_id = int(search_query.lstrip('@'))
                subscriptions = subscriptions.filter(telegram_user__telegram_id=telegram_id)
            except ValueError:
                subscriptions = subscriptions.filter(
                    Q(telegram_user__username__icontains=search_query) |
                    Q(telegram_user__first_name__icontains=search_query)
                )
        
        # Получаем уникальных пользователей (убираем дубликаты по telegram_id)
        # Используем эффективную пагинацию: получаем только нужную страницу
        seen_ids = set()
        unique_users = []
        
        # Ограничение для производительности: максимум 2000 подписок для обработки
        max_subscriptions = 2000
        subscriptions_slice = subscriptions[:max_subscriptions]
        
        # Собираем уникальных пользователей с учетом пагинации
        # Нам нужно получить достаточно для текущей страницы + немного для учета дубликатов
        needed_for_page = page * per_page + per_page  # Немного больше для учета дубликатов
        
        for subscription in subscriptions_slice:
            user = subscription.telegram_user
            if user.telegram_id not in seen_ids:
                seen_ids.add(user.telegram_id)
                unique_users.append({
                    'telegram_id': user.telegram_id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'language': user.language or 'ru',
                    'source': 'TelegramUser',
                    'subscribed_at': subscription.subscribed_at.strftime('%d.%m.%Y %H:%M') if subscription.subscribed_at else ''
                })
                # Если собрали достаточно для текущей страницы + следующих, можно остановиться
                if len(unique_users) >= needed_for_page:
                    break
        
        # Общее количество (ограничено для производительности)
        total = len(unique_users)
        if len(subscriptions_slice) == max_subscriptions:
            # Если достигли лимита, указываем что может быть больше
            total = min(len(unique_users), 1000)  # Приблизительное число
        
        # Пагинация
        start = (page - 1) * per_page
        end = start + per_page
        paginated_users = unique_users[start:end]
        
        return JsonResponse({
            'users': paginated_users,
            'total': total,
            'page': page,
            'per_page': per_page,
            'has_more': end < total
        })

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


class DjangoAdminAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    tenant_lookup = 'tenant'
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


class CustomUserAdmin(TenantFilteredAdminMixin, UserOverviewMixin, UserAdmin):
    """
    Админ-панель для CustomUser с интеграцией социальных аккаунтов и действием для создания DjangoAdmin.
    """
    model = CustomUser
    list_display = [
        'display_name', 'email', 'is_active', 'is_staff', 'telegram_id', 
        'subscription_status', 'django_admin_status', 'social_accounts_display', 'created_at'
    ]
    search_fields = ['username', 'email', 'telegram_id', 'first_name', 'last_name']
    list_filter = [
        'is_active', 'is_staff', 'subscription_status', 'language',
        'social_accounts__provider', 'social_accounts__is_active'
    ]
    inlines = [SocialAccountInline]
    
    fieldsets = (
        (None, {
            'fields': ('username', 'password'),
            'description': 'Логин (username) используется для входа в систему, а не для отображения имени. Имя пользователя указывается в полях "Имя" и "Фамилия" ниже.'
        }),
        ('Мультитенантность', {
            'fields': ('tenant',),
            'description': 'Укажите тенант, чтобы ограничить доступ этого пользователя (и его данные) только конкретным сайтом.'
        }),
        ('Персональная информация', {'fields': ('first_name', 'last_name', 'email', 'telegram_id', 'avatar', 'bio', 'location', 'birth_date', 'website')}),
        ('Социальные сети', {'fields': ('telegram', 'github', 'instagram', 'facebook', 'linkedin', 'youtube')}),
        ('Статистика', {'fields': ('total_points', 'quizzes_completed', 'average_score', 'favorite_category')}),
        ('Настройки', {'fields': ('language', 'is_telegram_user', 'email_notifications', 'is_public', 'theme_preference')}),
        ('Разрешения', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'date_joined', 'deactivated_at', 'last_seen')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'telegram_id', 'password1', 'password2', 'tenant', 'is_active', 'is_staff'),
        }),
    )
    actions = ['make_django_admin', 'remove_django_admin', 'link_social_accounts', 'show_user_overview', 'show_user_details']
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Переопределяем форму для добавления help_text к полю username.
        """
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['username'].help_text = 'Логин для входа в систему (не имя пользователя). Используется для авторизации. Имя пользователя указывается в полях "Имя" и "Фамилия" ниже.'
        form.base_fields['username'].label = 'Логин (username)'
        return form
    
    def get_queryset(self, request):
        """
        Переопределяем queryset чтобы гарантировать свежие данные из БД.
        """
        qs = super().get_queryset(request)
        # Не используем only() чтобы загрузить все поля
        return qs
    
    def display_name(self, obj):
        """
        Отображает имя пользователя через get_display_name().
        ПРИНУДИТЕЛЬНО обновляем объект из БД перед вызовом метода.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Обновляем объект из БД чтобы получить свежие данные
        old_name = obj.get_display_name()
        obj.refresh_from_db(fields=['first_name', 'last_name', 'email', 'username'])
        new_name = obj.get_display_name()
        
        logger.info(f"=== DEBUG admin display_name: User {obj.id} ({obj.username}) - first_name={obj.first_name}, old={old_name}, new={new_name}")
        
        return new_name
    display_name.short_description = 'Имя'
    display_name.admin_order_field = 'first_name'
    
    def save_model(self, request, obj, form, change):
        """
        Сохраняет модель CustomUser и синхронизирует данные с MiniAppUser.
        
        После сохранения в админке автоматически синхронизирует все поля с MiniAppUser
        если есть связь через mini_app_profile.
        """
        # Сохраняем объект (сигнал post_save автоматически синхронизирует данные)
        super().save_model(request, obj, form, change)
        
        # Обновляем объект из БД чтобы получить свежие данные
        obj.refresh_from_db()
        
        # Явная синхронизация после сохранения в админке
        # Это гарантирует, что данные синхронизируются даже если сигнал не сработал
        if change and hasattr(obj, 'mini_app_profile') and obj.mini_app_profile:
            try:
                mini_app_user = obj.mini_app_profile
                fields_updated = False
                changed_fields = []
                
                # Список полей для синхронизации
                social_fields = ['github', 'instagram', 'facebook', 'linkedin', 'youtube', 'website']
                basic_fields = ['first_name', 'last_name', 'bio', 'location', 'birth_date', 'language']
                
                # Синхронизируем поля социальных сетей
                for field in social_fields:
                    custom_user_value = getattr(obj, field, None)
                    mini_app_value = getattr(mini_app_user, field, None)
                    
                    # Нормализуем значения для сравнения
                    if isinstance(custom_user_value, str):
                        custom_user_value = custom_user_value.strip()
                    if isinstance(mini_app_value, str):
                        mini_app_value_normalized = mini_app_value.strip()
                    else:
                        mini_app_value_normalized = mini_app_value
                    
                    # Если в CustomUser есть значение и оно отличается - обновляем
                    if custom_user_value:
                        if not mini_app_value_normalized or mini_app_value_normalized != custom_user_value:
                            setattr(mini_app_user, field, custom_user_value)
                            changed_fields.append(field)
                            fields_updated = True
                    # Если в CustomUser поле пустое, а в MiniAppUser есть значение - очищаем
                    elif mini_app_value_normalized:
                        setattr(mini_app_user, field, '')
                        changed_fields.append(field)
                        fields_updated = True
                
                # Синхронизируем базовые поля
                for field in basic_fields:
                    custom_user_value = getattr(obj, field, None)
                    mini_app_value = getattr(mini_app_user, field, None)
                    
                    if field in ['first_name', 'last_name', 'bio', 'location', 'language']:
                        if custom_user_value and custom_user_value.strip():
                            if not mini_app_value or mini_app_value.strip() != custom_user_value.strip():
                                setattr(mini_app_user, field, custom_user_value)
                                changed_fields.append(field)
                                fields_updated = True
                    elif field == 'birth_date':
                        if custom_user_value:
                            if not mini_app_value or mini_app_value != custom_user_value:
                                setattr(mini_app_user, field, custom_user_value)
                                changed_fields.append(field)
                                fields_updated = True
                
                # Синхронизируем avatar
                if obj.avatar:
                    if not mini_app_user.avatar or mini_app_user.avatar != obj.avatar:
                        mini_app_user.avatar = obj.avatar
                        changed_fields.append('avatar')
                        fields_updated = True
                
                if fields_updated and changed_fields:
                    # Используем update_fields чтобы избежать рекурсии
                    mini_app_user.save(update_fields=changed_fields)
                    logger.info(f"✅ Синхронизированы поля для MiniAppUser (telegram_id={mini_app_user.telegram_id}) из CustomUser (id={obj.id}, username={obj.username}) в админке: {', '.join(changed_fields)}")
                else:
                    logger.debug(f"Нет изменений для синхронизации MiniAppUser (telegram_id={mini_app_user.telegram_id}) из CustomUser (id={obj.id})")
            except Exception as e:
                logger.warning(f"Ошибка при синхронизации CustomUser -> MiniAppUser в админке: {e}")
    
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


class TelegramUserAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
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


class UserChannelSubscriptionAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    """
    Админ-панель для подписок пользователей на каналы.
    """
    tenant_lookup = 'telegram_user__tenant'
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


class UserAvatarInline(admin.TabularInline):
    """
    Inline-форма для отображения аватарок пользователя Mini App.
    
    Позволяет просматривать, редактировать и удалять аватарки
    прямо из админки пользователя.
    """
    model = UserAvatar
    extra = 0
    max_num = 3
    verbose_name = "Аватарка"
    verbose_name_plural = "Аватарки пользователя (до 3)"
    
    fields = ['avatar_preview', 'image', 'order', 'is_gif', 'created_at']
    readonly_fields = ['avatar_preview', 'is_gif', 'created_at']
    ordering = ['order']
    
    def avatar_preview(self, obj):
        """
        Отображает миниатюру аватарки в inline.
        
        Returns:
            HTML с тегом img для миниатюры
        """
        from django.utils.safestring import mark_safe
        
        if obj.image:
            # Для GIF показываем анимированную версию
            if obj.is_gif:
                return mark_safe(
                    f'<img src="{obj.image.url}" '
                    f'style="width: 80px; height: 80px; object-fit: cover; border-radius: 8px; border: 2px solid #00ff00;" '
                    f'alt="Avatar" />'
                )
            else:
                return mark_safe(
                    f'<img src="{obj.image.url}" '
                    f'style="width: 80px; height: 80px; object-fit: cover; border-radius: 8px; border: 2px solid #4CAF50;" '
                    f'alt="Avatar" />'
                )
        return mark_safe('<span style="color: #999;">Нет изображения</span>')
    
    avatar_preview.short_description = 'Миниатюра'


class UserAvatarAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    """
    Админ-панель для управления аватарками пользователей Mini App.
    
    Позволяет модераторам просматривать, редактировать и удалять
    аватарки всех пользователей.
    """
    tenant_lookup = 'user__tenant'
    list_display = ['id', 'avatar_thumbnail', 'user_link', 'order', 'file_type', 'file_size_display', 'created_at']
    list_display_links = ['id', 'avatar_thumbnail']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'user__telegram_id']
    list_filter = ['created_at', 'order']
    readonly_fields = ['avatar_large_preview', 'is_gif', 'file_size_display', 'created_at', 'image_dimensions']
    raw_id_fields = ['user']
    ordering = ['-created_at', 'user', 'order']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'image', 'avatar_large_preview')
        }),
        ('Настройки', {
            'fields': ('order',)
        }),
        ('Информация о файле', {
            'fields': ('is_gif', 'file_size_display', 'image_dimensions', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['reorder_avatars', 'delete_selected_avatars']
    
    def avatar_thumbnail(self, obj):
        """
        Отображает миниатюру аватарки в списке.
        
        Args:
            obj: Объект UserAvatar
            
        Returns:
            HTML с тегом img для миниатюры
        """
        from django.utils.safestring import mark_safe
        
        if obj.image:
            gif_badge = '🎬 ' if obj.is_gif else ''
            border_color = '#00ff00' if obj.is_gif else '#4CAF50'
            
            return mark_safe(
                f'{gif_badge}<img src="{obj.image.url}" '
                f'style="width: 50px; height: 50px; object-fit: cover; border-radius: 8px; border: 2px solid {border_color};" '
                f'alt="Avatar" />'
            )
        return mark_safe('<span style="color: #999;">—</span>')
    
    avatar_thumbnail.short_description = 'Аватарка'
    
    def avatar_large_preview(self, obj):
        """
        Отображает большую превью аватарки в форме редактирования.
        
        Args:
            obj: Объект UserAvatar
            
        Returns:
            HTML с большим изображением
        """
        from django.utils.safestring import mark_safe
        
        if obj.image:
            file_type = 'GIF' if obj.is_gif else 'Изображение'
            return mark_safe(
                f'<div style="margin: 10px 0;">'
                f'<p style="margin: 5px 0; font-weight: bold;">Тип: {file_type}</p>'
                f'<img src="{obj.image.url}" '
                f'style="max-width: 300px; max-height: 300px; border-radius: 12px; border: 3px solid #00ff00; box-shadow: 0 4px 8px rgba(0,255,0,0.2);" '
                f'alt="Avatar Preview" />'
                f'</div>'
            )
        return mark_safe('<p style="color: #999;">Изображение не загружено</p>')
    
    avatar_large_preview.short_description = 'Предпросмотр'
    
    def user_link(self, obj):
        """
        Отображает ссылку на пользователя.
        
        Args:
            obj: Объект UserAvatar
            
        Returns:
            HTML со ссылкой на пользователя
        """
        from django.utils.safestring import mark_safe
        from django.urls import reverse
        
        if obj.user:
            url = reverse('admin:accounts_miniappuser_change', args=[obj.user.id])
            display_name = obj.user.username or obj.user.full_name or f'ID: {obj.user.telegram_id}'
            return mark_safe(f'<a href="{url}">{display_name}</a>')
        return mark_safe('<span style="color: #999;">—</span>')
    
    user_link.short_description = 'Пользователь'
    
    def file_type(self, obj):
        """
        Отображает тип файла с иконкой.
        
        Args:
            obj: Объект UserAvatar
            
        Returns:
            Строка с типом файла
        """
        if obj.is_gif:
            return '🎬 GIF'
        return '🖼️ Изображение'
    
    file_type.short_description = 'Тип'
    
    def file_size_display(self, obj):
        """
        Отображает размер файла в человеко-читаемом формате.
        
        Args:
            obj: Объект UserAvatar
            
        Returns:
            Строка с размером файла
        """
        if obj.image:
            try:
                size = obj.image.size
                # Конвертируем в KB или MB
                if size < 1024:
                    return f'{size} B'
                elif size < 1024 * 1024:
                    return f'{size / 1024:.1f} KB'
                else:
                    return f'{size / (1024 * 1024):.1f} MB'
            except Exception:
                return '—'
        return '—'
    
    file_size_display.short_description = 'Размер файла'
    
    def image_dimensions(self, obj):
        """
        Отображает размеры изображения.
        
        Args:
            obj: Объект UserAvatar
            
        Returns:
            Строка с размерами изображения
        """
        if obj.image:
            try:
                from PIL import Image
                img = Image.open(obj.image.path)
                return f'{img.width} × {img.height} px'
            except Exception:
                return '—'
        return '—'
    
    image_dimensions.short_description = 'Размеры'
    
    def reorder_avatars(self, request, queryset):
        """
        Автоматически переупорядочивает аватарки для каждого пользователя.
        
        Args:
            request: HTTP запрос
            queryset: Выбранные аватарки
        """
        # Группируем аватарки по пользователям
        users_avatars = {}
        for avatar in queryset:
            if avatar.user_id not in users_avatars:
                users_avatars[avatar.user_id] = []
            users_avatars[avatar.user_id].append(avatar)
        
        updated_count = 0
        for user_id, avatars in users_avatars.items():
            # Сортируем по текущему порядку
            avatars.sort(key=lambda x: x.order)
            # Переупорядочиваем
            for i, avatar in enumerate(avatars):
                if avatar.order != i:
                    avatar.order = i
                    avatar.save()
                    updated_count += 1
        
        self.message_user(
            request,
            f'Переупорядочено {updated_count} аватарок для {len(users_avatars)} пользователей.',
            level='SUCCESS'
        )
    
    reorder_avatars.short_description = '🔢 Переупорядочить аватарки (0, 1, 2)'
    
    def delete_selected_avatars(self, request, queryset):
        """
        Удаляет выбранные аватарки с подтверждением.
        
        Args:
            request: HTTP запрос
            queryset: Выбранные аватарки
        """
        count = queryset.count()
        queryset.delete()
        
        self.message_user(
            request,
            f'Удалено {count} аватарок.',
            level='SUCCESS'
        )
    
    delete_selected_avatars.short_description = '🗑️ Удалить выбранные аватарки'


class MiniAppUserAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    """
    Админ-панель для MiniAppUser.
    """
    list_display = ['telegram_id', 'username', 'full_name', 'language', 'grade', 'avatars_count', 'is_admin', 'admin_type', 'ban_status_display', 'notifications_enabled', 'created_at', 'last_seen']
    search_fields = ['telegram_id', 'username', 'first_name', 'last_name']
    list_filter = ['language', 'grade', 'is_banned', IsAdminFilter, 'notifications_enabled', 'created_at', 'last_seen']
    readonly_fields = ['created_at', 'last_seen', 'is_admin', 'admin_type', 'full_name', 'avatars_preview', 'ban_info_display', 'banned_by_admin_display']
    raw_id_fields = ['telegram_user', 'telegram_admin', 'django_admin', 'programming_language']
    filter_horizontal = ['programming_languages']
    inlines = [UserAvatarInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('telegram_id', 'username', 'first_name', 'last_name', 'language', 'avatar', 'telegram_photo_url')
        }),
        ('Аватарки (до 4: 1 главный + 3 дополнительных)', {
            'fields': ('avatars_preview',),
            'description': 'Главный аватар (оранжевая рамка) + галерея дополнительных аватарок. Редактировать можно в секции "Аватарки пользователя" ниже.'
        }),
        ('Профессиональная информация', {
            'fields': ('grade', 'programming_language', 'programming_languages', 'gender', 'birth_date')
        }),
        ('Социальные сети', {
            'fields': ('website', 'telegram', 'github', 'instagram', 'facebook', 'linkedin', 'youtube'),
            'classes': ('collapse',)
        }),
        ('Настройки', {
            'fields': ('is_profile_public', 'notifications_enabled'),
        }),
        ('🚫 Блокировка', {
            'fields': ('is_banned', 'ban_info_display', 'banned_at', 'banned_until', 'ban_reason', 'banned_by_admin_display'),
            'description': 'Управление блокировкой пользователя за нарушения'
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
    actions = ['update_last_seen', 'link_to_existing_users', 'merge_statistics_with_custom_user', 
               'ban_user_1_hour', 'ban_user_24_hours', 'ban_user_7_days', 'ban_user_permanent', 'unban_user']
    
    def save_model(self, request, obj, form, change):
        """
        Сохраняет модель MiniAppUser и синхронизирует данные с CustomUser.
        
        После сохранения в админке автоматически синхронизирует все поля с CustomUser
        если есть связь через linked_custom_user.
        """
        # Сохраняем объект (сигнал post_save автоматически синхронизирует данные)
        super().save_model(request, obj, form, change)
        
        # Обновляем объект из БД чтобы получить свежие данные
        obj.refresh_from_db()
        
        # Явная синхронизация после сохранения в админке
        # Это гарантирует, что данные синхронизируются даже если сигнал не сработал
        if change and hasattr(obj, 'linked_custom_user') and obj.linked_custom_user:
            try:
                custom_user = obj.linked_custom_user
                fields_updated = False
                changed_fields = []
                
                # Список полей для синхронизации
                social_fields = ['github', 'instagram', 'facebook', 'linkedin', 'youtube', 'website']
                basic_fields = ['first_name', 'last_name', 'bio', 'location', 'birth_date', 'language']
                
                # Синхронизируем поля социальных сетей
                for field in social_fields:
                    mini_app_value = getattr(obj, field, None)
                    custom_user_value = getattr(custom_user, field, None)
                    
                    if mini_app_value and mini_app_value.strip():
                        if not custom_user_value or custom_user_value.strip() != mini_app_value.strip():
                            setattr(custom_user, field, mini_app_value)
                            changed_fields.append(field)
                            fields_updated = True
                
                # Синхронизируем базовые поля
                for field in basic_fields:
                    mini_app_value = getattr(obj, field, None)
                    custom_user_value = getattr(custom_user, field, None)
                    
                    if field in ['first_name', 'last_name', 'bio', 'location', 'language']:
                        if mini_app_value and mini_app_value.strip():
                            if not custom_user_value or custom_user_value.strip() != mini_app_value.strip():
                                setattr(custom_user, field, mini_app_value)
                                changed_fields.append(field)
                                fields_updated = True
                    elif field == 'birth_date':
                        if mini_app_value:
                            if not custom_user_value or custom_user_value != mini_app_value:
                                setattr(custom_user, field, mini_app_value)
                                changed_fields.append(field)
                                fields_updated = True
                
                # Синхронизируем avatar
                if obj.avatar:
                    if not custom_user.avatar or custom_user.avatar != obj.avatar:
                        custom_user.avatar = obj.avatar
                        changed_fields.append('avatar')
                        fields_updated = True
                
                if fields_updated and changed_fields:
                    # Используем update_fields чтобы избежать рекурсии
                    custom_user.save(update_fields=changed_fields)
                    logger.info(f"✅ Синхронизированы поля для CustomUser (id={custom_user.id}, username={custom_user.username}) из MiniAppUser (telegram_id={obj.telegram_id}) в админке: {', '.join(changed_fields)}")
                else:
                    logger.debug(f"Нет изменений для синхронизации CustomUser (id={custom_user.id}) из MiniAppUser (telegram_id={obj.telegram_id})")
            except Exception as e:
                logger.warning(f"Ошибка при синхронизации MiniAppUser -> CustomUser в админке: {e}")
    
    def avatars_count(self, obj):
        """
        Отображает количество аватарок пользователя.
        Учитывает главный аватар и дополнительные аватарки из галереи.
        
        Args:
            obj: Объект MiniAppUser
            
        Returns:
            Строка с количеством аватарок
        """
        from django.utils.safestring import mark_safe
        
        main_avatar = 1 if obj.avatar else 0
        gallery_count = obj.avatars.count()
        total_count = main_avatar + gallery_count
        
        if total_count == 0:
            return mark_safe('<span style="color: #999;">—</span>')
        elif total_count < 4:  # Максимум 4: 1 главный + 3 дополнительных
            return mark_safe(f'<span style="color: #ff9800;">{total_count} / 4</span>')
        else:
            return mark_safe(f'<span style="color: #4CAF50;">{total_count} / 4</span>')
    
    avatars_count.short_description = 'Аватарки'
    
    def avatars_preview(self, obj):
        """
        Отображает превью всех аватарок пользователя.
        Главный аватар отображается первым с пометкой "ГЛАВНЫЙ".
        
        Args:
            obj: Объект MiniAppUser
            
        Returns:
            HTML с превью аватарок
        """
        from django.utils.safestring import mark_safe
        
        html = '<div style="display: flex; gap: 10px; flex-wrap: wrap;">'
        
        # 1. Главный аватар (если есть)
        if obj.avatar and hasattr(obj.avatar, 'url'):
            is_main_gif = obj.avatar.name.lower().endswith('.gif') if obj.avatar.name else False
            gif_badge = '🎬 GIF' if is_main_gif else '👑 ГЛАВНЫЙ'
            border_color = '#ff6b35' if is_main_gif else '#ff9800'  # Оранжевый для главного
            
            html += f'''
                <div style="text-align: center; position: relative;">
                    <img src="{obj.avatar.url}" 
                         style="width: 100px; height: 100px; object-fit: cover; border-radius: 12px; 
                                border: 3px solid {border_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.2);" 
                         alt="Main Avatar" />
                    <p style="margin: 5px 0; font-size: 12px; color: #ff9800; font-weight: bold;">{gif_badge}</p>
                    <div style="position: absolute; top: -5px; right: -5px; background: #ff9800; color: white; 
                                border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; 
                                justify-content: center; font-size: 10px; font-weight: bold;">★</div>
                </div>
            '''
        
        # 2. Дополнительные аватарки из галереи
        avatars = obj.avatars.all().order_by('order')
        for avatar in avatars:
            gif_badge = '🎬 GIF' if avatar.is_gif else f'#{avatar.order + 1}'
            border_color = '#00ff00' if avatar.is_gif else '#4CAF50'
            
            html += f'''
                <div style="text-align: center;">
                    <img src="{avatar.image.url}" 
                         style="width: 100px; height: 100px; object-fit: cover; border-radius: 12px; 
                                border: 3px solid {border_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.2);" 
                         alt="Avatar {avatar.order + 1}" />
                    <p style="margin: 5px 0; font-size: 12px; color: #666;">{gif_badge}</p>
                </div>
            '''
        
        # Если нет ни главного, ни дополнительных аватарок
        if not obj.avatar and not avatars:
            html += '<p style="color: #999; margin: 20px 0;">Аватарки не загружены</p>'
        
        html += '</div>'
        return mark_safe(html)
    
    avatars_preview.short_description = 'Галерея аватарок'

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
    
    def ban_status_display(self, obj):
        """Отображение статуса блокировки в списке."""
        from django.utils.safestring import mark_safe
        
        # Сначала проверяем, не истёк ли бан
        obj.check_ban_expired()
        
        if not obj.is_banned:
            return mark_safe('<span style="color: #28a745; font-weight: bold;">✅ Активен</span>')
        
        from django.utils import timezone
        
        if obj.banned_until is None:
            return mark_safe('<span style="color: #dc3545; font-weight: bold;">🚫 Бан навсегда</span>')
        
        if timezone.now() >= obj.banned_until:
            return mark_safe('<span style="color: #ffc107; font-weight: bold;">⚠️ Бан истёк</span>')
        
        remaining = obj.banned_until - timezone.now()
        hours = int(remaining.total_seconds() // 3600)
        
        if hours > 24:
            days = hours // 24
            return mark_safe(f'<span style="color: #dc3545; font-weight: bold;">🚫 Бан {days} дн.</span>')
        else:
            return mark_safe(f'<span style="color: #fd7e14; font-weight: bold;">🚫 Бан {hours} ч.</span>')
    
    ban_status_display.short_description = 'Статус бана'
    
    def ban_info_display(self, obj):
        """Детальная информация о текущем бане."""
        from django.utils.safestring import mark_safe
        from django.utils import timezone
        
        if not obj.is_banned:
            return mark_safe('<div style="padding: 15px; background: #d4edda; border-left: 4px solid #28a745; border-radius: 4px; color: #155724;"><strong>✅ Пользователь не заблокирован</strong></div>')
        
        # Проверяем, не истёк ли бан
        is_expired = obj.check_ban_expired()
        
        if is_expired:
            return mark_safe('<div style="padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px; color: #856404;"><strong>⚠️ Срок блокировки истёк</strong><br>Пользователь автоматически разблокирован.</div>')
        
        ban_type = 'Перманентный бан' if obj.banned_until is None else f'Заблокирован до {obj.banned_until.strftime("%d.%m.%Y %H:%M")}'
        
        remaining_text = ''
        if obj.banned_until:
            remaining = obj.banned_until - timezone.now()
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            
            if hours > 24:
                days = hours // 24
                remaining_text = f'<br><strong>Осталось:</strong> {days} дн. {hours % 24} ч.'
            else:
                remaining_text = f'<br><strong>Осталось:</strong> {hours} ч. {minutes} мин.'
        
        admin_info = ''
        if obj.banned_by_admin_id:
            try:
                from accounts.models import MiniAppUser
                admin = MiniAppUser.objects.get(telegram_id=obj.banned_by_admin_id)
                admin_name = admin.first_name or admin.username or f'ID {obj.banned_by_admin_id}'
                admin_info = f'<br><strong>Заблокировал:</strong> {admin_name} (@{admin.username or "нет"}, ID: {obj.banned_by_admin_id})'
            except:
                admin_info = f'<br><strong>Заблокировал:</strong> ID {obj.banned_by_admin_id}'
        
        reason_html = f'<br><strong>Причина:</strong> {obj.ban_reason}' if obj.ban_reason else ''
        banned_at = f'<br><strong>Дата блокировки:</strong> {obj.banned_at.strftime("%d.%m.%Y %H:%M")}' if obj.banned_at else ''
        
        return mark_safe(f'''
            <div style="padding: 15px; background: #f8d7da; border-left: 4px solid #dc3545; border-radius: 4px; color: #721c24;">
                <strong>🚫 ПОЛЬЗОВАТЕЛЬ ЗАБЛОКИРОВАН</strong>
                <br><br>
                <strong>Тип блокировки:</strong> {ban_type}
                {remaining_text}
                {reason_html}
                {banned_at}
                {admin_info}
            </div>
        ''')
    
    ban_info_display.short_description = 'Информация о блокировке'
    
    def banned_by_admin_display(self, obj):
        """Отображает информацию об админе, который забанил пользователя."""
        from django.utils.safestring import mark_safe
        
        if not obj.banned_by_admin_id:
            return mark_safe('<span style="color: #999; font-style: italic;">Не указано</span>')
        
        try:
            # Пытаемся найти админа через MiniAppUser
            admin = MiniAppUser.objects.get(telegram_id=obj.banned_by_admin_id)
            admin_name = admin.first_name or admin.username or 'Администратор'
            admin_username = f"@{admin.username}" if admin.username else 'нет username'
            
            return mark_safe(
                f'<a href="/admin/accounts/miniappuser/{admin.id}/change/" target="_blank" style="text-decoration: none; color: #007bff; font-weight: bold;">'
                f'👤 {admin_name} ({admin_username}, ID: {obj.banned_by_admin_id})'
                f'</a>'
            )
        except MiniAppUser.DoesNotExist:
            # Если не нашли в MiniAppUser, просто показываем ID
            return mark_safe(f'<span style="color: #666;">ID: {obj.banned_by_admin_id}</span>')
    
    banned_by_admin_display.short_description = 'Админ, который заблокировал'
    
    def get_admin_telegram_id(self, request):
        """
        Получает telegram_id администратора, который выполняет действие.
        Пытается найти через связи с MiniAppUser, DjangoAdmin, TelegramAdmin.
        
        Returns:
            int or None: Telegram ID админа или None если не найден
        """
        admin_id = None
        
        try:
            # Сначала пробуем получить через linked_custom_user -> MiniAppUser
            if hasattr(request.user, 'mini_app_profile'):
                mini_app_user = request.user.mini_app_profile
                if mini_app_user:
                    admin_id = mini_app_user.telegram_id
            
            # Если не нашли, пробуем через DjangoAdmin
            if not admin_id:
                from accounts.models import DjangoAdmin
                try:
                    django_admin = DjangoAdmin.objects.get(username=request.user.username)
                    if django_admin and hasattr(django_admin, 'mini_app_user') and django_admin.mini_app_user:
                        admin_id = django_admin.mini_app_user.telegram_id
                except DjangoAdmin.DoesNotExist:
                    pass
            
            # Если всё ещё не нашли, пробуем через TelegramAdmin
            if not admin_id:
                from accounts.models import TelegramAdmin
                try:
                    telegram_admin = TelegramAdmin.objects.filter(username=request.user.username).first()
                    if telegram_admin:
                        admin_id = telegram_admin.telegram_id
                except Exception:
                    pass
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Не удалось получить telegram_id админа: {e}")
        
        return admin_id
    
    @admin.action(description='🚫 Забанить на 1 час')
    def ban_user_1_hour(self, request, queryset):
        """Банит пользователей на 1 час."""
        admin_id = self.get_admin_telegram_id(request)
        count = 0
        for user in queryset:
            user.ban_user(
                duration_hours=1,
                reason='Блокировка на 1 час (действие администратора)',
                admin_id=admin_id
            )
            count += 1
        self.message_user(request, f'Заблокировано {count} пользователей на 1 час', messages.SUCCESS)
    
    @admin.action(description='🚫 Забанить на 24 часа')
    def ban_user_24_hours(self, request, queryset):
        """Банит пользователей на 24 часа."""
        admin_id = self.get_admin_telegram_id(request)
        count = 0
        for user in queryset:
            user.ban_user(
                duration_hours=24,
                reason='Блокировка на 24 часа (действие администратора)',
                admin_id=admin_id
            )
            count += 1
        self.message_user(request, f'Заблокировано {count} пользователей на 24 часа', messages.SUCCESS)
    
    @admin.action(description='🚫 Забанить на 7 дней')
    def ban_user_7_days(self, request, queryset):
        """Банит пользователей на 7 дней."""
        admin_id = self.get_admin_telegram_id(request)
        count = 0
        for user in queryset:
            user.ban_user(
                duration_hours=168,  # 7 * 24
                reason='Блокировка на 7 дней (действие администратора)',
                admin_id=admin_id
            )
            count += 1
        self.message_user(request, f'Заблокировано {count} пользователей на 7 дней', messages.SUCCESS)
    
    @admin.action(description='🚫 Перманентный бан')
    def ban_user_permanent(self, request, queryset):
        """Банит пользователей навсегда."""
        admin_id = self.get_admin_telegram_id(request)
        count = 0
        for user in queryset:
            user.ban_user(
                duration_hours=None,
                reason='Перманентная блокировка (действие администратора)',
                admin_id=admin_id
            )
            count += 1
        self.message_user(request, f'Заблокировано {count} пользователей навсегда', messages.WARNING)
    
    @admin.action(description='✅ Разбанить пользователей')
    def unban_user(self, request, queryset):
        """Разбанивает пользователей."""
        count = 0
        for user in queryset:
            if user.is_banned:
                user.unban_user()
                count += 1
        self.message_user(request, f'Разблокировано {count} пользователей', messages.SUCCESS)


# Регистрация моделей
@admin.register(Notification)
class NotificationAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    tenant_lookup = 'user__tenant'
    """
    Админ-панель для уведомлений.
    """
    form = NotificationAdminForm
    list_display = ['id', 'get_recipient_display', 'notification_type', 'title', 'is_read_display', 'sent_to_telegram', 'created_at']
    list_filter = ['notification_type', 'is_admin_notification', 'is_read', 'sent_to_telegram', 'created_at']
    search_fields = ['recipient_telegram_id', 'title', 'message']
    readonly_fields = ['created_at']
    list_per_page = 50
    date_hierarchy = 'created_at'
    list_display_links = ['id', 'title']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('is_admin_notification', 'recipient_telegram_id', 'notification_type', 'title', 'message')
        }),
        ('Связанный объект', {
            'fields': ('related_object_id', 'related_object_type'),
            'classes': ('collapse',)
        }),
        ('Статус', {
            'fields': ('is_read', 'sent_to_telegram', 'created_at'),
            'description': 'Используйте чекбокс "Прочитано" для отметки уведомления как прочитанного.'
        }),
    )
    
    def get_recipient_display(self, obj):
        """Отображает получателя уведомления."""
        if obj.is_admin_notification:
            return "👥 Все админы"
        return obj.recipient_telegram_id or "-"
    get_recipient_display.short_description = "Получатель"
    
    def is_read_display(self, obj):
        """Визуальное отображение статуса прочтения."""
        if obj.is_read:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Прочитано</span>'
            )
        else:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">● Непрочитано</span>'
            )
    is_read_display.short_description = "Статус"
    is_read_display.admin_order_field = 'is_read'
    
    def get_queryset(self, request):
        """Оптимизация запросов."""
        qs = super().get_queryset(request)
        return qs.select_related()
    
    def changelist_view(self, request, extra_context=None):
        """Переопределяем для улучшенного отображения уведомлений."""
        # Убираем автоматический фильтр по умолчанию - показываем все уведомления
        # Пользователь может сам выбрать фильтр через интерфейс
        return super().changelist_view(request, extra_context)
    
    def save_model(self, request, obj, form, change):
        """Сохраняет модель и логирует изменения статуса прочтения."""
        # Сохраняем значение is_read напрямую из формы
        if 'is_read' in form.cleaned_data:
            obj.is_read = form.cleaned_data['is_read']
            logger.debug(f"Установка is_read={obj.is_read} для уведомления {obj.id if obj.pk else 'новое'}")
        
        # Сохраняем объект
        super().save_model(request, obj, form, change)
        
        # Дополнительная проверка сохранения
        if change and obj.pk:
            obj.refresh_from_db()
            logger.debug(f"Уведомление {obj.id} сохранено, is_read={obj.is_read}")
    
    actions = ['mark_as_read', 'mark_as_unread', 'resend_to_telegram']
    
    def mark_as_read(self, request, queryset):
        """Отметить уведомления как прочитанные."""
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} уведомлений отмечено как прочитанные.')
    mark_as_read.short_description = "Отметить как прочитанные"
    
    def mark_as_unread(self, request, queryset):
        """Отметить уведомления как непрочитанные."""
        updated = queryset.update(is_read=False)
        self.message_user(request, f'{updated} уведомлений отмечено как непрочитанные.')
    mark_as_unread.short_description = "Отметить как непрочитанные"
    
    def resend_to_telegram(self, request, queryset):
        """Повторно отправить уведомления в Telegram."""
        from accounts.utils_folder.telegram_notifications import send_telegram_notification_sync
        from accounts.models import MiniAppUser
        from django.db import models as django_models
        
        sent_count = 0
        for notification in queryset:
            if notification.is_admin_notification:
                # Для админских уведомлений отправляем всем админам
                admins = MiniAppUser.objects.filter(
                    notifications_enabled=True
                ).filter(
                    django_models.Q(telegram_admin__isnull=False) |
                    django_models.Q(django_admin__isnull=False)
                ).distinct()
                
                admin_sent = 0
                for admin in admins:
                    success = send_telegram_notification_sync(admin.telegram_id, notification.message)
                    if success:
                        admin_sent += 1
                
                if admin_sent > 0:
                    notification.mark_as_sent()
                    sent_count += 1
            else:
                # Для обычных уведомлений отправляем конкретному пользователю
                if notification.recipient_telegram_id:
                    success = send_telegram_notification_sync(
                        notification.recipient_telegram_id,
                        notification.message
                    )
                    if success:
                        notification.mark_as_sent()
                        sent_count += 1
        
        self.message_user(request, f'Отправлено {sent_count} уведомлений из {queryset.count()}.')
    resend_to_telegram.short_description = "Повторно отправить в Telegram"


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(TelegramUser, TelegramUserAdmin)
admin.site.register(TelegramAdmin, TelegramAdminAdmin)
admin.site.register(DjangoAdmin, DjangoAdminAdmin)
admin.site.register(UserChannelSubscription, UserChannelSubscriptionAdmin)
admin.site.register(MiniAppUser, MiniAppUserAdmin)
admin.site.register(UserAvatar, UserAvatarAdmin)