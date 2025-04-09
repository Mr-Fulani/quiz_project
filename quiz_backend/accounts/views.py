from django.db.models.functions import TruncDate
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import login, logout, update_session_auth_hash
from .models import CustomUser, TelegramAdmin, DjangoAdmin, UserChannelSubscription, Profile
from .serializers import (
    UserSerializer,
    LoginSerializer,
    RegisterSerializer,
    ProfileSerializer,
    SubscriptionSerializer,
    AdminSerializer
)
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.permissions import AllowAny
from django.contrib import messages
from .forms import CustomUserCreationForm, ProfileEditForm, PersonalInfoForm
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import RedirectView, DetailView, ListView, UpdateView, TemplateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseRedirect
import re
from tasks.models import TaskStatistics
from django.utils import timezone
import json
from django.db.models import Count, Q
from django.db import models

from blog.models import Message


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
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            return Response(UserSerializer(user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomLogoutView(LogoutView):
    """
    При логауте перенаправляет на '/' (next_page='/').
    """
    next_page = '/'


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


class ProfileEditView(LoginRequiredMixin, UpdateView):
    """
    UpdateView для редактирования профиля (Profile),
    шаблон 'accounts/profile_edit.html'.
    Поля: avatar, bio, location, website.
    """
    model = Profile
    template_name = 'accounts/profile_edit.html'
    fields = ['avatar', 'bio', 'location', 'website']
    success_url = reverse_lazy('user-profile')

    def get_object(self, queryset=None):
        """
        Возвращаем профиль текущего пользователя.
        """
        return self.request.user.profile

    def get_success_url(self):
        """
        Перенаправляем на user-profile (по username текущего пользователя).
        """
        return reverse_lazy('user-profile', kwargs={'username': self.request.user.username})


@login_required
def profile_edit(request):
    """
    Функция-альтернатива ProfileEditView. При GET выдаёт форму ProfileEditForm,
    при POST сохраняет изменения в профиле.
    """
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            form.save()
            return redirect('blog:profile')
    else:
        form = ProfileEditForm(instance=request.user.profile)

    return render(request, 'accounts/profile_edit.html', {'form': form})


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


@login_required
def change_password(request):
    """
    Позволяет поменять пароль (current_password, new_password1, new_password2).
    Проверяет правильность, сложность, совпадение.
    Если всё ок - set_password, update_session_auth_hash.
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        errors = {}

        if not request.user.check_password(current_password):
            errors['current_password'] = ['Current password is incorrect.']

        if new_password1 != new_password2:
            errors['new_password2'] = ['Passwords do not match.']

        if len(new_password1) < 8:
            errors['new_password1'] = ['Password must be at least 8 characters long.']
        elif not re.search(r'[A-Z]', new_password1):
            errors['new_password1'] = ['Password must contain at least one uppercase letter.']
        elif not re.search(r'[a-z]', new_password1):
            errors['new_password1'] = ['Password must contain at least one lowercase letter.']
        elif not re.search(r'\d', new_password1):
            errors['new_password1'] = ['Password must contain at least one number.']

        if errors:
            for field, field_errors in errors.items():
                messages.error(request, field_errors[0])
            return redirect('blog:profile')

        request.user.set_password(new_password1)
        request.user.save()
        update_session_auth_hash(request, request.user)

        messages.success(request, 'Password successfully changed!')
        return redirect('blog:profile')

    return redirect('blog:profile')







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
