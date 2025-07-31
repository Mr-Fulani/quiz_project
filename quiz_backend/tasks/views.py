from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404

from .models import Task, TaskStatistics
from topics.models import Subtopic
from .serializers import (
    TaskSerializer,
    TaskStatisticsSerializer,
    TaskSubmitSerializer,
    TaskStatsResponseSerializer,
    TaskSkipSerializer
)


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

@api_view(['GET'])
@permission_classes([AllowAny])
def tasks_by_subtopic(request, subtopic_id):
    """
    Получение задач для подтемы с учетом языка
    """
    try:
        subtopic = get_object_or_404(Subtopic, id=subtopic_id)
        language = request.query_params.get('language', 'en')
        
        # Получаем задачи с переводами на нужном языке
        tasks = Task.objects.filter(
            subtopic=subtopic,
            published=True,
            translations__language=language
        ).select_related('topic', 'subtopic').prefetch_related(
            'translations'
        )
        
        # Подготавливаем данные для мини-приложения
        tasks_data = []
        for task in tasks:
            translation = task.translations.filter(language=language).first()
            if translation:
                # Перемешиваем варианты ответов
                import random
                import json
                
                try:
                    answers = translation.answers if isinstance(translation.answers, list) else json.loads(translation.answers)
                except (json.JSONDecodeError, TypeError):
                    answers = []
                
                # Перемешиваем ответы
                shuffled_answers = answers[:]
                random.shuffle(shuffled_answers)
                
                # Добавляем опцию "Не знаю"
                dont_know_options = {
                    'ru': 'Я не знаю, но хочу узнать',
                    'en': 'I don\'t know, but I want to learn'
                }
                dont_know_option = dont_know_options.get(language, dont_know_options['en'])
                shuffled_answers.append(dont_know_option)
                
                task_data = {
                    'id': task.id,
                    'topic_id': task.topic.id,
                    'subtopic_id': task.subtopic.id,
                    'difficulty': task.difficulty,
                    'image_url': task.image_url,
                    'question': translation.question,
                    'answers': shuffled_answers,
                    'correct_answer': translation.correct_answer,
                    'explanation': translation.explanation or '',
                    'is_solved': False  # Для мини-приложения пока всегда False
                }
                tasks_data.append(task_data)
        
        return Response({
            'results': tasks_data,
            'count': len(tasks_data),
            'subtopic_name': subtopic.name,
            'topic_name': subtopic.topic.name
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
