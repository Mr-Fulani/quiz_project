# tenants/mixins.py
"""
TenantFilteredAdminMixin — примесь для всех ModelAdmin в системе.

Логика:
    - Superuser → видит и редактирует ВСЁ (без ограничений)
    - Staff (request.user.tenant != None) → видит только записи своего тенанта,
      создаёт записи только в своём тенанте

Использование:
    class TopicAdmin(TenantFilteredAdminMixin, ModelAdmin):
        ...
"""

import logging
from django.contrib.admin import ModelAdmin
from django.forms import HiddenInput
from django.core.exceptions import ImproperlyConfigured
from rest_framework import exceptions

logger = logging.getLogger(__name__)


class TenantFilteredAdminMixin:
    """
    Примесь для Django ModelAdmin.
    Автоматически фильтрует записи и FK-выборки по тенанту текущего пользователя.

    Атрибуты класса:
        tenant_lookup (str): Имя поля для фильтрации. По умолчанию 'tenant'.
            Для моделей без прямого FK указывайте через связь:
            tenant_lookup = 'topic__tenant'  # для Subtopic
            tenant_lookup = 'task__tenant'   # для TaskTranslation
    """

    tenant_lookup: str = 'tenant'  # переопределить в подклассе если нет прямого FK

    # ── Фильтрация queryset ────────────────────────────────────────────────────

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        tenant = getattr(request.user, 'tenant', None)
        if tenant:
            return qs.filter(**{self.tenant_lookup: tenant})
        logger.warning(
            f'[TenantAdmin] Staff user {request.user} has no tenant assigned. '
            f'Returning empty queryset.'
        )
        return qs.none()

    # ── Автоматическое назначение тенанта при создании ────────────────────────

    def save_model(self, request, obj, form, change):
        """
        При сохранении автоматически подставляем тенант, если он не задан.
        """
        if not change:
            # 1. Проверяем, не задан ли уже тенант в объекте
            current_tenant = getattr(obj, 'tenant', None)
            
            # 2. Если не задан, пробуем из разных источников
            if not current_tenant:
                # А) Из middleware (по домену)
                current_tenant = getattr(request, 'tenant', None)
                
            if not current_tenant:
                # Б) Из профиля пользователя
                current_tenant = getattr(request.user, 'tenant', None)

            # 3. Если нашли тенант - присваиваем
            if current_tenant:
                obj.tenant = current_tenant
                logger.info(f"[TenantAdmin] Successfully assigned tenant '{current_tenant.slug}' to {obj}")
            else:
                # Если всё еще нет (например, суперюзер на localhost без привязки)
                # Выбросим понятную ошибку вместо IntegrityError
                logger.error(f"[TenantAdmin] Could not determine tenant for {request.user} on {request.get_host()}")
        
        super().save_model(request, obj, form, change)

    # ── Ограничение FK-выборок по тенанту ────────────────────────────────────

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            tenant = getattr(request.user, 'tenant', None)
            if tenant:
                related_model = db_field.related_model
                if hasattr(related_model, 'tenant'):
                    kwargs['queryset'] = related_model.objects.filter(tenant=tenant)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            tenant = getattr(request.user, 'tenant', None)
            if tenant:
                related_model = db_field.related_model
                if hasattr(related_model, 'tenant'):
                    kwargs['queryset'] = related_model.objects.filter(tenant=tenant)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    # ── Скрытие поля tenant от обычного staff ─────────────────────────────────

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and 'tenant' in form.base_fields:
            form.base_fields['tenant'].widget = HiddenInput()
            form.base_fields['tenant'].required = False
        return form

    # ── Добавляем tenant в fieldsets для superuser ────────────────────────────

    def get_fieldsets(self, request, obj=None):
        """
        Гарантирует, что суперюзер видит поле выбора тенанта, даже если оно 
        явно исключено в fieldsets у конкретной модели.
        """
        fieldsets = list(super().get_fieldsets(request, obj))
        # Проверяем наличие поля 'tenant' в модели
        has_tenant_field = any(f.name == 'tenant' for f in self.model._meta.get_fields())
        
        if request.user.is_superuser and self.tenant_lookup == 'tenant' and has_tenant_field:
            # Ищем, нет ли уже поля tenant
            tenant_present = False
            for name, opts in fieldsets:
                if 'tenant' in opts.get('fields', []):
                    tenant_present = True
                    break
            
            # Если нет, добавляем в самый верх первой секции
            if not tenant_present and fieldsets:
                first_name, first_opts = fieldsets[0]
                first_opts_copy = dict(first_opts)
                fields = list(first_opts_copy.get('fields', []))
                if 'tenant' not in fields:
                    fields.insert(0, 'tenant')
                    first_opts_copy['fields'] = tuple(fields)
                fieldsets[0] = (first_name, first_opts_copy)
        return tuple(fieldsets)

    # ── Добавляем tenant в list_display для superuser ─────────────────────────

    def get_list_display(self, request):
        list_display = list(super().get_list_display(request))
        # Проверяем наличие поля 'tenant' в модели
        has_tenant_field = any(f.name == 'tenant' for f in self.model._meta.get_fields())
        if request.user.is_superuser and has_tenant_field and 'tenant' not in list_display:
            list_display.insert(1, 'tenant')
        return list_display

    # ── Добавляем фильтр по тенанту для superuser ─────────────────────────────

    def get_list_filter(self, request):
        list_filter = list(super().get_list_filter(request))
        # Проверяем наличие поля 'tenant' в модели
        has_tenant_field = any(f.name == 'tenant' for f in self.model._meta.get_fields())
        if request.user.is_superuser and has_tenant_field and 'tenant' not in list_filter:
            list_filter.insert(0, 'tenant')
        return list_filter


class TenantFilteredViewMixin:
    """
    Примесь для Django Rest Framework (DRF) GenericAPIView/ViewSet.
    Автоматически добавляет фильтрацию по тенанту для API ответов.
    Может быть использована во ViewSets.

    Атрибуты:
        tenant_lookup (str): Имя поля, в котором находится ссылка на тенанта (по умолчанию 'tenant').
    """

    tenant_lookup: str = 'tenant'

    def get_queryset(self):
        """
        Фильтрует queryset по тенанту из request.tenant.
        Если тенант не установлен или не найден, возвращает пустой QuerySet (для не-админов).
        Админы-суперпользователи получают полный QuerySet (если необходимо).
        """
        qs = super().get_queryset()
        request = getattr(self, 'request', None)

        if not request:
            return qs.none()

        if request.user and request.user.is_superuser:
            return qs

        tenant = getattr(request, 'tenant', None)
        if tenant:
            return qs.filter(**{self.tenant_lookup: tenant})

        logger.warning(
            f"[TenantFilteredViewMixin] Request from user {request.user} "
            f"on path {request.path} has no tenant. Returning empty queryset."
        )
        return qs.none()

    def perform_create(self, serializer):
        """
        Автоматически подставляет тенант при создании объекта через API.
        """
        request = getattr(self, 'request', None)
        tenant = getattr(request, 'tenant', None) if request else None

        if tenant:
            serializer.save(**{self.tenant_lookup: tenant})
        else:
            # Для суперпользователей без конкретного тенанта может потребоваться выбор
            serializer.save()
