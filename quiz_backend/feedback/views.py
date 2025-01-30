from django.shortcuts import render
from rest_framework import generics, permissions
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
