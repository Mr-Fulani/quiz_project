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
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.db import transaction, IntegrityError
import logging

from ..models import CustomUser, TelegramAdmin, DjangoAdmin, UserChannelSubscription, TelegramUser, MiniAppUser
from ..serializers import (
    UserSerializer,
    LoginSerializer,
    RegisterSerializer,
    SubscriptionSerializer,
    AdminSerializer,
    ProfileSerializer,
    SocialLinksSerializer,
    MiniAppUserSerializer,
    MiniAppUserCreateSerializer,
    MiniAppUserUpdateSerializer
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
            next_url = request.POST.get('next', request.META.get('HTTP_REFERER', '/'))
            return Response({
                'success': True,
                'user': UserSerializer(user).data,
                'next': next_url
            })
        print(f"Login errors: {serializer.errors}")
        return Response({'error': 'Неверный логин или пароль'}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(generics.CreateAPIView):
    """
    Регистрация нового пользователя.
    """
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def get(self, request, *args, **kwargs):
        """Перенаправление на главную."""
        from django.utils.translation import get_language
        lang_code = get_language() or 'en'
        return HttpResponseRedirect(f'/{lang_code}/?open_register=true')

    def create(self, request, *args, **kwargs):
        """Создание и логин пользователя."""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            # Для обычных форм возвращаем редирект с ошибками
            if request.content_type == 'application/x-www-form-urlencoded':
                from django.utils.translation import gettext as _
                from urllib.parse import quote
                from django.utils.translation import get_language
                
                errors = serializer.errors
                error_messages = []
                
                for field, field_errors in errors.items():
                    if isinstance(field_errors, list):
                        for error in field_errors:
                            # Используем Django переводы
                            error_str = str(error)
                            if 'already exists' in error_str:
                                translated_error = _('A user with that username already exists.')
                            elif 'required' in error_str.lower():
                                translated_error = _('This field is required.')
                            elif 'valid email' in error_str.lower():
                                translated_error = _('Enter a valid email address.')
                            elif 'too short' in error_str.lower():
                                translated_error = _('This password is too short. It must contain at least 8 characters.')
                            elif 'too common' in error_str.lower():
                                translated_error = _('This password is too common.')
                            elif 'entirely numeric' in error_str.lower():
                                translated_error = _('This password is entirely numeric.')
                            elif 'didn\'t match' in error_str.lower() or 'не совпадают' in error_str:
                                translated_error = _('The two password fields didn\'t match.')
                            else:
                                translated_error = error_str  # Fallback к оригинальному тексту
                            error_messages.append(translated_error)
                    else:
                        error_str = str(field_errors)
                        if 'already exists' in error_str:
                            translated_error = _('A user with that username already exists.')
                        elif 'required' in error_str.lower():
                            translated_error = _('This field is required.')
                        else:
                            translated_error = error_str
                        error_messages.append(translated_error)
                
                # Объединяем все сообщения об ошибках в одно с разделителем
                combined_error = ' | '.join(error_messages)
                error_param = quote(combined_error)
                lang_code = get_language() or 'en'
                return HttpResponseRedirect(f'/{lang_code}/?open_register=true&error={error_param}')
            
            # Для API запросов возвращаем JSON
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
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
    API для получения или создания профиля пользователя по telegram_id.
    Принимает POST-запрос с данными пользователя.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Ищет пользователя по telegram_id. Если находит - возвращает его
        профиль. Если нет - пытается привязать по username или создает нового
        пользователя с данными из запроса и возвращает его профиль.
        """
        user_data = request.data
        telegram_id = user_data.get('telegram_id')
        username = user_data.get('username')

        if not telegram_id:
            return Response(
                {"error": "telegram_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Вся логика выполняется в одной транзакции для атомарности
        try:
            with transaction.atomic():
                # Шаг 1: Ищем пользователя по telegram_id
                user = CustomUser.objects.filter(telegram_id=telegram_id).first()

                if not user:
                    # Шаг 2: Не нашли. Пытаемся привязать аккаунт по username.
                    if username:
                        unlinked_user = CustomUser.objects.filter(
                            username=username, telegram_id__isnull=True
                        ).first()
                        if unlinked_user:
                            logger.info(f"Связываем аккаунт: найден пользователь сайта '{username}', привязываем telegram_id {telegram_id}.")
                            unlinked_user.telegram_id = telegram_id
                            unlinked_user.is_telegram_user = True
                            unlinked_user.first_name = user_data.get('first_name', unlinked_user.first_name)
                            unlinked_user.last_name = user_data.get('last_name', unlinked_user.last_name)
                            unlinked_user.save()
                            user = unlinked_user

                # Шаг 3: Если пользователь все еще не найден, создаем нового.
                if not user:
                    logger.info(f"Создаем нового пользователя для telegram_id {telegram_id}.")
                    try:
                        user = CustomUser.objects.create(
                            telegram_id=telegram_id,
                            username=username or f"user_{telegram_id}",
                            first_name=user_data.get('first_name', ''),
                            last_name=user_data.get('last_name', ''),
                            is_telegram_user=True,
                        )
                    except IntegrityError:
                        logger.warning(f"Имя пользователя '{username}' уже занято. Создаем уникальное имя.")
                        unique_username = f"{username}_{telegram_id}"
                        user = CustomUser.objects.create(
                            telegram_id=telegram_id,
                            username=unique_username,
                            first_name=user_data.get('first_name', ''),
                            last_name=user_data.get('last_name', ''),
                            is_telegram_user=True,
                        )

                # Шаг 4: Обновляем или создаем запись в модели TelegramUser
                TelegramUser.objects.update_or_create(
                    user=user,
                    telegram_id=telegram_id,
                    defaults={
                        'username': username,
                        'first_name': user_data.get('first_name'),
                        'last_name': user_data.get('last_name'),
                        'language_code': user_data.get('language_code'),
                        'photo_url': user_data.get('photo_url')
                    }
                )

        except Exception as e:
            logger.exception(f"Критическая ошибка при создании/обновлении профиля для telegram_id={telegram_id}: {e}")
            return Response({"error": "An internal server error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = ProfileSerializer(user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicProfileByTelegramAPIView(APIView):
    """
    API для получения публичного профиля пользователя по telegram_id.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, telegram_id):
        """Получение публичного профиля по telegram_id"""
        try:
            # Используем .get() вместо get_object_or_404, чтобы вручную
            # обработать случай, когда пользователь не найден.
            user = CustomUser.objects.get(telegram_id=telegram_id)
            
            serializer = ProfileSerializer(user, context={'request': request})
            return Response(serializer.data)

        except CustomUser.DoesNotExist:
            # Это ожидаемое поведение для новых пользователей.
            # Возвращаем 404, чтобы сервис mini_app понял, что нужно создать профиль.
            logger.info(f"Профиль для telegram_id={telegram_id} не найден, возвращаем 404.")
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            # Логируем полную трассировку для неожиданных ошибок
            logger.exception(f"Unexpected error in PublicProfileByTelegramAPIView for telegram_id={telegram_id}")
            return Response({'error': 'An internal server error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProfileUpdateByTelegramView(generics.UpdateAPIView):
    """
    APIView для обновления профиля пользователя по его telegram_id.
    Используется для mini_app, чтобы загружать аватар.
    """
    queryset = CustomUser.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.AllowAny]  # Временно разрешаем без аутентификации для mini_app
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


class MiniAppUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления пользователями Mini App.
    
    Предоставляет полный CRUD для пользователей Mini App.
    """
    queryset = MiniAppUser.objects.all()
    permission_classes = [permissions.AllowAny]  # Разрешаем доступ для Mini App
    
    def get_serializer_class(self):
        """
        Выбирает подходящий сериализатор в зависимости от действия.
        """
        if self.action == 'create':
            return MiniAppUserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return MiniAppUserUpdateSerializer
        return MiniAppUserSerializer
    
    def get_object(self):
        """
        Получает объект по telegram_id вместо pk.
        """
        telegram_id = self.kwargs.get('pk')
        if telegram_id and telegram_id.isdigit():
            # Если передан числовой ID, ищем по telegram_id
            obj = get_object_or_404(MiniAppUser, telegram_id=telegram_id)
        else:
            # Иначе используем стандартный поиск по pk
            obj = super().get_object()
        return obj
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Получает информацию о текущем пользователе Mini App.
        Требует telegram_id в query параметрах.
        """
        telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return Response(
                {'error': 'telegram_id required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = MiniAppUser.objects.get(telegram_id=telegram_id)
            serializer = self.get_serializer(user)
            return Response(serializer.data)
        except MiniAppUser.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def update_last_seen(self, request):
        """
        Обновляет время последнего визита пользователя.
        """
        telegram_id = request.data.get('telegram_id')
        if not telegram_id:
            return Response(
                {'error': 'telegram_id required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = MiniAppUser.objects.get(telegram_id=telegram_id)
            user.update_last_seen()
            return Response({'success': True})
        except MiniAppUser.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def link_users(self, request):
        """
        Связывает MiniAppUser с существующими пользователями.
        """
        telegram_id = request.data.get('telegram_id')
        if not telegram_id:
            return Response(
                {'error': 'telegram_id required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = MiniAppUser.objects.get(telegram_id=telegram_id)
            
            # Пытаемся связать с существующими пользователями
            linked_count = 0
            
            # Связываем с TelegramUser
            telegram_user = TelegramUser.objects.filter(telegram_id=telegram_id).first()
            if telegram_user and not user.telegram_user:
                user.link_to_telegram_user(telegram_user)
                linked_count += 1
            
            # Связываем с TelegramAdmin
            telegram_admin = TelegramAdmin.objects.filter(telegram_id=telegram_id).first()
            if telegram_admin and not user.telegram_admin:
                user.link_to_telegram_admin(telegram_admin)
                linked_count += 1
            
            # Связываем с DjangoAdmin (по username)
            if user.username:
                django_admin = DjangoAdmin.objects.filter(username=user.username).first()
                if django_admin and not user.django_admin:
                    user.link_to_django_admin(django_admin)
                    linked_count += 1
            
            return Response({
                'success': True,
                'linked_count': linked_count,
                'user': self.get_serializer(user).data
            })
            
        except MiniAppUser.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class MiniAppUserByTelegramIDView(generics.RetrieveUpdateAPIView):
    """
    API для получения и обновления пользователя Mini App по telegram_id.
    """
    queryset = MiniAppUser.objects.all()
    serializer_class = MiniAppUserSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'telegram_id'
    
    def get_object(self):
        """
        Получает объект по telegram_id.
        """
        telegram_id = self.kwargs.get('telegram_id')
        return get_object_or_404(MiniAppUser, telegram_id=telegram_id)
    
    def get_serializer_class(self):
        """
        Выбирает сериализатор в зависимости от метода.
        """
        if self.request.method in ['PUT', 'PATCH']:
            return MiniAppUserUpdateSerializer
        return MiniAppUserSerializer 