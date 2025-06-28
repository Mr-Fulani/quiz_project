from rest_framework import viewsets, permissions, generics, status
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model, logout, login
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponseRedirect
import logging

from ..models import CustomUser, TelegramAdmin, DjangoAdmin, UserChannelSubscription
from ..serializers import (
    UserSerializer,
    LoginSerializer,
    RegisterSerializer,
    SubscriptionSerializer,
    AdminSerializer,
    ProfileSerializer,
    SocialLinksSerializer
)

User = get_user_model()
logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = User.objects.all()

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


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
    serializer_class = UserSerializer

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


class PublicProfileAPIView(APIView):
    """
    API для получения публичного профиля пользователя.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, user_id=None):
        """Получение публичного профиля по ID"""
        try:
            if user_id:
                user = get_object_or_404(CustomUser, id=user_id)
            else:
                if not request.user.is_authenticated:
                    return Response({'error': 'Authentication required'}, 
                                  status=status.HTTP_401_UNAUTHORIZED)
                user = request.user

            # Проверяем публичность профиля
            if user != request.user and not user.is_public:
                return Response({'error': 'Private profile'}, 
                              status=status.HTTP_403_FORBIDDEN)

            serializer = ProfileSerializer(user, context={'request': request})
            data = serializer.data
            
            return Response(data)

        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, 
                          status=status.HTTP_404_NOT_FOUND)


class ProfileByTelegramID(APIView):
    """
    API для получения профиля пользователя по telegram_id.
    Если пользователь не найден, он будет создан.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, telegram_id):
        user, created = CustomUser.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'username': f'user_{telegram_id}',
                'first_name': 'New',
                'last_name': 'User'
            }
        )

        if created:
            logger.info(f"Создан новый пользователь с telegram_id: {telegram_id}")

        serializer = ProfileSerializer(user)
        return Response(serializer.data)


class ProfileUpdateByTelegramView(generics.UpdateAPIView):
    """
    APIView для обновления профиля пользователя по его telegram_id.
    Используется для mini_app, чтобы загружать аватар.
    """
    queryset = CustomUser.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated] # Можно заменить на кастомный пермишн для mini_app
    lookup_field = 'telegram_id'

    def get_object(self):
        """
        Получаем пользователя по telegram_id из URL.
        """
        telegram_id = self.kwargs.get('telegram_id')
        return get_object_or_404(CustomUser, telegram_id=telegram_id)


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