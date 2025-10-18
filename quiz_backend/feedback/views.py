from django.shortcuts import render
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, AllowAny

from .models import FeedbackMessage
from .serializers import FeedbackSerializer
from .filters import FeedbackFilter


# Create your views here.

class CustomPageNumberPagination(PageNumberPagination):
    """
    Кастомная пагинация для API
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class FeedbackListCreateView(generics.ListCreateAPIView):
    """
    API endpoint для списка и создания отзывов.
    
    GET: Получение списка отзывов
    - Для админов: все отзывы
    - Для пользователей: только свои отзывы
    
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
        if self.request.user.is_staff:
            return FeedbackMessage.objects.all()
        return FeedbackMessage.objects.filter(user_id=self.request.user.id)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class FeedbackDetailView(generics.RetrieveAPIView):
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
        if self.request.user.is_staff:
            return FeedbackMessage.objects.all()
        return FeedbackMessage.objects.filter(user_id=self.request.user.id)

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

class FeedbackListView(generics.ListAPIView):
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
    
    Принимает данные в формате:
    {
        "user_id": 123456789,
        "username": "user_name",
        "message": "Текст сообщения",
        "category": "bug",  # опционально
        "source": "mini_app"
    }
    """
    try:
        user_id = request.data.get('user_id')
        username = request.data.get('username', '')
        message = request.data.get('message', '')
        category = request.data.get('category', 'other')
        source = request.data.get('source', 'mini_app')
        
        # Валидация данных
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not message or len(message) < 3:
            return Response(
                {'error': 'message is required and must be at least 3 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Создаем сообщение обратной связи
        feedback = FeedbackMessage.objects.create(
            user_id=user_id,
            username=username,
            message=message,
            category=category,
            source=source,
            is_processed=False
        )
        
        return Response(
            {
                'success': True,
                'message': 'Feedback submitted successfully',
                'feedback_id': feedback.id
            },
            status=status.HTTP_201_CREATED
        )
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
