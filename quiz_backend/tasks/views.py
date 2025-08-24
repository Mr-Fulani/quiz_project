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

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import Task, TaskTranslation, MiniAppTaskStatistics
from accounts.models import MiniAppUser

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
def submit_mini_app_task_answer(request, task_id):
    """
    API эндпоинт для отправки ответов на задачи из мини-аппа.
    
    Принимает telegram_id и ответ, сохраняет статистику в MiniAppTaskStatistics.
    """
    
    try:
        # Получаем данные из запроса
        telegram_id = request.data.get('telegram_id')
        selected_answer = request.data.get('answer')
        
        if not telegram_id:
            return Response(
                {'error': 'telegram_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not selected_answer:
            return Response(
                {'error': 'answer is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Получаем задачу
        task = get_object_or_404(Task, id=task_id, published=True)
        
        # Получаем пользователя мини-аппа
        try:
            mini_app_user = MiniAppUser.objects.get(telegram_id=telegram_id)
        except MiniAppUser.DoesNotExist:
            logger.error(f"MiniAppUser с telegram_id {telegram_id} не найден")
            return Response(
                {'error': 'Mini App user not found. User must be initialized first.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Получаем перевод задачи
        language = mini_app_user.language or 'en'
        translation = (TaskTranslation.objects.filter(task=task, language=language).first() or
                      TaskTranslation.objects.filter(task=task).first())
        
        if not translation:
            return Response(
                {'error': 'No translation available for this task'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверяем правильность ответа
        is_correct = selected_answer == translation.correct_answer
        
        # Сохраняем статистику
        stats, created = MiniAppTaskStatistics.objects.get_or_create(
            mini_app_user=mini_app_user,
            task=task,
            defaults={
                'attempts': 1,
                'successful': is_correct,
                'selected_answer': selected_answer
            }
        )
        
        if not created:
            # Если статистика уже существует, обновляем её
            stats.attempts += 1
            stats.successful = is_correct
            stats.selected_answer = selected_answer
            stats.save()
        
        # Обновляем время последнего визита пользователя
        mini_app_user.update_last_seen()
        
        # Формируем результаты для отображения статистики
        total_votes = task.statistics.count() + task.mini_app_statistics.count() + 1
        
        # Получаем варианты ответов
        if isinstance(translation.answers, str):
            import json
            answers = json.loads(translation.answers)
        else:
            answers = translation.answers
        
        results = []
        for answer in answers:
            # Подсчитываем голоса из основной статистики
            main_votes = task.statistics.filter(selected_answer=answer).count()
            # Подсчитываем голоса из статистики мини-аппа
            mini_app_votes = task.mini_app_statistics.filter(selected_answer=answer).count()
            total_answer_votes = main_votes + mini_app_votes
            
            # Если это выбранный ответ, добавляем 1
            if answer == selected_answer:
                total_answer_votes += 1
            
            percentage = (total_answer_votes / total_votes * 100) if total_votes > 0 else 0
            results.append({
                'text': answer,
                'is_correct': answer == translation.correct_answer,
                'percentage': round(percentage, 1)
            })
        
        return Response({
            'status': 'success',
            'is_correct': is_correct,
            'selected_answer': selected_answer,
            'results': results,
            'explanation': translation.explanation or 'No explanation available.',
            'total_attempts': stats.attempts,
            'successful_attempts': 1 if is_correct else 0
        })
        
    except Exception as e:
        logger.error(f"Error in submit_mini_app_task_answer: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
