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

from .forms import  PersonalInfoForm
from .models import CustomUser, TelegramAdmin, DjangoAdmin, UserChannelSubscription, Profile
from .serializers import (
    UserSerializer,
    LoginSerializer,
    RegisterSerializer,
    ProfileSerializer,
    SubscriptionSerializer,
    AdminSerializer
)


class LoginView(APIView):
    """
    APIView для входа пользователя.
    При POST-передаче данных (логин/пароль) валидируем, логиним.
    """
    permission_classes = (permissions.AllowAny,)

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
            # Получаем параметр next из формы
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
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def get(self, request, *args, **kwargs):
        # Для GET-запросов перенаправляем на главную с open_register=true
        return HttpResponseRedirect('/?open_register=true')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Логиним пользователя после регистрации
        user = serializer.instance
        login(request, user)
        # Получаем next или используем главную
        next_url = request.POST.get('next', '/')
        return HttpResponseRedirect(f"{next_url}?registration_success=true")


class ProfileUpdateView(generics.UpdateAPIView):
    """
    APIView для обновления профиля (PATCH/PUT /accounts/profile/update/).
    """
    serializer_class = ProfileSerializer

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
        Деактивирует пользователя, разлогинивает,
        возвращает 200 OK.
        """
        user = request.user
        user.is_active = False
        user.save()
        logout(request)
        return Response(status=status.HTTP_200_OK)


class SubscriptionListView(generics.ListCreateAPIView):
    """
    Список/создание подписок (UserChannelSubscription)
    текущего пользователя (request.user).
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
    Доступ разрешён только админам (permissions.IsAdminUser).
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)

    def get_queryset(self):
        return CustomUser.objects.filter(
            is_staff=True
        ).exclude(is_superuser=True)


class AdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Получение/изменение/удаление конкретного администратора.
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)

    def get_queryset(self):
        return CustomUser.objects.filter(
            is_staff=True
        ).exclude(is_superuser=True)


class TelegramAdminListView(generics.ListAPIView):
    """
    Список администраторов TelegramAdmin (модель TelegramAdmin).
    permission_classes = IsAdminUser => только админы.
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = TelegramAdmin.objects.all()


class DjangoAdminListView(generics.ListAPIView):
    """
    Список администраторов DjangoAdmin (модель DjangoAdmin).
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = DjangoAdmin.objects.all()


class UserStatsView(APIView):
    """
    Пример APIView для возвращения статистики текущего пользователя.
    (здесь - заглушка)
    """

    def get(self, request):
        """
        Возвращает словарь с 'total_tasks', 'successful_tasks',
        и количеством подписок у текущего user.
        """
        user = request.user
        stats = {
            'total_tasks': 0,  # пока заглушка
            'successful_tasks': 0,  # заглушка
            'subscriptions': user.channel_subscriptions.count()
        }
        return Response(stats)


@method_decorator(csrf_exempt, name='dispatch')
class CustomObtainAuthToken(ObtainAuthToken):
    """
    Получение токена через POST (логин/пароль).
    permission_classes = AllowAny.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Создаёт или возвращает уже существующий токен для пользователя.
        """
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
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
        error_messages={
            'required': 'Поле текущего пароля обязательно.',
        }
    )
    new_password1 = forms.CharField(
        label="Новый пароль",
        widget=forms.PasswordInput,
        error_messages={
            'required': 'Поле нового пароля обязательно.',
        }
    )
    new_password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput,
        error_messages={
            'required': 'Поле подтверждения пароля обязательно.',
        }
    )

    error_messages = {
        'password_mismatch': 'Поля нового пароля и подтверждения не совпадают.',
        'password_incorrect': 'Текущий пароль введён неверно.',
        'password_too_short': 'Пароль слишком короткий. Минимальная длина — 8 символов.',
        'password_entirely_numeric': 'Пароль не может состоять только из цифр. Добавьте буквы или символы.',
        'password_too_common': 'Пароль должен содержать буквы, цифры и хотя бы один специальный символ (например, !, @, #).',
    }

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].min_length = 8

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError(
                self.error_messages['password_incorrect'],
                code='password_incorrect',
            )
        return old_password

    def clean_new_password2(self):
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')
        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError(
                self.error_messages['password_mismatch'],
                code='password_mismatch',
            )
        return new_password2

    def clean_new_password1(self):
        new_password1 = self.cleaned_data.get('new_password1')
        if new_password1:
            if len(new_password1) < 8:
                raise forms.ValidationError(
                    self.error_messages['password_too_short'],
                    code='password_too_short',
                )
            if new_password1.isdigit():
                raise forms.ValidationError(
                    self.error_messages['password_entirely_numeric'],
                    code='password_entirely_numeric',
                )
            # Проверка на сложность (буквы, цифры, символы)
            has_letter = any(c.isalpha() for c in new_password1)
            has_digit = any(c.isdigit() for c in new_password1)
            has_symbol = any(not c.isalnum() for c in new_password1)
            if not (has_letter and has_digit and has_symbol):
                raise forms.ValidationError(
                    self.error_messages['password_too_common'],
                    code='password_too_common',
                )
        return new_password1

    def save(self):
        new_password = self.cleaned_data['new_password1']
        self.user.set_password(new_password)
        self.user.save()



@login_required
def change_password(request):
    """
    Обработка формы смены пароля с использованием CustomPasswordChangeForm.
    Ошибки отображаются только в форме, успех через флаг success.
    """
    success = False
    if request.method == 'POST':
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            success = True
            form = CustomPasswordChangeForm(user=request.user)  # Очистка формы после успеха
        else:
            print(f"Password form errors: {form.errors}")
    else:
        form = CustomPasswordChangeForm(user=request.user)

    return render(request, 'accounts/dashboard.html', {
        'password_form': form,
        'personal_info_form': PersonalInfoForm(instance=request.user.profile, user=request.user),
        'profile_user': request.user,
        'is_owner': True,
        'user_settings': request.user.profile,
        'active_tab': 'security',
        'password_change_success': success,
    })



@login_required
def update_personal_info(request):
    """
    Обработка формы PersonalInfoForm или загрузки аватара.
    Устанавливает active_tab='personal' по умолчанию.
    """
    if request.method == 'POST':
        print(f"POST data: {request.POST}")
        print(f"FILES: {request.FILES}")
        if 'avatar' in request.FILES and 'personal_info' not in request.POST:
            profile = request.user.profile
            old_avatar = profile.avatar
            form = PersonalInfoForm(
                request.POST,
                request.FILES,
                instance=profile,
                user=request.user,
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
                messages.success(request, 'Аватар успешно обновлён!')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'avatar_url': profile.get_avatar_url})
                return redirect('accounts:dashboard')
            else:
                print(f"Avatar form errors: {form.errors}")
                messages.error(request, 'Недопустимый файл аватара.')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': 'Недопустимый файл аватара'}, status=400)
                return redirect('accounts:dashboard')
        else:
            form = PersonalInfoForm(
                request.POST,
                request.FILES,
                instance=request.user.profile,
                user=request.user
            )
            if form.is_valid():
                form.save()
                messages.success(request, 'Профиль успешно обновлён!')
                return redirect('accounts:dashboard')
            else:
                print(f"Form errors: {form.errors}")
                messages.error(request, 'Исправьте ошибки в форме.')
    else:
        form = PersonalInfoForm(instance=request.user.profile, user=request.user)

    return render(request, 'accounts/dashboard.html', {
        'personal_info_form': form,
        'profile_user': request.user,
        'is_owner': True,
        'user_settings': request.user.profile,
        'active_tab': 'personal',  # По умолчанию Personal Info
    })












class UserProfileView(LoginRequiredMixin, DetailView):
    """
    DetailView для профиля пользователя (CustomUser),
    шаблон 'accounts/user_profile.html',
    slug_field='username'.
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
    Список пользователей (не staff),
    по 10 на страницу, шаблон 'accounts/user_list.html'.
    """
    model = CustomUser
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 10

    def get_queryset(self):
        return CustomUser.objects.exclude(is_staff=True).select_related('profile').order_by('-date_joined')


@login_required
def user_list(request):
    """
    Ещё одно отображение списка пользователей (не себя),
    по 12 на страницу, шаблон 'accounts/user_list.html'.
    """
    users_list = CustomUser.objects.filter(is_active=True).exclude(id=request.user.id)
    paginator = Paginator(users_list, 12)

    page = request.GET.get('page')
    users = paginator.get_page(page)

    return render(request, 'accounts/user_list.html', {
        'users': users,
        'is_paginated': users.has_other_pages(),
        'page_obj': users,
    })




class ProfileView(TemplateView):
    """
    Простейшее отображение профиля (accounts/profile.html).
    Использует self.request.user как user_profile.
    """
    template_name = 'accounts/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_profile'] = self.request.user
        return context


@login_required
def dashboard_view(request):
    """
    Личный кабинет (dashboard) -> вызывает profile_view(..., is_dashboard=True).
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
    Если is_dashboard=True -> рендерим blog/dashboard.html,
    иначе accounts/profile.html.

    Вычисляет статистику (stats),
    а если личный кабинет (is_dashboard),
    добавляет form, inbox_messages и sent_messages.
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
        'successful_attempts': TaskStatistics.objects.filter(user=profile_user, successful=True).count(),
    }
    if stats['total_attempts'] > 0:
        stats['success_rate'] = round((stats['successful_attempts'] / stats['total_attempts']) * 100, 1)
    else:
        stats['success_rate'] = 0

    context = {
        'profile_user': profile_user,
        'is_owner': is_owner,
        'stats': stats,
        'chart_data': get_user_chart_data(profile_user),
    }

    if is_dashboard:
        context.update({
            'personal_info_form': PersonalInfoForm(instance=profile_user.profile, user=profile_user),
            'user_settings': profile_user.profile,  # Для вкладки Settings
        })

    return render(request, template_name, context)


def get_user_chart_data(user):
    """
    Возвращает словарь с данными для трёх видов графиков:
    - activity (активность за последние 30 дней)
    - topics (топ-5 тем)
    - difficulty (статистика по уровню сложности)
    """
    last_30_days = timezone.now() - timezone.timedelta(days=30)
    activity_stats = TaskStatistics.objects.filter(
        user=user,
        last_attempt_date__gte=last_30_days
    ).annotate(
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

    return {
        'activity': {
            'labels': [stat['date'].strftime('%d.%m') for stat in activity_stats],
            'attempts': [stat['attempts'] for stat in activity_stats],
            'successful': [stat['successful'] for stat in activity_stats]
        },
        'topics': {
            'labels': [stat['task__topic__name'] for stat in topic_stats],
            'success_rates': [
                round((stat['successful'] / stat['total']) * 100 if stat['total'] > 0 else 0, 1)
                for stat in topic_stats
            ]
        },
        'difficulty': {
            'labels': [stat['task__difficulty'] for stat in difficulty_stats],
            'success_rates': [
                round((stat['successful'] / stat['total']) * 100 if stat['total'] > 0 else 0, 1)
                for stat in difficulty_stats
            ]
        }
    }


@login_required
@require_POST
def update_settings(request):
    """
    AJAX для обновления настроек профиля (email_notifications, is_public, theme_preference).
    Принимает JSON {setting, value}, возвращает JSON-ответ.
    """
    try:
        data = json.loads(request.body)
        setting = data.get('setting')
        value = data.get('value')

        profile = request.user.profile

        if setting == 'email_notifications':
            profile.email_notifications = value
        elif setting == 'is_public':
            profile.is_public = value
        elif setting == 'theme_preference':
            profile.theme_preference = 'dark' if value else 'light'
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid setting'}, status=400)

        profile.save()
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)










