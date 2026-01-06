# accounts/views.py
import json
import os

from blog.models import Message
from django import forms
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView, PasswordResetView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetCompleteView
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, TemplateView
from tasks.models import TaskStatistics
from django.urls import reverse_lazy, reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from .utils import send_password_reset_email

from .forms import PersonalInfoForm, CustomPasswordResetForm
from .models import CustomUser
import logging

logger = logging.getLogger(__name__)


class CustomLogoutView(LogoutView):
    """
    При логауте перенаправляет на '/' (next_page='/').
    """
    next_page = '/'

    def post(self, request, *args, **kwargs):
        print(f"Logout request: {request.POST}")
        return super().post(request, *args, **kwargs)


class CustomPasswordChangeForm(forms.Form):
    """
    Кастомная форма смены пароля с переводом ошибок на русский.
    """
    old_password = forms.CharField(
        label="Текущий пароль",
        widget=forms.PasswordInput,
        error_messages={'required': 'Поле текущего пароля обязательно.'}
    )
    new_password1 = forms.CharField(
        label="Новый пароль",
        widget=forms.PasswordInput,
        error_messages={'required': 'Поле нового пароля обязательно.'}
    )
    new_password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput,
        error_messages={'required': 'Поле подтверждения пароля обязательно.'}
    )

    error_messages = {
        'password_mismatch': 'Поля нового пароля и подтверждения не совпадают.',
        'password_incorrect': 'Текущий пароль введён неверно.',
        'password_too_short': 'Пароль слишком короткий. Минимальная длина — 8 символов.',
        'password_entirely_numeric': 'Пароль не может состоять только из цифр. Добавьте буквы или символы.',
        'password_too_common': 'Пароль должен содержать буквы, цифры и хотя бы один специальный символ (например, !, @, #).'
    }

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].min_length = 8

    def clean_old_password(self):
        """Валидация текущего пароля."""
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError(self.error_messages['password_incorrect'], code='password_incorrect')
        return old_password

    def clean_new_password2(self):
        """Валидация подтверждения пароля."""
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')
        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError(self.error_messages['password_mismatch'], code='password_mismatch')
        return new_password2

    def clean_new_password1(self):
        """Валидация нового пароля."""
        new_password1 = self.cleaned_data.get('new_password1')
        if new_password1:
            if len(new_password1) < 8:
                raise forms.ValidationError(self.error_messages['password_too_short'], code='password_too_short')
            if new_password1.isdigit():
                raise forms.ValidationError(self.error_messages['password_entirely_numeric'], code='password_entirely_numeric')
            has_letter = any(c.isalpha() for c in new_password1)
            has_digit = any(c.isdigit() for c in new_password1)
            has_symbol = any(not c.isalnum() for c in new_password1)
            if not (has_letter and has_digit and has_symbol):
                raise forms.ValidationError(self.error_messages['password_too_common'], code='password_too_common')
        return new_password1

    def save(self):
        """Сохранение нового пароля."""
        new_password = self.cleaned_data['new_password1']
        self.user.set_password(new_password)
        self.user.save()


@login_required
def change_password(request):
    """
    Обработка формы смены пароля с использованием CustomPasswordChangeForm.
    Поддерживает AJAX и HTML-ответы.
    """
    success = False
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            print("Saving new password")
            form.save()
            update_session_auth_hash(request, form.user)
            success = True
            form = CustomPasswordChangeForm(user=request.user)
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': 'Пароль успешно изменён!'})
            messages.success(request, 'Пароль успешно изменён!')
        else:
            print(f"Password form errors: {form.errors}")
            if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Исправьте ошибки в форме',
                    'errors': form.errors.as_json()
                }, status=400)
    else:
        form = CustomPasswordChangeForm(user=request.user)

    if is_ajax:
        return JsonResponse({'status': 'error', 'message': 'Некорректный запрос'}, status=400)

    return render(request, 'accounts/dashboard.html', {
        'password_form': form,
        'personal_info_form': PersonalInfoForm(instance=request.user, user=request.user),
        'profile_user': request.user,
        'is_owner': True,
        'user_settings': request.user,
        'active_tab': 'security',
        'password_change_success': success
    })


@login_required
def update_personal_info(request):
    """
    Обработка формы PersonalInfoForm или загрузки аватара.
    Возвращает JsonResponse для AJAX-запросов.
    """
    if request.method == 'POST':
        print(f"POST data: {request.POST}")
        print(f"FILES: {request.FILES}")
        user = request.user
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if 'avatar' in request.FILES and 'personal_info' not in request.POST:
            old_avatar = user.avatar
            form = PersonalInfoForm(
                request.POST,
                request.FILES,
                instance=user,
                user=user,
                avatar_only=True
            )
            if form.is_valid():
                if old_avatar and old_avatar.name and old_avatar != form.cleaned_data['avatar']:
                    try:
                        if os.path.isfile(old_avatar.path):
                            os.remove(old_avatar.path)
                    except Exception as e:
                        print(f"Error deleting old avatar: {e}")
                form.save()
                if is_ajax:
                    return JsonResponse({'status': 'success', 'avatar_url': user.get_avatar_url})
                messages.success(request, 'Аватар успешно обновлён!')
                return redirect('accounts:dashboard')
            else:
                print(f"Avatar form errors: {form.errors}")
                if is_ajax:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Недопустимый файл аватара',
                        'errors': form.errors.as_json()
                    }, status=400)
                messages.error(request, 'Недопустимый файл аватара.')
                return redirect('accounts:dashboard')
        else:
            form = PersonalInfoForm(
                request.POST,
                request.FILES,
                instance=user,
                user=user
            )
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Form created with data: {form.data}")
            logger.debug(f"POST data keys: {list(request.POST.keys())}")
            logger.debug(f"POST data values: {dict(request.POST)}")
            
            if form.is_valid():
                logger.debug(f"Form is valid, cleaned data: {form.cleaned_data}")
                try:
                    form.save()
                    logger.info(f"User {user.username} saved with email: {user.email}, first_name: {user.first_name}")
                    if is_ajax:
                        return JsonResponse({'status': 'success', 'avatar_url': user.get_avatar_url})
                    messages.success(request, 'Профиль успешно обновлён!')
                    return redirect('accounts:dashboard')
                except Exception as save_error:
                    logger.error(f"Ошибка при сохранении формы для пользователя {user.username}: {save_error}", exc_info=True)
                    if is_ajax:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Ошибка при сохранении данных: {str(save_error)}',
                            'errors': {}
                        }, status=500)
                    messages.error(request, f'Ошибка при сохранении данных: {str(save_error)}')
                    return redirect('accounts:dashboard')
            else:
                logger.warning(f"Form errors for user {user.username}: {form.errors}")
                logger.debug(f"Form errors as JSON: {form.errors.as_json()}")
                logger.debug(f"Form non_field_errors: {form.non_field_errors()}")
                # Логируем ошибки по каждому полю
                for field, errors in form.errors.items():
                    logger.warning(f"Field '{field}' errors: {errors}")
                if is_ajax:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Исправьте ошибки в форме',
                        'errors': form.errors.as_json()
                    }, status=400)
                messages.error(request, 'Исправьте ошибки в форме.')
                return redirect('accounts:dashboard')
    else:
        form = PersonalInfoForm(instance=request.user, user=request.user)

    return render(request, 'accounts/dashboard.html', {
        'personal_info_form': form,
        'profile_user': request.user,
        'is_owner': True,
        'user_settings': request.user,
        'active_tab': 'personal'
    })


class UserProfileView(DetailView):
    """
    DetailView для профиля пользователя (CustomUser).
    """
    model = CustomUser
    template_name = 'accounts/user_profile.html'
    context_object_name = 'profile_user'
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_queryset(self):
        """Добавляем аннотации для статистики."""
        from django.db.models import Count, Q
        # Не используем only() чтобы гарантировать свежие данные из БД
        return CustomUser.objects.annotate(
            tasks_completed=Count('statistics', filter=Q(statistics__successful=True)),
            total_score=CustomUser.get_rating_annotation()
        )

    def get_context_data(self, **kwargs):
        """
        Определяем, является ли текущий user владельцем профиля (is_owner).
        """
        context = super().get_context_data(**kwargs)
        # ПРИНУДИТЕЛЬНО обновляем объект из БД перед передачей в шаблон
        if self.object:
            self.object.refresh_from_db(fields=['first_name', 'last_name', 'email', 'username'])
        # Проверяем авторизован ли пользователь перед сравнением
        context['is_owner'] = (
            self.request.user.is_authenticated and 
            self.object == self.request.user
        )
        return context


class UserListView(LoginRequiredMixin, ListView):
    """
    Список пользователей (не staff), по 10 на страницу.
    """
    model = CustomUser
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 10

    def get_queryset(self):
        """Фильтрация не-администраторов с аннотацией статистики."""
        from django.db.models import Count, Q
        # Не используем only() чтобы гарантировать свежие данные из БД
        return CustomUser.objects.exclude(is_staff=True).annotate(
            tasks_completed=Count('statistics', filter=Q(statistics__successful=True)),
            total_score=CustomUser.get_rating_annotation()
        ).order_by('-date_joined')
    
    def get_context_data(self, **kwargs):
        """ПРИНУДИТЕЛЬНО обновляем объекты из БД перед передачей в шаблон."""
        context = super().get_context_data(**kwargs)
        if 'users' in context:
            for user in context['users']:
                user.refresh_from_db(fields=['first_name', 'last_name', 'email', 'username'])
        return context


@login_required
def user_list(request):
    """
    Отображение списка активных пользователей (кроме текущего).
    """
    import logging
    logger = logging.getLogger(__name__)
    
    from django.db.models import Count, Q
    # Не используем only() чтобы гарантировать свежие данные из БД
    users_list = CustomUser.objects.filter(is_active=True).exclude(id=request.user.id).annotate(
        tasks_completed=Count('statistics', filter=Q(statistics__successful=True)),
        total_score=CustomUser.get_rating_annotation()
    ).order_by('-last_seen')
    paginator = Paginator(users_list, 12)
    page = request.GET.get('page')
    users = paginator.get_page(page)
    
    # ПРИНУДИТЕЛЬНО обновляем каждый объект из БД перед передачей в шаблон
    # ВАЖНО: refresh_from_db может сбросить аннотированные поля, поэтому обновляем только нужные поля вручную
    for user in users:
        # Получаем свежие данные напрямую из БД
        fresh_data = CustomUser.objects.only('first_name', 'last_name', 'email', 'username').get(pk=user.pk)
        # Обновляем поля, сохраняя аннотированные
        user.first_name = fresh_data.first_name
        user.last_name = fresh_data.last_name
        user.email = fresh_data.email
        old_name = user.get_display_name()
        logger.info(f"=== DEBUG user_list: User {user.id} ({user.username}) - first_name={user.first_name}, get_display_name()={old_name}")
    
    return render(request, 'accounts/user_list.html', {
        'users': users,
        'is_paginated': users.has_other_pages(),
        'page_obj': users
    })


class ProfileView(TemplateView):
    """
    Простейшее отображение профиля.
    """
    template_name = 'accounts/profile.html'

    def get_context_data(self, **kwargs):
        """Добавление текущего пользователя."""
        context = super().get_context_data(**kwargs)
        context['user_profile'] = self.request.user
        return context


@login_required
def dashboard_view(request):
    """
    Личный кабинет (dashboard).
    """
    return profile_view(request, username=request.user.username, is_dashboard=True)


@login_required
def profile_redirect_view(request):
    """
    Редирект с /profile/ на /dashboard/.
    """
    return redirect('accounts:dashboard')


@login_required
def profile_view(request, username, is_dashboard=False):
    """
    Основное представление профиля.
    Если is_dashboard=True, рендерим dashboard.html, иначе profile.html.
    """
    print(f"\nDebug profile view:")
    print(f"Username param: {username}")
    print(f"Current user: {request.user.username}")
    print(f"Is dashboard: {is_dashboard}")

    profile_user = get_object_or_404(CustomUser, username=username)
    is_owner = request.user == profile_user
    template_name = 'accounts/dashboard.html' if is_dashboard else 'accounts/profile.html'

    # Вся логика статистики теперь в модели TaskStatistics
    dashboard_stats = TaskStatistics.get_stats_for_dashboard(profile_user)

    inbox_messages = profile_user.received_messages.all().order_by('-created_at')[:10] if is_owner else []
    sent_messages = profile_user.sent_messages.all().order_by('-created_at')[:10] if is_owner else []
    
    context = {
        'profile_user': profile_user,
        'is_owner': is_owner,
        'inbox_messages': inbox_messages,
        'sent_messages': sent_messages
    }
    context.update(dashboard_stats)

    if is_dashboard:
        context.update({
            'personal_info_form': PersonalInfoForm(instance=profile_user, user=profile_user),
            'user_settings': profile_user
        })

    return render(request, template_name, context)


def get_user_chart_data(user):
    """
    Возвращает данные для графиков: активность, темы, сложность.
    """
    # Активность по дням
    activity_stats = TaskStatistics.objects.filter(
        user=user,
        last_attempt_date__isnull=False
    ).annotate(
        date=TruncDate('last_attempt_date')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    activity_dates = [stat['date'].strftime('%d.%m') for stat in activity_stats]
    activity_data = [stat['count'] for stat in activity_stats]
    
    # Статистика по темам
    category_stats = TaskStatistics.objects.filter(user=user).values(
        'task__topic__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    categories_labels = [stat['task__topic__name'] for stat in category_stats]
    categories_data = [stat['count'] for stat in category_stats]
    
    # Распределение попыток
    attempts = TaskStatistics.objects.filter(user=user).values('attempts').annotate(count=Count('id'))
    attempts_distribution = [0] * 5  # 5 групп: 1, 2-5, 6-10, 11-15, 16+
    
    for attempt in attempts:
        attempts_value = int(attempt['attempts']) if attempt['attempts'] is not None else 0
        if attempts_value == 1:
            attempts_distribution[0] += attempt['count']
        elif 2 <= attempts_value <= 5:
            attempts_distribution[1] += attempt['count']
        elif 6 <= attempts_value <= 10:
            attempts_distribution[2] += attempt['count']
        elif 11 <= attempts_value <= 15:
            attempts_distribution[3] += attempt['count']
        else:
            attempts_distribution[4] += attempt['count']
    
    return {
        'activity_dates': activity_dates,
        'activity_data': activity_data,
        'categories_labels': categories_labels,
        'categories_data': categories_data,
        'attempts_distribution': attempts_distribution,
    }


@login_required
@require_POST
def update_settings(request):
    """
    AJAX-обработчик для обновления настроек пользователя.
    """
    try:
        data = json.loads(request.body)
        user = request.user
        
        # Обновляем настройки
        if 'email_notifications' in data:
            user.email_notifications = data['email_notifications']
        if 'is_public' in data:
            user.is_public = data['is_public']
        if 'theme' in data:
            user.theme = data['theme']
        if 'language' in data:
            user.language = data['language']
            
        user.save()
        
        return JsonResponse({'status': 'success', 'message': 'Настройки сохранены'})
    except Exception as e:
        print(f"Error updating settings: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ошибка при сохранении'}, status=400)


def custom_password_reset_view(request):
    """
    Полностью кастомное представление для сброса пароля.
    Напрямую вызывает нашу утилиту отправки email.
    """
    if request.method == 'POST':
        form = CustomPasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                user = None

            if user:
                # Генерация токена и uid
                token = default_token_generator.make_token(user)
                uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

                # Отправка письма
                send_password_reset_email(request, user, uidb64, token)

            return redirect('accounts:password_reset_done')
    else:
        form = CustomPasswordResetForm()

    return render(request, 'registration/password_reset_form.html', {'form': form})


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Кастомный view для подтверждения сброса пароля"""
    template_name = 'registration/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class CustomPasswordResetDoneView(PasswordResetDoneView):
    """Кастомный view для страницы успешной отправки email"""
    template_name = 'registration/password_reset_done.html'


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    """Кастомный view для страницы успешного сброса пароля"""
    template_name = 'registration/password_reset_complete.html'