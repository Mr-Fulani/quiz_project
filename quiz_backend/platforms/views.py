from django.shortcuts import render
from rest_framework import generics, permissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from .models import TelegramGroup
from .serializers import TelegramChannelSerializer
from .filters import TelegramChannelFilter

from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta

from accounts.models import UserChannelSubscription
from tasks.pagination import CustomPageNumberPagination

from rest_framework.permissions import IsAdminUser


# Create your views here.

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Разрешение, которое позволяет только админам доступ к API
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)

class TelegramChannelListView(generics.ListCreateAPIView):
    """
    API endpoint для списка и создания Telegram каналов.
    
    Поддерживает:
    - Пагинацию
    - Фильтрацию по различным параметрам
    - Сортировку по дате создания и названию
    
    Permissions:
    - Просмотр: Авторизованные пользователи
    - Создание: Только админы
    """
    queryset = TelegramGroup.objects.all()
    serializer_class = TelegramChannelSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = TelegramChannelFilter
    ordering_fields = ['created_at', 'group_name']
    ordering = ['id']
    pagination_class = CustomPageNumberPagination

class TelegramChannelDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint для просмотра, обновления и удаления Telegram канала.
    
    Permissions:
    - Просмотр: Авторизованные пользователи
    - Обновление/Удаление: Только админы
    """
    queryset = TelegramGroup.objects.all()
    serializer_class = TelegramChannelSerializer
    permission_classes = [IsAdminOrReadOnly]

class ChannelStatsView(APIView):
    """
    API endpoint для получения статистики по каналам.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Базовая статистика
        total_channels = TelegramGroup.objects.count()
        active_channels = TelegramGroup.objects.filter(is_active=True).count()
        
        # Статистика по языкам
        language_stats = TelegramGroup.objects.values('language')\
            .annotate(count=Count('id'))
        
        # Статистика по типам
        type_stats = TelegramGroup.objects.values('location_type')\
            .annotate(count=Count('id'))
        
        # Статистика по подписчикам
        subscriber_stats = {
            'total': UserChannelSubscription.objects.count(),
            'active': UserChannelSubscription.objects.filter(is_active=True).count(),
            'avg_per_channel': UserChannelSubscription.objects.values('channel')\
                .annotate(count=Count('id'))\
                .aggregate(avg=Avg('count'))['avg']
        }

        return Response({
            'total_channels': total_channels,
            'active_channels': active_channels,
            'language_distribution': language_stats,
            'type_distribution': type_stats,
            'subscriber_stats': subscriber_stats
        })

class ChannelHealthCheckView(APIView):
    """
    API endpoint для проверки состояния каналов.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        channels = TelegramGroup.objects.all()
        health_status = []

        for channel in channels:
            # Проверяем последнюю активность
            last_activity = channel.last_activity_at or channel.created_at
            is_active = (timezone.now() - last_activity) < timedelta(days=7)
            
            # Проверяем количество подписчиков
            subscriber_count = channel.channel_subscriptions.filter(is_active=True).count()
            
            health_status.append({
                'channel_id': channel.id,
                'group_name': channel.group_name,
                'is_active': is_active,
                'last_activity': last_activity,
                'subscriber_count': subscriber_count,
                'health_score': self._calculate_health_score(is_active, subscriber_count)
            })

        return Response(health_status)

    def _calculate_health_score(self, is_active, subscriber_count):
        """Рассчитывает оценку здоровья канала от 0 до 100."""
        score = 0
        if is_active:
            score += 50
        if subscriber_count > 0:
            score += min(50, subscriber_count)
        return score
