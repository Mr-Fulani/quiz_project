from django.shortcuts import render, redirect
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import login, logout
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
from .forms import CustomUserCreationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import RedirectView, DetailView, ListView, UpdateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin

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

    def get_object(self):
        # Отладочное сообщение для проверки переданного username
        print(f"Looking for user with username: {self.kwargs.get('username')}")
        return super().get_object()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_own_profile'] = self.object == self.request.user
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
