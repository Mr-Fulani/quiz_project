from django.shortcuts import render
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, AllowAny
import logging

from tenants.mixins import TenantFilteredViewMixin
from .models import FeedbackMessage, FeedbackImage
from .serializers import FeedbackSerializer
from .filters import FeedbackFilter

logger = logging.getLogger(__name__)


# Create your views here.

class CustomPageNumberPagination(PageNumberPagination):
    """
    Кастомная пагинация для API
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class FeedbackListCreateView(TenantFilteredViewMixin, generics.ListCreateAPIView):
    """
    API endpoint для списка и создания отзывов.
    
    GET: Получение списка отзывов
    - Для админов: все отзывы (в рамках тенанта)
    - Для пользователей: только свои отзывы (в рамках тенанта)
    
    POST: Создание нового отзыва
    - Доступно всем авторизованным пользователям
    """
    queryset = FeedbackMessage.objects.all()
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = FeedbackFilter
    ordering_fields = ['created_at', 'is_processed']
    ordering = ['-created_at']
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs
        return qs.filter(user_id=self.request.user.id)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class FeedbackDetailView(TenantFilteredViewMixin, generics.RetrieveAPIView):
    """
    API endpoint для просмотра, обновления и удаления отзыва.
    
    - GET: Доступно владельцу отзыва и админам
    - PUT/PATCH: Только админы могут обновлять статус
    - DELETE: Только админы могут удалять отзывы
    """
    queryset = FeedbackMessage.objects.all()
    serializer_class = FeedbackSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs
        return qs.filter(user_id=self.request.user.id)

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

class FeedbackListView(TenantFilteredViewMixin, generics.ListAPIView):
    queryset = FeedbackMessage.objects.all()
    serializer_class = FeedbackSerializer
    permission_classes = [IsAdminUser]

class FeedbackCreateView(generics.CreateAPIView):
    queryset = FeedbackMessage.objects.all()
    serializer_class = FeedbackSerializer
    permission_classes = [AllowAny]


@api_view(['POST'])
@permission_classes([AllowAny])
def submit_feedback_from_mini_app(request):
    """
    API endpoint для отправки обратной связи из мини-аппа.
    
    Принимает данные в формате multipart/form-data:
    - user_id: Telegram ID пользователя
    - username: Имя пользователя
    - message: Текст сообщения
    - category: Категория (bug, suggestion, complaint, other)
    - source: Источник (mini_app)
    - images: Массив изображений (до 3 файлов, макс 5MB каждый)
    """
    try:
        logger.info("=" * 50)
        logger.info("Получен запрос на создание feedback")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Request data: {request.data}")
        logger.info(f"Request FILES: {request.FILES}")
        
        user_id = request.data.get('user_id') or request.data.get('telegram_id')
        username = request.data.get('username', '')
        message = request.data.get('message', '')
        category = request.data.get('category', 'other')
        source = request.data.get('source', 'mini_app')
        
        # Валидация данных
        if not user_id:
            return Response(
                {'error': 'user_id or telegram_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not message or len(message) < 3:
            return Response(
                {'error': 'message is required and must be at least 3 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Обрабатываем изображения
        images = request.FILES.getlist('images')
        
        # Валидация изображений
        if images:
            # Проверка количества
            if len(images) > 3:
                return Response(
                    {'error': 'Максимум 3 изображения'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Проверка размера и типа каждого файла
            MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
            ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
            
            for idx, image in enumerate(images):
                # Проверка размера
                if image.size > MAX_FILE_SIZE:
                    return Response(
                        {'error': f'Изображение {idx + 1}: размер не должен превышать 5 MB (текущий: {image.size / (1024*1024):.2f} MB)'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Проверка типа
                if image.content_type not in ALLOWED_TYPES:
                    return Response(
                        {'error': f'Изображение {idx + 1}: недопустимый формат ({image.content_type}). Разрешены: JPEG, PNG, GIF, WebP'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                logger.info(f"Валидация изображения {idx + 1}: размер={image.size / 1024:.1f}KB, тип={image.content_type}")
        
        # Получаем тенант
        tenant = getattr(request, 'tenant', None)
        
        # Создаем сообщение обратной связи
        feedback = FeedbackMessage.objects.create(
            tenant=tenant,
            user_id=user_id,
            username=username,
            message=message,
            category=category,
            source=source,
            is_processed=False
        )
        
        logger.info(f"✅ Создано сообщение обратной связи ID={feedback.id}")
        
        # Сохраняем изображения
        for image in images:
            FeedbackImage.objects.create(
                feedback=feedback,
                image=image
            )
            logger.info(f"✅ Сохранено изображение для feedback ID={feedback.id}")
        
        # Отправляем уведомление админам о новом обращении
        try:
            from accounts.utils_folder.telegram_notifications import notify_all_admins, escape_markdown, escape_username_for_markdown, get_base_url, format_markdown_link
            from accounts.models import MiniAppUser
            from django.urls import reverse
            
            # Получаем полную информацию о пользователе
            try:
                # Фильтруем по тенанту!
                mini_user_qs = MiniAppUser.objects.filter(telegram_id=user_id)
                if tenant:
                    mini_user_qs = mini_user_qs.filter(tenant=tenant)
                
                mini_user = mini_user_qs.first()
                if mini_user:
                    author_name = mini_user.first_name or mini_user.username or 'Без имени'
                    escaped_username = escape_username_for_markdown(mini_user.username) if mini_user.username else None
                    author_username = f"@{escaped_username}" if escaped_username else 'нет'
                else:
                    raise MiniAppUser.DoesNotExist()
            except MiniAppUser.DoesNotExist:
                author_name = username or "Без имени"
                escaped_username = escape_username_for_markdown(username) if username else None
                author_username = f"@{escaped_username}" if escaped_username else 'нет'
            
            # Получаем категорию
            category_display = dict(FeedbackMessage.CATEGORY_CHOICES).get(category, category)
            
            # Формируем ссылку на feedback в админке с динамическим URL
            # Используем get_base_url(None) для использования settings.SITE_URL,
            # так как request может не содержать правильных заголовков от прокси
            base_url = get_base_url(None)
            admin_path = reverse('admin:feedback_feedbackmessage_change', args=[feedback.id])
            admin_url = f"{base_url}{admin_path}"
            
            # Экранируем значения для Markdown
            escaped_category = escape_markdown(str(category_display))
            escaped_message = escape_markdown(message[:200]) if message else ""

            admin_title = "📩 Новое обращение в поддержку"
            admin_message = (
                f"От: {author_name} ({author_username}, ID: {user_id})\n"
                f"Категория: {escaped_category}\n\n"
                f"Сообщение: {escaped_message}\n\n"
                f"👉 {format_markdown_link('Посмотреть в админке', admin_url)}"
            )
            
            logger.info(f"📤 Отправка уведомления о feedback #{feedback.id} с URL: {admin_url}")
            
            notify_all_admins(
                notification_type='feedback',
                title=admin_title,
                message=admin_message,
                related_object_id=feedback.id,
                related_object_type='feedback',
                request=request
            )
            
            logger.info(f"✅ Уведомление о feedback #{feedback.id} отправлено админам")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о feedback: {e}", exc_info=True)
        
        return Response(
            {
                'success': True,
                'message': 'Feedback submitted successfully',
                'feedback_id': feedback.id,
                'images_count': len(images)
            },
            status=status.HTTP_201_CREATED
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания feedback: {str(e)}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
