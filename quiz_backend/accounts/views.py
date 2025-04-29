# accounts/views.py
import json
import os
import re
from blog.models import Message
from django import forms
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, UpdateView, TemplateView
from rest_framework import generics, status, permissions
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from tasks.models import TaskStatistics
from .forms import PersonalInfoForm
from .models import CustomUser, TelegramAdmin, DjangoAdmin, UserChannelSubscription  # Изменено для объединения Profile и CustomUser: удалён импорт Profile
from .serializers import (
    UserSerializer,  # Изменено для объединения Profile и CustomUser: заменён ProfileSerializer на UserSerializer
    LoginSerializer,
    RegisterSerializer,
    SubscriptionSerializer,
    AdminSerializer
)


class LoginView(APIView):
    """
    APIView для входа пользователя.
    При POST-передаче данных (логин/пароль) валидируем, логиним.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        """
        Получаем логин/пароль из request.data,
        если ок, login(request, user) и возвращаем JSON с данными пользователя.
        """
        print(f"Login request data: {request.data}")
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            print(f"User {user.username} logged in")
            next_url = request.POST.get('next', '/')
            return Response({
                'success': True,
                'user': UserSerializer(user).data,
                'next': next_url
            })
        print(f"Login errors: {serializer.errors}")
        return Response({'error': 'Неверный логин или пароль'}, status=status.HTTP_400_BAD_REQUEST)


class CustomLogoutView(LogoutView):
    """
    При логауте перенаправляет на '/' (next_page='/').
    """
    next_page = '/'

    def post(self, request, *args, **kwargs):
        print(f"Logout request: {request.POST}")
        return super().post(request, *args, **kwargs)


class RegisterView(generics.CreateAPIView):
    """
    Регистрация нового пользователя.
    """
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def get(self, request, *args, **kwargs):
        """Перенаправление на главную."""
        return HttpResponseRedirect('/?open_register=true')

    def create(self, request, *args, **kwargs):
        """Создание и логин пользователя."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        user = serializer.instance
        login(request, user)
        next_url = request.POST.get('next', '/')
        return HttpResponseRedirect(f"{next_url}?registration_success=true")


class ProfileUpdateView(generics.UpdateAPIView):
    """
    APIView для обновления профиля (PATCH/PUT /accounts/profile/update/).
    """
    serializer_class = UserSerializer  # Изменено для объединения Profile и CustomUser: заменён ProfileSerializer на UserSerializer

    def get_object(self):
        """
        Текущий пользователь (request.user).
        """
        return self.request.user


class ProfileDeactivateView(APIView):
    """
    APIView для деактивации профиля (POST).
    Ставит is_active=False, вызывает logout.
    """
    def post(self, request):
        """
        Деактивирует пользователя, разлогинивает, возвращает 200 OK.
        """
        user = request.user
        user.is_active = False
        user.save()
        logout(request)
        return Response(status=status.HTTP_200_OK)


class SubscriptionListView(generics.ListCreateAPIView):
    """
    Список/создание подписок (UserChannelSubscription) текущего пользователя.
    """
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        """
        Возвращает все подписки, связанные с request.user.
        """
        return UserChannelSubscription.objects.filter(user=self.request.user)


class SubscriptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Получение/обновление/удаление конкретной подписки (по pk).
    """
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        """
        Если это swagger_fake_view, возвращаем пустой QuerySet.
        Иначе подписки, принадлежащие request.user.
        """
        if getattr(self, 'swagger_fake_view', False):
            return UserChannelSubscription.objects.none()
        return UserChannelSubscription.objects.filter(user=self.request.user)


class AdminListView(generics.ListAPIView):
    """
    Список всех администраторов (is_staff=True, но не superuser).
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)

    def get_queryset(self):
        """Фильтрация администраторов."""
        return CustomUser.objects.filter(is_staff=True).exclude(is_superuser=True)


class AdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Получение/изменение/удаление конкретного администратора.
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)

    def get_queryset(self):
        """Фильтрация администраторов."""
        return CustomUser.objects.filter(is_staff=True).exclude(is_superuser=True)


class TelegramAdminListView(generics.ListAPIView):
    """
    Список администраторов TelegramAdmin.
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = TelegramAdmin.objects.all()


class DjangoAdminListView(generics.ListAPIView):
    """
    Список администраторов DjangoAdmin.
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = DjangoAdmin.objects.all()


class UserStatsView(APIView):
    """
    APIView для возвращения статистики текущего пользователя (заглушка).
    """
    def get(self, request):
        """
        Возвращает словарь с заглушкой статистики.
        """
        user = request.user
        stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'subscriptions': user.channel_subscriptions.count()
        }
        return Response(stats)


@method_decorator(csrf_exempt, name='dispatch')
class CustomObtainAuthToken(ObtainAuthToken):
    """
    Получение токена через POST (логин/пароль).
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Создаёт или возвращает уже существующий токен для пользователя.
        """
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username
        })


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
        'personal_info_form': PersonalInfoForm(instance=request.user, user=request.user),  # Изменено для объединения Profile и CustomUser: instance=request.user.profile -> instance=request.user
        'profile_user': request.user,
        'is_owner': True,
        'user_settings': request.user,  # Изменено для объединения Profile и CustomUser: user_settings=request.user.profile -> user_settings=request.user
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
        user = request.user  # Изменено для объединения Profile и CustomUser: profile = request.user.profile -> user = request.user
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if 'avatar' in request.FILES and 'personal_info' not in request.POST:
            old_avatar = user.avatar  # Изменено для объединения Profile и CustomUser: profile.avatar -> user.avatar
            form = PersonalInfoForm(
                request.POST,
                request.FILES,
                instance=user,  # Изменено для объединения Profile и CustomUser: instance=profile -> instance=user
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
                    return JsonResponse({'status': 'success', 'avatar_url': user.get_avatar_url})  # Изменено для объединения Profile и CustomUser: profile.get_avatar_url -> user.get_avatar_url
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
                instance=user,  # Изменено для объединения Profile и CustomUser: instance=profile -> instance=user
                user=user
            )
            print(f"Form created with data: {form.data}")
            if form.is_valid():
                print(f"Form is valid, cleaned data: {form.cleaned_data}")
                form.save()  # Изменено для объединения Profile и CustomUser: убрано отдельное сохранение user и profile, так как всё в CustomUser
                print(f"User {user.username} saved with email: {user.email}, first_name: {user.first_name}")
                if is_ajax:
                    return JsonResponse({'status': 'success', 'avatar_url': user.get_avatar_url})  # Изменено для объединения Profile и CustomUser: profile.get_avatar_url -> user.get_avatar_url
                messages.success(request, 'Профиль успешно обновлён!')
                return redirect('accounts:dashboard')
            else:
                print(f"Form errors: {form.errors.as_json()}")
                if is_ajax:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Исправьте ошибки в форме',
                        'errors': form.errors.as_json()
                    }, status=400)
                messages.error(request, 'Исправьте ошибки в форме.')
                return redirect('accounts:dashboard')
    else:
        form = PersonalInfoForm(instance=request.user, user=request.user)  # Изменено для объединения Profile и CustomUser: instance=request.user.profile -> instance=request.user

    return render(request, 'accounts/dashboard.html', {
        'personal_info_form': form,
        'profile_user': request.user,
        'is_owner': True,
        'user_settings': request.user,  # Изменено для объединения Profile и CustomUser: user_settings=request.user.profile -> user_settings=request.user
        'active_tab': 'personal'
    })


class UserProfileView(LoginRequiredMixin, DetailView):
    """
    DetailView для профиля пользователя (CustomUser).
    """
    model = CustomUser
    template_name = 'accounts/user_profile.html'
    context_object_name = 'profile_user'
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_context_data(self, **kwargs):
        """
        Определяем, является ли текущий user владельцем профиля (is_owner).
        """
        context = super().get_context_data(**kwargs)
        context['is_owner'] = self.object == self.request.user
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
        """Фильтрация не-администраторов."""
        return CustomUser.objects.exclude(is_staff=True).order_by('-date_joined')  # Изменено для объединения Profile и CustomUser: убрано select_related('profile')


@login_required
def user_list(request):
    """
    Отображение списка активных пользователей (кроме текущего).
    """
    users_list = CustomUser.objects.filter(is_active=True).exclude(id=request.user.id).order_by('-last_seen')  # Изменено для объединения Profile и CustomUser: убрано select_related('profile') и сортировка по -last_seen вместо -profile__last_seen
    paginator = Paginator(users_list, 12)
    page = request.GET.get('page')
    users = paginator.get_page(page)
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

    stats = {
        'total_attempts': TaskStatistics.objects.filter(user=profile_user).count(),
        'successful_attempts': TaskStatistics.objects.filter(user=profile_user, successful=True).count()
    }
    stats['success_rate'] = round((stats['successful_attempts'] / stats['total_attempts']) * 100, 1) if stats['total_attempts'] > 0 else 0

    inbox_messages = profile_user.received_messages.all().order_by('-created_at')[:10] if is_owner else []
    sent_messages = profile_user.sent_messages.all().order_by('-created_at')[:10] if is_owner else []

    activity_stats = TaskStatistics.objects.filter(
        user=profile_user,
        last_attempt_date__isnull=False
    ).annotate(
        date=TruncDate('last_attempt_date')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    activity_dates = [stat['date'].strftime('%d.%m') for stat in activity_stats] or ['No data']
    activity_data = [stat['count'] for stat in activity_stats] or [0]
    has_activity_data = len(activity_stats) > 0

    category_stats = TaskStatistics.objects.filter(user=profile_user).values(
        'task__topic__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    categories_labels = [stat['task__topic__name'] if stat['task__topic__name'] else 'Unknown' for stat in category_stats] or ['No data']
    categories_data = [stat['count'] for stat in category_stats] or [0]
    has_categories_data = len(category_stats) > 0

    attempts = TaskStatistics.objects.filter(user=profile_user).values('attempts').annotate(count=Count('id'))
    attempts_distribution = [0] * 5
    for attempt in attempts:
        attempts_value = int(attempt['attempts']) if attempt['attempts'] is not None else 0
        if attempts_value > 0:
            bin_index = min((attempts_value - 1) // 5, 4)
            attempts_distribution[bin_index] += attempt['count']
        elif attempts_value == 0:
            attempts_distribution[0] += attempt['count']
    has_attempts_data = any(attempts_distribution)

    print(f"\nDebug chart data for user {profile_user.username}:")
    print(f"Activity dates: {activity_dates}")
    print(f"Activity data: {activity_data}")
    print(f"Has activity data: {has_activity_data}")
    print(f"Categories labels: {categories_labels}")
    print(f"Categories data: {categories_data}")
    print(f"Has categories data: {has_categories_data}")
    print(f"Attempts distribution: {attempts_distribution}")
    print(f"Has attempts data: {has_attempts_data}")

    context = {
        'profile_user': profile_user,
        'is_owner': is_owner,
        'stats': stats,
        'activity_dates': activity_dates,
        'activity_data': activity_data,
        'has_activity_data': has_activity_data,
        'categories_labels': categories_labels,
        'categories_data': categories_data,
        'has_categories_data': has_categories_data,
        'attempts_distribution': attempts_distribution,
        'has_attempts_data': has_attempts_data,
        'inbox_messages': inbox_messages,
        'sent_messages': sent_messages
    }

    if is_dashboard:
        context.update({
            'personal_info_form': PersonalInfoForm(instance=profile_user, user=profile_user),  # Изменено для объединения Profile и CustomUser: instance=profile_user.profile -> instance=profile_user
            'user_settings': profile_user  # Изменено для объединения Profile и CustomUser: user_settings=profile_user.profile -> user_settings=profile_user
        })

    return render(request, template_name, context)


def get_user_chart_data(user):
    """
    Возвращает данные для графиков: активность, темы, сложность.
    """
    activity_stats = TaskStatistics.objects.filter(user=user).annotate(
        date=TruncDate('last_attempt_date')
    ).values('date').annotate(
        attempts=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    ).order_by('date')

    topic_stats = TaskStatistics.objects.filter(user=user).values(
        'task__topic__name'
    ).annotate(
        total=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    ).order_by('-total')[:5]

    difficulty_stats = TaskStatistics.objects.filter(user=user).values(
        'task__difficulty'
    ).annotate(
        total=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    )

    print(f"\nDebug get_user_chart_data for user {user.username}:")
    print(f"Activity stats: {list(activity_stats)}")
    print(f"Topic stats: {list(topic_stats)}")
    print(f"Difficulty stats: {list(difficulty_stats)}")

    activity_data = {
        'labels': [stat['date'].strftime('%d.%m') for stat in activity_stats] or ['No data'],
        'datasets': [
            {
                'label': 'Attempts',
                'data': [stat['attempts'] for stat in activity_stats] or [0],
                'borderColor': '#ffaa00',
                'fill': False
            },
            {
                'label': 'Successful',
                'data': [stat['successful'] for stat in activity_stats] or [0],
                'borderColor': '#00ff00',
                'fill': False
            }
        ]
    }

    topics_data = {
        'labels': [stat['task__topic__name'] for stat in topic_stats] or ['No data'],
        'datasets': [{
            'label': 'Success Rate (%)',
            'data': [
                round((stat['successful'] / stat['total']) * 100 if stat['total'] > 0 else 0, 1)
                for stat in topic_stats
            ] or [0],
            'backgroundColor': '#ffaa00'
        }]
    }

    difficulty_data = {
        'labels': [stat['task__difficulty'] for stat in difficulty_stats] or ['No data'],
        'datasets': [{
            'label': 'Success Rate (%)',
            'data': [
                round((stat['successful'] / stat['total']) * 100 if stat['total'] > 0 else 0, 1)
                for stat in difficulty_stats
            ] or [0],
            'backgroundColor': ['#ffaa00', '#ffd700', '#ffa500']
        }]
    }

    return {
        'activity': activity_data,
        'topics': topics_data,
        'difficulty': difficulty_data
    }


@login_required
@require_POST
def update_settings(request):
    """
    AJAX для обновления настроек профиля.
    """
    try:
        data = json.loads(request.body)
        setting = data.get('setting')
        value = data.get('value')
        user = request.user  # Изменено для объединения Profile и CustomUser: profile = request.user.profile -> user = request.user

        if setting == 'email_notifications':
            user.email_notifications = value
        elif setting == 'is_public':
            user.is_public = value
        elif setting == 'theme_preference':
            user.theme_preference = 'dark' if value else 'light'
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid setting'}, status=400)

        user.save()
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)