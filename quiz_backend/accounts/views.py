from django.shortcuts import render
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import login, logout
from .models import CustomUser, TelegramAdmin, DjangoAdmin, UserChannelSubscription
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

class LogoutView(APIView):
    """
    Выход пользователя из системы.
    """
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_200_OK)

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
