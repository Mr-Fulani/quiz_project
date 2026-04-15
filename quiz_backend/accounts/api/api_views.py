from rest_framework import viewsets, permissions, generics, status
from tenants.mixins import TenantFilteredViewMixin
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.contrib.auth import get_user_model, logout, login
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.db import transaction, IntegrityError
from django.db.models import Count, Q
from django.utils.translation import activate, gettext_lazy as _
import logging

from ..models import CustomUser, TelegramAdmin, DjangoAdmin, UserChannelSubscription, TelegramUser, MiniAppUser
from topics.models import Topic
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
    MiniAppUserUpdateSerializer,
    MiniAppTopUserSerializer,
    PublicMiniAppUserSerializer
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

    def perform_create(self, serializer):
        """Создаёт пользователя с тенантом текущего домена."""
        tenant = getattr(self.request, 'tenant', None)
        serializer.save(tenant=tenant)


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
                tenant = getattr(request, 'tenant', None)
                user = get_object_or_404(CustomUser, id=user_id, tenant=tenant)
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
                tenant = getattr(request, 'tenant', None)
                # Шаг 1: Ищем пользователя по telegram_id и тенанту
                user = CustomUser.objects.filter(telegram_id=telegram_id, tenant=tenant).first()

                if not user:
                    # Шаг 2: Не нашли. Пытаемся привязать аккаунт по username в том же тенанте.
                    if username:
                        unlinked_user = CustomUser.objects.filter(
                            username=username, 
                            tenant=tenant,
                            telegram_id__isnull=True
                        ).first()
                        if unlinked_user:
                            logger.info(f"Связываем аккаунт: найден пользователь сайта '{username}' в тенанте {tenant}, привязываем telegram_id {telegram_id}.")
                            unlinked_user.telegram_id = telegram_id
                            unlinked_user.is_telegram_user = True
                            unlinked_user.first_name = user_data.get('first_name', unlinked_user.first_name)
                            unlinked_user.last_name = user_data.get('last_name', unlinked_user.last_name)
                            unlinked_user.save()
                            user = unlinked_user

                # Шаг 3: Если пользователь все еще не найден, создаем нового в текущем тенанте.
                if not user:
                    logger.info(f"Создаем нового пользователя для telegram_id {telegram_id} в тенанте {tenant}.")
                    try:
                        user = CustomUser.objects.create(
                            telegram_id=telegram_id,
                            tenant=tenant,
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
                            tenant=tenant,
                            username=unique_username,
                            first_name=user_data.get('first_name', ''),
                            last_name=user_data.get('last_name', ''),
                            is_telegram_user=True,
                        )

                # Шаг 4: Обновляем или создаем запись в модели TelegramUser в том же тенанте
                TelegramUser.objects.update_or_create(
                    linked_user=user,
                    telegram_id=telegram_id,
                    tenant=tenant,
                    defaults={
                        'username': username,
                        'first_name': user_data.get('first_name'),
                        'last_name': user_data.get('last_name'),
                        'language': user_data.get('language_code'),
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
            tenant = getattr(request, 'tenant', None)
            # Используем .get() вместо get_object_or_404, чтобы вручную
            # обработать случай, когда пользователь не найден.
            user = CustomUser.objects.get(telegram_id=telegram_id, tenant=tenant)
            
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
    queryset = MiniAppUser.objects.all()
    serializer_class = MiniAppUserUpdateSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'telegram_id'
    parser_classes = [MultiPartParser, FormParser]
    
    def update(self, request, *args, **kwargs):
        """Переопределяем update чтобы возвращать JSON вместо редиректа."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Обновление аватара пользователя Mini App.",
        manual_parameters=[
            openapi.Parameter(
                'telegram_id',
                openapi.IN_PATH,
                description="ID пользователя Telegram.",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'avatar',
                openapi.IN_FORM,
                description="Файл аватара для загрузки.",
                type=openapi.TYPE_FILE,
                required=False
            ),
            openapi.Parameter(
                'username',
                openapi.IN_FORM,
                description="Имя пользователя.",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'first_name',
                openapi.IN_FORM,
                description="Имя.",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'last_name',
                openapi.IN_FORM,
                description="Фамилия.",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'language',
                openapi.IN_FORM,
                description="Язык.",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        responses={
            200: MiniAppUserSerializer,
            400: 'Неверные данные',
            404: 'Пользователь не найден'
        }
    )
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Частичное обновление профиля пользователя Mini App.",
        manual_parameters=[
            openapi.Parameter(
                'telegram_id',
                openapi.IN_PATH,
                description="ID пользователя Telegram.",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'avatar',
                openapi.IN_FORM,
                description="Файл аватара для загрузки.",
                type=openapi.TYPE_FILE,
                required=False
            ),
            openapi.Parameter(
                'username',
                openapi.IN_FORM,
                description="Имя пользователя.",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'first_name',
                openapi.IN_FORM,
                description="Имя.",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'last_name',
                openapi.IN_FORM,
                description="Фамилия.",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'language',
                openapi.IN_FORM,
                description="Язык.",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        responses={
            200: MiniAppUserSerializer,
            400: 'Неверные данные',
            404: 'Пользователь не найден'
        }
    )
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


    def get_object(self):
        """
        Получаем пользователя MiniAppUser по telegram_id из URL и тенанту.
        """
        telegram_id = self.kwargs.get('telegram_id')
        tenant = getattr(self.request, 'tenant', None)
        return get_object_or_404(MiniAppUser, telegram_id=telegram_id, tenant=tenant)


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
    
    def get_queryset(self):
        """
        Фильтрует пользователей по тенанту текущего запроса.
        """
        tenant = getattr(self.request, 'tenant', None)
        return MiniAppUser.objects.filter(tenant=tenant)
    
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
        tenant = getattr(self.request, 'tenant', None)
        if telegram_id and str(telegram_id).isdigit():
            # Если передан числовой ID, ищем по telegram_id и тенанту
            obj = get_object_or_404(MiniAppUser, telegram_id=telegram_id, tenant=tenant)
        else:
            # Иначе используем стандартный поиск по pk
            obj = super().get_object()
        return obj

    def perform_create(self, serializer):
        """
        При создании пользователя устанавливаем текущий тенант.
        """
        tenant = getattr(self.request, 'tenant', None)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"MiniAppUserViewSet.perform_create: создание пользователя с tenant={tenant}")
        serializer.save(tenant=tenant)
    
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
            tenant = getattr(request, 'tenant', None)
            user = MiniAppUser.objects.get(telegram_id=telegram_id, tenant=tenant)
            serializer = self.get_serializer(user)
            return Response(serializer.data)
        except MiniAppUser.DoesNotExist:
            return Response(
                {'error': 'User not found in this tenant'}, 
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
            tenant = getattr(request, 'tenant', None)
            user = MiniAppUser.objects.get(telegram_id=telegram_id, tenant=tenant)
            user.update_last_seen()
            return Response({'success': True})
        except MiniAppUser.DoesNotExist:
            return Response(
                {'error': 'User not found in this tenant'}, 
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
            tenant = getattr(request, 'tenant', None)
            user = MiniAppUser.objects.get(telegram_id=telegram_id, tenant=tenant)
            
            # Пытаемся связать с существующими пользователями
            linked_count = 0
            
            # Связываем с TelegramUser
            telegram_user = TelegramUser.objects.filter(telegram_id=telegram_id, tenant=tenant).first()
            if telegram_user and not user.telegram_user:
                user.link_to_telegram_user(telegram_user)
                linked_count += 1
            
            # Связываем с TelegramAdmin
            telegram_admin = TelegramAdmin.objects.filter(telegram_id=telegram_id, tenant=tenant).first()
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
    
    @action(detail=False, methods=['post'])
    def refresh_from_telegram(self, request):
        """
        Обновляет данные пользователя Mini App из Telegram.
        
        Получает актуальные данные пользователя из Telegram и синхронизирует их.
        Использует данные из request.data (например, из Mini App initData) или пытается получить через Bot API.
        """
        telegram_id = request.data.get('telegram_id')
        if not telegram_id:
            return Response(
                {'error': 'telegram_id required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            tenant = getattr(request, 'tenant', None)
            user = MiniAppUser.objects.get(telegram_id=telegram_id, tenant=tenant)
            
            # Получаем данные из запроса (из Mini App initData)
            # Важно: last_name может быть пустой строкой, поэтому проверяем явно
            raw_last_name = request.data.get('last_name')
            telegram_data = {
                'first_name': request.data.get('first_name'),
                'last_name': raw_last_name,  # Сохраняем как есть (может быть None, пустая строка или значение)
                'username': request.data.get('username'),
                'photo_url': request.data.get('photo_url'),
                'language_code': request.data.get('language_code', 'ru')
            }
            
            # Логируем полученные данные для отладки
            logger.info(f"🔄 Обновление данных из Telegram для telegram_id={telegram_id}")
            logger.info(f"📝 Полученные данные из request.data: first_name={request.data.get('first_name')}, last_name={raw_last_name} (тип: {type(raw_last_name)}), username={request.data.get('username')}, photo_url={request.data.get('photo_url')}")
            logger.info(f"📝 Сформированные telegram_data: {telegram_data}")
            logger.info(f"📝 Текущие данные пользователя: first_name={user.first_name}, last_name={user.last_name}, username={user.username}, telegram_photo_url={user.telegram_photo_url}")
            
            # Синхронизируем данные из Telegram
            updated = user.sync_from_telegram(telegram_data)
            
            logger.info(f"✅ Результат синхронизации: updated={updated}")
            
            if updated:
                # Обновляем last_seen
                user.update_last_seen()
                
                # Возвращаем обновленные данные
                serializer = self.get_serializer(user)
                return Response({
                    'success': True,
                    'message': 'Данные успешно обновлены из Telegram',
                    'user': serializer.data
                })
            else:
                # Данные не изменились, но возвращаем текущие данные
                serializer = self.get_serializer(user)
                return Response({
                    'success': True,
                    'message': 'Данные актуальны',
                    'user': serializer.data
                })
            
        except MiniAppUser.DoesNotExist:
            return Response(
                {'error': 'User not found in this tenant'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Ошибка при обновлении данных из Telegram для telegram_id={telegram_id}: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
        tenant = getattr(self.request, 'tenant', None)
        logger.info(f"🔍 MiniAppUserByTelegramIDView: Ищем пользователя с telegram_id={telegram_id} и tenant={tenant}")
        
        # Проверяем, есть ли пользователь в базе
        user = MiniAppUser.objects.filter(telegram_id=telegram_id, tenant=tenant).first()
        if user:
            logger.info(f"✅ Найден пользователь: ID={user.id}, telegram_id={user.telegram_id}, username={user.username}")
        else:
            logger.warning(f"❌ Пользователь с telegram_id={telegram_id} и tenant={tenant} не найден в базе данных")
        
        return get_object_or_404(MiniAppUser, telegram_id=telegram_id, tenant=tenant)
    
    def get_serializer_class(self):
        """
        Выбирает сериализатор в зависимости от метода.
        """
        if self.request.method in ['PUT', 'PATCH']:
            return MiniAppUserUpdateSerializer
        return MiniAppUserSerializer


class MiniAppUserUpdateByTelegramIDView(generics.UpdateAPIView):
    """
    API для обновления пользователя Mini App по telegram_id.
    Поддерживает загрузку файлов (аватар) и обычные данные.
    """
    queryset = MiniAppUser.objects.all()
    serializer_class = MiniAppUserUpdateSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'telegram_id'
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_object(self):
        """
        Получает объект по telegram_id.
        """
        telegram_id = self.kwargs.get('telegram_id')
        tenant = getattr(self.request, 'tenant', None)
        logger.info(f"🔍 MiniAppUserUpdateByTelegramIDView: Ищем пользователя с telegram_id={telegram_id} и tenant={tenant}")
        
        user = MiniAppUser.objects.filter(telegram_id=telegram_id, tenant=tenant).first()
        if user:
            logger.info(f"✅ Найден пользователь для обновления: ID={user.id}, telegram_id={user.telegram_id}")
        else:
            logger.warning(f"❌ Пользователь с telegram_id={telegram_id} и tenant={tenant} не найден")
            
        return get_object_or_404(MiniAppUser, telegram_id=telegram_id, tenant=tenant)
    
    def update(self, request, *args, **kwargs):
        """
        Переопределяем update для логирования и обработки JSON данных.
        """
        logger.info(f"🔄 Обновление профиля пользователя telegram_id={kwargs.get('telegram_id')}")
        logger.info(f"📝 Данные запроса: {request.data}")
        logger.info(f"📁 Файлы запроса: {request.FILES}")
        
        # Логируем programming_language_ids отдельно для отладки
        # Обрабатываем как QueryDict (form-data) или обычный dict (JSON)
        if hasattr(request.data, 'getlist'):
            # Это QueryDict (form-data запрос)
            programming_language_ids = request.data.getlist('programming_language_ids')
        else:
            # Это обычный dict (JSON запрос)
            programming_language_ids = request.data.get('programming_language_ids')
            # Если это не список, преобразуем в список
            if programming_language_ids is not None and not isinstance(programming_language_ids, list):
                programming_language_ids = [programming_language_ids] if programming_language_ids else []
        
        if programming_language_ids:
            logger.info(f"🔧 programming_language_ids получены: {programming_language_ids} (тип: {type(programming_language_ids)})")
        
        # Сериализатор сам обработает programming_language_ids
        if hasattr(request.data, 'copy'):
            data = request.data.copy()
        else:
            # Для обычного dict используем dict()
            data = dict(request.data)
        
        # Исправляем programming_language_ids для правильной обработки множественных значений
        if programming_language_ids:
            data['programming_language_ids'] = programming_language_ids
            logger.info(f"🔧 Исправленные programming_language_ids: {data['programming_language_ids']}")
        
        logger.info(f"🔄 Данные для сериализатора: {data}")
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data, partial=partial)
        
        if serializer.is_valid():
            logger.info(f"✅ Данные валидны, сохраняем изменения")
            self.perform_update(serializer)
            
            if getattr(instance, '_prefetched_objects_cache', None):
                instance._prefetched_objects_cache = {}
                
            logger.info(f"✅ Профиль успешно обновлен")
            return Response(serializer.data)
        else:
            logger.error(f"❌ Ошибки валидации: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_description="Обновление пользователя Mini App по telegram_id.",
        manual_parameters=[
            openapi.Parameter(
                'telegram_id',
                openapi.IN_PATH,
                description="ID пользователя Telegram.",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'grade',
                openapi.IN_FORM,
                description="Грейд разработчика (junior, middle, senior).",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'programming_language_ids',
                openapi.IN_FORM,
                description="Список ID технологий (JSON строка).",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'gender',
                openapi.IN_FORM,
                description="Пол (male, female).",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'birth_date',
                openapi.IN_FORM,
                description="Дата рождения (YYYY-MM-DD).",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'website',
                openapi.IN_FORM,
                description="Веб-сайт.",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'telegram',
                openapi.IN_FORM,
                description="Telegram username.",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'github',
                openapi.IN_FORM,
                description="GitHub профиль.",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        responses={
            200: MiniAppUserSerializer,
            400: 'Неверные данные',
            404: 'Пользователь не найден'
        }
    )
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class MiniAppProfileByTelegramID(APIView):
    """
    API для получения или создания профиля Mini App пользователя по telegram_id.
    Принимает POST-запрос с данными пользователя.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Ищет MiniAppUser по telegram_id. Если находит - возвращает его
        профиль. Если нет - создает нового пользователя с данными из запроса.
        """
        user_data = request.data
        telegram_id = user_data.get('telegram_id')
        username = user_data.get('username')
        
        logger.info(f"🔍 MiniAppProfileByTelegramID: Получены данные: {user_data}")
        logger.info(f"🔍 MiniAppProfileByTelegramID: telegram_id={telegram_id}, username={username}")

        if not telegram_id:
            return Response(
                {"error": "telegram_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                # Ищем пользователя по telegram_id с учетом тенанта
                tenant = getattr(request, 'tenant', None)
                mini_app_user = MiniAppUser.objects.filter(telegram_id=telegram_id, tenant=tenant).first()

                if not mini_app_user:
                    # Создаем нового MiniAppUser с использованием сериализатора
                    tenant = getattr(request, 'tenant', None)
                    logger.info(
                        f"Создаем нового MiniAppUser для telegram_id={telegram_id}, "
                        f"tenant={tenant} через MiniAppUserCreateSerializer."
                    )
                    if not tenant:
                        logger.error(
                            f"[MiniAppProfileByTelegramID] КРИТИЧНО: tenant=None для telegram_id={telegram_id}! "
                            f"HTTP_HOST={request.META.get('HTTP_HOST')}, "
                            f"X-Forwarded-Host={request.META.get('HTTP_X_FORWARDED_HOST')}"
                        )
                    create_serializer = MiniAppUserCreateSerializer(
                        data=user_data,
                        context={'request': request}
                    )
                    create_serializer.is_valid(raise_exception=True)
                    # Явно передаём tenant — это критично для multi-tenant изоляции
                    mini_app_user = create_serializer.save(tenant=tenant)

                    logger.info(f"✅ Создан MiniAppUser: ID={mini_app_user.id}, telegram_id={mini_app_user.telegram_id}, tenant={mini_app_user.tenant}")
                    
                    # Отправляем уведомление админам о новом пользователе
                    try:
                        from accounts.utils_folder.telegram_notifications import notify_all_admins, escape_markdown, escape_username_for_markdown, get_base_url, format_markdown_link
                        from django.urls import reverse
                        
                        # Формируем ссылку на пользователя в админке с динамическим URL
                        base_url = get_base_url(request)
                        admin_path = reverse('admin:accounts_miniappuser_change', args=[mini_app_user.id])
                        admin_url = f"{base_url}{admin_path}"
                        
                        # Получаем информацию о пользователе
                        author_name = mini_app_user.first_name or mini_app_user.username or "Без имени"
                        escaped_username = escape_username_for_markdown(mini_app_user.username) if mini_app_user.username else None
                        author_username = f"@{escaped_username}" if escaped_username else 'нет'
                        
                        first_name = mini_app_user.first_name or ""
                        last_name = mini_app_user.last_name or ""
                        full_name = f"{first_name} {last_name}".strip() or "Без имени"

                        # Экранируем значения для Markdown
                        escaped_full_name = escape_markdown(full_name)

                        admin_title = "🆕 Новый пользователь Mini App"
                        admin_message = (
                            f"Пользователь: {author_name} ({author_username}, ID: {mini_app_user.telegram_id})\n"
                            f"Имя: {escaped_full_name}\n"
                            f"Дата регистрации: {mini_app_user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                            f"👉 {format_markdown_link('Посмотреть в админке', admin_url)}"
                        )

                        notify_all_admins(
                            notification_type='other',
                            title=admin_title,
                            message=admin_message,
                            related_object_id=mini_app_user.id,
                            related_object_type='message',
                            request=request,
                            tenant=tenant
                        )
                        
                        logger.info(f"📤 Отправлено уведомление о новом пользователе #{mini_app_user.id}")
                        
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки уведомления о новом пользователе: {e}", exc_info=True)
                else:
                    # Если пользователь существует, обновляем его данные, если предоставлены
                    logger.info(f"Найден существующий MiniAppUser для telegram_id {telegram_id}. Обновляем данные.")
                    update_serializer = MiniAppUserUpdateSerializer(mini_app_user, data=user_data, partial=True)
                    update_serializer.is_valid(raise_exception=True)
                    mini_app_user = update_serializer.save()

        except Exception as e:
            logger.exception(f"Критическая ошибка при создании/обновлении MiniAppUser для telegram_id={telegram_id}: {e}")
            return Response({"error": "An internal server error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = MiniAppUserSerializer(mini_app_user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class MiniAppTopUsersListView(TenantFilteredViewMixin, generics.ListAPIView):
    """
    APIView для получения списка топ-пользователей Mini App по рейтингу.
    """
    serializer_class = MiniAppTopUserSerializer
    permission_classes = [permissions.AllowAny]

    def get_serializer_context(self):
        """
        Добавляем request в контекст сериализатора, чтобы
        можно было строить абсолютные URL для аватарок.
        """
        return {'request': self.request}

    def get_queryset(self):
        """
        Возвращает топ-N пользователей Mini App, отсортированных по рейтингу с поддержкой фильтрации.
        """
        # Аннотируем пользователей их рейтингом, используя метод из модели MiniAppUser
        queryset = super().get_queryset().annotate(
            rating=MiniAppUser.get_rating_annotation()
        )
        
        tenant = getattr(self.request, 'tenant', None)
        logger.info(f"[MiniAppTopUsers] Request tenant: {tenant.slug if tenant else 'None'}")
        logger.info(f"[MiniAppTopUsers] Initial queryset count for tenant: {queryset.count()}")
        
        # Применяем фильтры
        gender = self.request.query_params.get('gender')
        age = self.request.query_params.get('age')
        language_pref = self.request.query_params.get('language_pref')
        online_only = self.request.query_params.get('online_only')
        
        if gender:
            queryset = queryset.filter(gender=gender)
        
        if age:
            # Фильтрация по возрастному диапазону
            from datetime import date
            today = date.today()
            
            if age == '18-25':
                birth_year_max = today.year - 18
                birth_year_min = today.year - 25
            elif age == '26-35':
                birth_year_max = today.year - 26
                birth_year_min = today.year - 35
            elif age == '36-45':
                birth_year_max = today.year - 36
                birth_year_min = today.year - 45
            elif age == '46+':
                birth_year_max = today.year - 46
                birth_year_min = today.year - 100  # Предполагаем, что никто не старше 100 лет
            
            queryset = queryset.filter(
                birth_date__year__gte=birth_year_min,
                birth_date__year__lte=birth_year_max
            )
        
        if language_pref:
            # Фильтруем по programming_languages (ManyToManyField), где хранятся все любимые технологии
            # Очищаем значение от лишних пробелов
            language_pref_cleaned = language_pref.strip()
            logger.info(f"🔍 Фильтрация по технологии: '{language_pref_cleaned}' (исходное: '{language_pref}')")
            
            # Используем Q объект для поиска как в новом поле programming_languages (ManyToMany),
            # так и в старом поле programming_language (ForeignKey) для обратной совместимости
            # Это обеспечивает работу фильтра для всех пользователей, независимо от того,
            # где у них сохранены технологии
            
            # Фильтруем по ManyToMany полю - он находит всех пользователей, у которых есть хотя бы одна технология с таким названием
            # Также проверяем старое поле programming_language для обратной совместимости
            queryset = queryset.filter(
                Q(programming_languages__name__iexact=language_pref_cleaned) |
                Q(programming_language__name__iexact=language_pref_cleaned)
            ).distinct()
            
            # Логируем для отладки
            logger.info(f"🔍 После фильтрации по технологии '{language_pref_cleaned}': {queryset.count()} пользователей")
            
            # Дополнительная диагностика: проверяем, какие технологии есть в базе
            if queryset.count() == 0:
                # Если ничего не найдено, проверяем похожие названия для диагностики
                similar_topics = Topic.objects.filter(
                    name__icontains=language_pref_cleaned[:3]  # Первые 3 символа для поиска похожих
                ).values_list('name', flat=True)[:5]
                if similar_topics:
                    logger.warning(f"⚠️ По запросу '{language_pref_cleaned}' ничего не найдено. Похожие темы в базе: {list(similar_topics)}")
        
        if online_only == 'true':
            # Фильтрация только онлайн пользователей (последний визит в течение 5 минут)
            from datetime import timedelta
            from django.utils import timezone
            five_minutes_ago = timezone.now() - timedelta(minutes=5)
            queryset = queryset.filter(last_seen__gte=five_minutes_ago)
        
        # Сортируем по рейтингу, затем по дате создания
        queryset = queryset.order_by('-rating', '-created_at')
        
        # Ограничиваем количество пользователей (например, топ-100)
        return queryset[:100]

    @swagger_auto_schema(
        operation_description="Получение списка топ-пользователей Mini App.",
        responses={
            200: openapi.Response(
                "Список топ-пользователей Mini App",
                MiniAppTopUserSerializer(many=True)
            )
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class MiniAppUserStatisticsView(APIView):
    """
    APIView для получения статистики пользователя Mini App.
    """
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Получение статистики пользователя Mini App по telegram_id.",
        manual_parameters=[
            openapi.Parameter(
                'telegram_id',
                openapi.IN_QUERY,
                description="ID пользователя Telegram.",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
        responses={
            200: openapi.Response(
                "Статистика пользователя Mini App",
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'user': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'telegram_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'username': openapi.Schema(type=openapi.TYPE_STRING),
                                'first_name': openapi.Schema(type=openapi.TYPE_STRING),
                                'last_name': openapi.Schema(type=openapi.TYPE_STRING),
                                'avatar_url': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        ),
                        'stats': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'total_quizzes': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'completed_quizzes': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'success_rate': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'total_points': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'current_streak': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'best_streak': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'favorite_topic': openapi.Schema(type=openapi.TYPE_STRING, description='Любимая тема пользователя'),
                                'favorite_topic_percentage': openapi.Schema(type=openapi.TYPE_INTEGER, description='Процент успеха в любимой теме'),
                            }
                        ),
                        'topic_progress': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'completed': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'percentage': openapi.Schema(type=openapi.TYPE_INTEGER),
                                }
                            )
                        ),
                        'achievements': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'icon': openapi.Schema(type=openapi.TYPE_STRING),
                                    'unlocked': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                }
                            )
                        ),
                    }
                )
            ),
            404: 'Пользователь не найден',
            400: 'Неверные параметры запроса'
        }
    )
    def get(self, request):
        """
        Получает статистику пользователя Mini App по telegram_id.
        """
        telegram_id = request.query_params.get('telegram_id')
        
        if not telegram_id:
            return Response(
                {'error': 'telegram_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Получаем и активируем язык, если он передан
        language = request.query_params.get('language')
        if language:
            activate(language)
        
        try:
            # Получаем пользователя Mini App с учетом тенанта
            tenant = getattr(request, 'tenant', None)
            mini_app_user = MiniAppUser.objects.get(telegram_id=telegram_id, tenant=tenant)
            
            # Получаем статистику из MiniAppTaskStatistics
            from tasks.models import MiniAppTaskStatistics
            
            # Основная статистика пользователя
            # Считаем уникальные translation_group_id вместо отдельных записей
            total_attempts = MiniAppTaskStatistics.objects.filter(mini_app_user=mini_app_user).values('task__translation_group_id').distinct().count()
            successful_attempts = MiniAppTaskStatistics.objects.filter(mini_app_user=mini_app_user, successful=True).values('task__translation_group_id').distinct().count()
            failed_attempts = total_attempts - successful_attempts
            
            user_stats = {
                'total_attempts': total_attempts,
                'successful_attempts': successful_attempts,
                'failed_attempts': failed_attempts
            }
            
            success_rate = (
                round((user_stats['successful_attempts'] / user_stats['total_attempts']) * 100, 1)
                if user_stats['total_attempts'] > 0 else 0
            )
            
            # Прогресс по темам (топ 5)
            # Считаем уникальные translation_group_id для каждой темы
            topic_progress = []
            user_category_stats = MiniAppTaskStatistics.objects.filter(mini_app_user=mini_app_user).values(
                'task__topic__name',
                'task__topic__id'
            ).annotate(
                completed=Count('task__translation_group_id', filter=Q(successful=True), distinct=True),
                total=Count('task__translation_group_id', distinct=True)
            ).order_by('-total')[:5]

            # Определяем лучшую специализацию пользователя
            best_specialization = None
            best_percentage = 0
            
            for stat in user_category_stats:
                topic_name = stat['task__topic__name'] or 'Unknown'
                completed = stat['completed']
                total = stat['total']
                percentage = round((completed / total * 100), 0) if total > 0 else 0

                # Обновляем лучшую специализацию
                if percentage > best_percentage and total >= 3:  # Минимум 3 попытки
                    best_percentage = percentage
                    best_specialization = topic_name

                topic_progress.append({
                    'name': topic_name,
                    'completed': completed,
                    'total': total,
                    'percentage': percentage
                })
            
            # Подсчет очков
            total_points = user_stats['successful_attempts'] * 10
            
            # Серия (streak)
            recent_attempts = MiniAppTaskStatistics.objects.filter(mini_app_user=mini_app_user).order_by('-last_attempt_date')[:10]
            current_streak = 0
            best_streak = 0
            temp_streak = 0
            
            for attempt in recent_attempts:
                if attempt.successful:
                    temp_streak += 1
                    if current_streak == 0:
                        current_streak = temp_streak
                else:
                    if temp_streak > best_streak:
                        best_streak = temp_streak
                    temp_streak = 0
            
            if temp_streak > best_streak:
                best_streak = temp_streak
                
            # Информация о пользователе
            user_info = {
                'telegram_id': mini_app_user.telegram_id,
                'username': mini_app_user.username,
                'first_name': mini_app_user.first_name or mini_app_user.username,
                'last_name': mini_app_user.last_name or '',
                'avatar_url': mini_app_user.avatar.url if mini_app_user.avatar else None
            }
            
            # Достижения с динамической специализацией
            achievements = [
                {'id': 1, 'name': _('Первый шаг'), 'icon': '🏆', 'unlocked': user_stats['total_attempts'] > 0},
                {'id': 2, 'name': _('Знаток {}').format(best_specialization or _("Программирования")), 'icon': '💻', 'unlocked': success_rate > 60, 'specialization': best_specialization},
                {'id': 3, 'name': _('Веб-мастер'), 'icon': '🌐', 'unlocked': False},
                {'id': 4, 'name': _('Серия'), 'icon': '🔥', 'unlocked': current_streak >= 3},
                {'id': 5, 'name': _('Эксперт'), 'icon': '⭐', 'unlocked': success_rate > 90},
                {'id': 6, 'name': _('Скорость'), 'icon': '⚡', 'unlocked': False}
            ]
            
            statistics_data = {
                'user': user_info,
                'stats': {
                    'total_quizzes': user_stats['total_attempts'],
                    'completed_quizzes': user_stats['successful_attempts'],
                    'failed_quizzes': user_stats['failed_attempts'],
                    'success_rate': int(success_rate),
                    'total_points': total_points,
                    'current_streak': current_streak,
                    'best_streak': best_streak,
                    'favorite_topic': best_specialization or 'Не определена',
                    'favorite_topic_percentage': int(best_percentage) if best_percentage > 0 else 0
                },
                'topic_progress': topic_progress,
                'achievements': achievements
            }
            
            return Response(statistics_data)
            
        except MiniAppUser.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Ошибка при получении статистики для telegram_id={telegram_id}: {e}")
            return Response(
                {'error': 'Internal server error'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProgrammingLanguagesListView(generics.ListAPIView):
    """
    APIView для получения списка языков программирования (тем) для фильтрации.
    """
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        """
        Возвращает все темы (языки программирования) отсортированные по названию.
        """
        tenant = getattr(self.request, 'tenant', None)
        return Topic.objects.filter(tenant=tenant).order_by('name')

    @swagger_auto_schema(
        operation_description="Получение списка языков программирования для фильтрации топ пользователей.",
        responses={
            200: openapi.Response(
                "Список языков программирования",
                openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID темы'),
                            'name': openapi.Schema(type=openapi.TYPE_STRING, description='Название языка программирования'),
                        }
                    )
                )
            )
        }
    )
    def get(self, request, *args, **kwargs):
        """
        Возвращает список языков программирования в формате JSON.
        """
        topics = self.get_queryset()
        languages = [
            {
                'id': topic.id,
                'name': topic.name,
                'value': topic.name.lower().replace(' ', '_').replace('#', 'sharp')
            }
            for topic in topics
        ]
        return Response(languages)


class MiniAppUserPublicProfileView(APIView):
    """
    API для получения публичного профиля пользователя Mini App по telegram_id.
    
    Если профиль публичный (is_profile_public=True):
        - Возвращает полную информацию о пользователе
    Если профиль приватный (is_profile_public=False):
        - Возвращает только базовую информацию (аватар, имя, username)
    """
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        operation_description="Получение публичного профиля пользователя Mini App по telegram_id.",
        manual_parameters=[
            openapi.Parameter(
                'telegram_id',
                openapi.IN_PATH,
                description="ID пользователя Telegram.",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: PublicMiniAppUserSerializer,
            404: 'Пользователь не найден'
        }
    )
    def get(self, request, telegram_id):
        """
        Получение публичного профиля пользователя по telegram_id.
        
        Args:
            request: HTTP запрос
            telegram_id: Telegram ID пользователя
            
        Returns:
            Response: JSON с данными профиля (полными или ограниченными в зависимости от is_profile_public)
        """
        try:
            tenant = getattr(request, 'tenant', None)
            # Получаем пользователя по telegram_id с учётом тенанта
            user = MiniAppUser.objects.get(telegram_id=telegram_id, tenant=tenant)
            
            # Сериализуем данные (сериализатор сам проверит is_profile_public и отфильтрует поля)
            serializer = PublicMiniAppUserSerializer(user, context={'request': request})
            
            logger.info(f"✅ Профиль пользователя {telegram_id} успешно получен. Публичный: {user.is_profile_public}")
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except MiniAppUser.DoesNotExist:
            logger.warning(f"❌ Пользователь с telegram_id={telegram_id} не найден")
            return Response(
                {'error': 'User not found', 'detail': 'Пользователь не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при получении профиля пользователя {telegram_id}: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserAvatarUploadView(APIView):
    """
    API для загрузки аватарок пользователя Mini App.
    Поддерживает загрузку до 3 аватарок на пользователя.
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    
    @swagger_auto_schema(
        operation_description="Загрузка новой аватарки для пользователя Mini App (макс. 3)",
        manual_parameters=[
            openapi.Parameter(
                'telegram_id',
                openapi.IN_PATH,
                description="ID пользователя Telegram",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'image',
                openapi.IN_FORM,
                description="Файл изображения аватарки (поддерживаются изображения и GIF)",
                type=openapi.TYPE_FILE,
                required=True
            ),
            openapi.Parameter(
                'order',
                openapi.IN_FORM,
                description="Порядок отображения (0, 1, 2). Если не указан, будет автоматически присвоен следующий доступный",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            201: 'Аватарка успешно загружена',
            400: 'Неверные данные или превышен лимит аватарок',
            404: 'Пользователь не найден'
        }
    )
    def post(self, request, telegram_id):
        """
        Загрузка новой аватарки для пользователя.
        
        Args:
            request: HTTP запрос с файлом изображения
            telegram_id: Telegram ID пользователя
            
        Returns:
            Response: JSON с данными созданной аватарки
        """
        try:
            from ..models import UserAvatar
            from ..serializers import UserAvatarSerializer
            
            # Получаем пользователя
            tenant = getattr(request, 'tenant', None)
            user = MiniAppUser.objects.get(telegram_id=telegram_id, tenant=tenant)
            
            # Проверяем количество существующих аватарок
            existing_count = UserAvatar.objects.filter(user=user).count()
            if existing_count >= 3:
                return Response(
                    {'error': 'Maximum avatars limit reached', 'detail': 'Пользователь может иметь максимум 3 аватарки'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Получаем файл изображения
            image = request.FILES.get('image')
            if not image:
                return Response(
                    {'error': 'Image file is required', 'detail': 'Необходимо предоставить файл изображения'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Определяем порядок
            order = request.data.get('order')
            if order is not None:
                try:
                    order = int(order)
                    # Проверяем, что такой порядок не занят
                    if UserAvatar.objects.filter(user=user, order=order).exists():
                        return Response(
                            {'error': 'Order already exists', 'detail': f'Аватарка с порядком {order} уже существует'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                except (ValueError, TypeError):
                    return Response(
                        {'error': 'Invalid order value', 'detail': 'Порядок должен быть числом'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Автоматически определяем следующий свободный порядок
                used_orders = UserAvatar.objects.filter(user=user).values_list('order', flat=True)
                for i in range(3):
                    if i not in used_orders:
                        order = i
                        break
            
            # Создаем аватарку
            avatar = UserAvatar.objects.create(
                user=user,
                image=image,
                order=order
            )
            
            # Сериализуем и возвращаем
            serializer = UserAvatarSerializer(avatar, context={'request': request})
            logger.info(f"✅ Аватарка успешно загружена для пользователя {telegram_id}, order={order}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except MiniAppUser.DoesNotExist:
            logger.warning(f"❌ Пользователь с telegram_id={telegram_id} не найден")
            return Response(
                {'error': 'User not found', 'detail': 'Пользователь не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            logger.error(f"❌ Ошибка валидации: {e}")
            return Response(
                {'error': 'Validation error', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке аватарки: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserAvatarDeleteView(APIView):
    """
    API для удаления аватарки пользователя Mini App.
    """
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        operation_description="Удаление аватарки пользователя Mini App",
        manual_parameters=[
            openapi.Parameter(
                'telegram_id',
                openapi.IN_PATH,
                description="ID пользователя Telegram",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'avatar_id',
                openapi.IN_PATH,
                description="ID аватарки для удаления",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
        responses={
            204: 'Аватарка успешно удалена',
            403: 'Аватарка не принадлежит пользователю',
            404: 'Пользователь или аватарка не найдены'
        }
    )
    def delete(self, request, telegram_id, avatar_id):
        """
        Удаление аватарки пользователя.
        
        Args:
            request: HTTP запрос
            telegram_id: Telegram ID пользователя
            avatar_id: ID аватарки для удаления
            
        Returns:
            Response: Пустой ответ с кодом 204
        """
        try:
            from ..models import UserAvatar
            
            # Получаем пользователя
            tenant = getattr(request, 'tenant', None)
            user = MiniAppUser.objects.get(telegram_id=telegram_id, tenant=tenant)
            
            # Получаем аватарку
            avatar = UserAvatar.objects.get(id=avatar_id)
            
            # Проверяем, что аватарка принадлежит этому пользователю
            if avatar.user != user:
                return Response(
                    {'error': 'Permission denied', 'detail': 'Аватарка не принадлежит пользователю'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Удаляем аватарку (файл удалится автоматически благодаря Django)
            avatar.delete()
            
            logger.info(f"✅ Аватарка {avatar_id} успешно удалена для пользователя {telegram_id}")
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except MiniAppUser.DoesNotExist:
            logger.warning(f"❌ Пользователь с telegram_id={telegram_id} не найден")
            return Response(
                {'error': 'User not found', 'detail': 'Пользователь не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        except UserAvatar.DoesNotExist:
            logger.warning(f"❌ Аватарка с id={avatar_id} не найдена")
            return Response(
                {'error': 'Avatar not found', 'detail': 'Аватарка не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при удалении аватарки: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserAvatarReorderView(APIView):
    """
    API для изменения порядка аватарок пользователя Mini App.
    """
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        operation_description="Изменение порядка аватарок пользователя Mini App",
        manual_parameters=[
            openapi.Parameter(
                'telegram_id',
                openapi.IN_PATH,
                description="ID пользователя Telegram",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'avatar_orders': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID аватарки'),
                            'order': openapi.Schema(type=openapi.TYPE_INTEGER, description='Новый порядок (0, 1, 2)')
                        }
                    ),
                    description='Массив объектов с ID аватарки и новым порядком'
                )
            },
            example={'avatar_orders': [{'id': 1, 'order': 0}, {'id': 2, 'order': 1}, {'id': 3, 'order': 2}]}
        ),
        responses={
            200: 'Порядок аватарок успешно обновлен',
            400: 'Неверные данные',
            403: 'Аватарка не принадлежит пользователю',
            404: 'Пользователь не найден'
        }
    )
    def patch(self, request, telegram_id):
        """
        Изменение порядка аватарок пользователя.
        
        Args:
            request: HTTP запрос с данными о новом порядке
            telegram_id: Telegram ID пользователя
            
        Returns:
            Response: JSON с обновленными данными аватарок
        """
        try:
            from ..models import UserAvatar
            from ..serializers import UserAvatarSerializer
            
            # Получаем пользователя
            tenant = getattr(request, 'tenant', None)
            user = MiniAppUser.objects.get(telegram_id=telegram_id, tenant=tenant)
            
            # Получаем данные о новом порядке
            avatar_orders = request.data.get('avatar_orders', [])
            if not avatar_orders:
                return Response(
                    {'error': 'avatar_orders is required', 'detail': 'Необходимо предоставить массив с порядком аватарок'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Обновляем порядок каждой аватарки
            updated_avatars = []
            for item in avatar_orders:
                avatar_id = item.get('id')
                new_order = item.get('order')
                
                if avatar_id is None or new_order is None:
                    continue
                
                try:
                    avatar = UserAvatar.objects.get(id=avatar_id)
                    
                    # Проверяем, что аватарка принадлежит этому пользователю
                    if avatar.user != user:
                        return Response(
                            {'error': 'Permission denied', 'detail': f'Аватарка {avatar_id} не принадлежит пользователю'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                    
                    # Обновляем порядок
                    avatar.order = new_order
                    avatar.save()
                    updated_avatars.append(avatar)
                    
                except UserAvatar.DoesNotExist:
                    logger.warning(f"⚠️ Аватарка с id={avatar_id} не найдена, пропускаем")
                    continue
            
            # Сериализуем и возвращаем обновленные аватарки
            serializer = UserAvatarSerializer(updated_avatars, many=True, context={'request': request})
            logger.info(f"✅ Порядок аватарок успешно обновлен для пользователя {telegram_id}")
            return Response({'avatars': serializer.data}, status=status.HTTP_200_OK)
            
        except MiniAppUser.DoesNotExist:
            logger.warning(f"❌ Пользователь с telegram_id={telegram_id} не найден")
            return Response(
                {'error': 'User not found', 'detail': 'Пользователь не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при изменении порядка аватарок: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) 