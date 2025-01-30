from django.shortcuts import render
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Avg, F, Sum, Case, When
from django.utils import timezone
from .models import Task, TaskTranslation, TaskStatistics
from .serializers import (
    TaskSerializer, 
    TaskTranslationSerializer,
    TaskStatisticsSerializer,
    TaskSubmitSerializer,
    TaskStatsResponseSerializer,
    TaskSkipSerializer
)
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from .pagination import CustomPageNumberPagination
from .filters import TaskFilter
from rest_framework.permissions import IsAuthenticated, IsAdminUser

# Create your views here.

class TaskListView(generics.ListAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

class TaskDetailView(generics.RetrieveAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

class TaskCreateView(generics.CreateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAdminUser]

class TaskSubmitView(generics.GenericAPIView):
    serializer_class = TaskSubmitSerializer
    queryset = Task.objects.all()
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Task.objects.none()
        return super().get_queryset()

    def post(self, request, pk):
        task = self.get_object()
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Ваша логика обработки ответа
            return Response({'status': 'success'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TaskSkipView(APIView):
    serializer_class = TaskSkipSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        task = Task.objects.get(pk=pk)
        stats, created = TaskStatistics.objects.get_or_create(
            user=request.user,
            task=task,
            defaults={'attempts': 0, 'successful': False}
        )
        stats.attempts += 1
        stats.save()
        return Response({'status': 'skipped'})

class NextTaskView(APIView):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Получаем следующую задачу (пока простая логика)
        task = Task.objects.filter(published=True).first()
        if not task:
            return Response({'message': 'No tasks available'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = TaskSerializer(task)
        return Response(serializer.data)

class TaskStatsView(generics.ListAPIView):
    serializer_class = TaskStatisticsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TaskStatistics.objects.filter(user=self.request.user)

class UserTaskStatsView(generics.GenericAPIView):
    serializer_class = TaskStatsResponseSerializer
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TaskStatistics.objects.none()
        return TaskStatistics.objects.filter(user=self.request.user)

    def get(self, request):
        # Ваша логика
        return Response({
            'total_tasks': 0,
            'completed_tasks': 0,
            'success_rate': 0.0,
            'average_time': 0.0,
            'total_points': 0
        })

class TopicTaskStatsView(generics.GenericAPIView):
    serializer_class = TaskStatsResponseSerializer
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TaskStatistics.objects.none()
        return TaskStatistics.objects.filter(user=self.request.user)

    def get(self, request, topic_id):
        # Ваша логика
        return Response({
            'total_tasks': 0,
            'completed_tasks': 0,
            'success_rate': 0.0,
            'average_time': 0.0,
            'total_points': 0
        })
