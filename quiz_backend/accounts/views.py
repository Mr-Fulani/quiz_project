from django.shortcuts import render, redirect
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
from .forms import CustomUserCreationForm, ProfileEditForm
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import RedirectView, DetailView, ListView, UpdateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
import re
from tasks.models import TaskStatistics
from django.utils import timezone
import json
from django.db.models import Count, Q
from django.db import models

# Create your views here.

class LoginView(APIView):
    """
    Вход пользователя в систему.
    """
    permission_classes = (permissions.AllowAny,)
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            return Response(UserSerializer(user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CustomLogoutView(LogoutView):
    next_page = '/'  # Редирект на главную после выхода

class RegisterView(generics.CreateAPIView):
    """
    Регистрация нового пользователя.
    """
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

class ProfileView(generics.RetrieveAPIView):
    """
    Получение профиля пользователя.
    """
    serializer_class = ProfileSerializer
    
    def get_object(self):
        return self.request.user

class ProfileUpdateView(generics.UpdateAPIView):
    """
    Обновление профиля пользователя.
    """
    serializer_class = ProfileSerializer
    
    def get_object(self):
        return self.request.user

class ProfileDeactivateView(APIView):
    """
    Деактивация профиля пользователя.
    """
    def post(self, request):
        user = request.user
        user.is_active = False
        user.save()
        logout(request)
        return Response(status=status.HTTP_200_OK)

class SubscriptionListView(generics.ListCreateAPIView):
    """
    Список подписок пользователя.
    """
    serializer_class = SubscriptionSerializer
    
    def get_queryset(self):
        return UserChannelSubscription.objects.filter(user=self.request.user)

class SubscriptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Управление конкретной подпиской.
    """
    serializer_class = SubscriptionSerializer
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):  # для swagger
            return UserChannelSubscription.objects.none()
        return UserChannelSubscription.objects.filter(user=self.request.user)

class AdminListView(generics.ListAPIView):
    """
    Список всех администраторов.
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)
    
    def get_queryset(self):
        return CustomUser.objects.filter(
            is_staff=True
        ).exclude(is_superuser=True)

class AdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Управление конкретным администратором.
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)
    
    def get_queryset(self):
        return CustomUser.objects.filter(
            is_staff=True
        ).exclude(is_superuser=True)

class TelegramAdminListView(generics.ListAPIView):
    """
    Список Telegram администраторов.
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = TelegramAdmin.objects.all()

class DjangoAdminListView(generics.ListAPIView):
    """
    Список Django администраторов.
    """
    serializer_class = AdminSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = DjangoAdmin.objects.all()

class UserStatsView(APIView):
    """
    Статистика пользователя.
    """
    def get(self, request):
        user = request.user
        stats = {
            'total_tasks': 0,  # Заглушка, пока нет модели статистики
            'successful_tasks': 0,  # Заглушка, пока нет модели статистики
            'subscriptions': user.channel_subscriptions.count()
        }
        return Response(stats)

@method_decorator(csrf_exempt, name='dispatch')
class CustomObtainAuthToken(ObtainAuthToken):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
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

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True
    success_url = reverse_lazy('blog:index')

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('/')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

class UserProfileView(LoginRequiredMixin, DetailView):
    model = CustomUser
    template_name = 'accounts/user_profile.html'
    context_object_name = 'profile_user'
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_owner'] = self.object == self.request.user
        return context

class UserListView(LoginRequiredMixin, ListView):
    model = CustomUser
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 10

    def get_queryset(self):
        return CustomUser.objects.exclude(is_staff=True).select_related('profile').order_by('-date_joined')

class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = Profile
    template_name = 'accounts/profile_edit.html'
    fields = ['avatar', 'bio', 'location', 'website']
    success_url = reverse_lazy('user-profile')

    def get_object(self, queryset=None):
        return self.request.user.profile

    def get_success_url(self):
        return reverse_lazy('user-profile', kwargs={'username': self.request.user.username})

@login_required
def profile_edit(request):
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
    users_list = CustomUser.objects.filter(is_active=True).exclude(id=request.user.id)
    paginator = Paginator(users_list, 12)  # 12 пользователей на страницу
    
    page = request.GET.get('page')
    users = paginator.get_page(page)
    
    return render(request, 'accounts/user_list.html', {
        'users': users,
        'is_paginated': users.has_other_pages(),
        'page_obj': users,
    })

@login_required
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')
        
        errors = {}
        
        # Проверяем текущий пароль
        if not request.user.check_password(current_password):
            errors['current_password'] = ['Current password is incorrect.']
        
        # Проверяем совпадение новых паролей
        if new_password1 != new_password2:
            errors['new_password2'] = ['Passwords do not match.']
        
        # Проверяем сложность пароля
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
        
        # Меняем пароль
        request.user.set_password(new_password1)
        request.user.save()
        
        # Обновляем сессию
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Password successfully changed!')
        return redirect('blog:profile')
    
    return redirect('blog:profile')

def profile_view(request, username=None):
    # Получаем профиль пользователя
    profile_user = request.user if username is None else CustomUser.objects.get(username=username)
    context = {'profile_user': profile_user}

    # Подготовка данных для статистики
    stats = {
        'total_attempts': TaskStatistics.objects.filter(user=profile_user).count(),
        'successful_attempts': TaskStatistics.objects.filter(user=profile_user, successful=True).count(),
    }
    
    # Вычисляем процент успешности
    if stats['total_attempts'] > 0:
        stats['success_rate'] = round((stats['successful_attempts'] / stats['total_attempts']) * 100, 1)
    else:
        stats['success_rate'] = 0

    # Статистика по сложности
    difficulty_stats = TaskStatistics.objects.filter(user=profile_user).values(
        'task__difficulty'
    ).annotate(
        total=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    ).order_by('task__difficulty')

    # Статистика по темам
    topic_stats = TaskStatistics.objects.filter(user=profile_user).values(
        'task__topic__name'
    ).annotate(
        total=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    ).order_by('-total')[:5]  # Топ-5 тем

    # Статистика активности за последние 30 дней
    last_30_days = timezone.now() - timezone.timedelta(days=30)
    activity_stats = TaskStatistics.objects.filter(
        user=profile_user,
        attempt_date__gte=last_30_days
    ).annotate(
        date=models.functions.TruncDate('attempt_date')
    ).values('date').annotate(
        attempts=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    ).order_by('date')

    # Подготовка данных для графиков
    chart_data = {
        'activity': {
            'labels': json.dumps([stat['date'].strftime('%Y-%m-%d') for stat in activity_stats]),
            'attempts': json.dumps([stat['attempts'] for stat in activity_stats]),
            'successful': json.dumps([stat['successful'] for stat in activity_stats])
        },
        'topics': {
            'labels': json.dumps([stat['task__topic__name'] for stat in topic_stats]),
            'success_rates': json.dumps([
                round((stat['successful'] / stat['total'] * 100), 1) if stat['total'] > 0 else 0 
                for stat in topic_stats
            ])
        },
        'difficulty': {
            'labels': json.dumps([stat['task__difficulty'] for stat in difficulty_stats]),
            'success_rates': json.dumps([
                round((stat['successful'] / stat['total'] * 100), 1) if stat['total'] > 0 else 0 
                for stat in difficulty_stats
            ])
        }
    }

    context.update({
        'stats': stats,
        'chart_data': chart_data,
    })

    return render(request, 'accounts/profile.html', context)
