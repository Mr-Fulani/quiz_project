from django.shortcuts import render
from rest_framework import generics, permissions
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import Topic, Subtopic
from .serializers import TopicSerializer, SubtopicSerializer, TopicMiniAppSerializer, SubtopicWithTasksSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import models
from django.db.models import Count
from tasks.models import TaskTranslation, MiniAppTaskStatistics
import logging

logger = logging.getLogger(__name__)

# Create your views here.

# Views для тем
class TopicListView(generics.ListAPIView):
    """
    Список всех тем.
    """
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    permission_classes = [permissions.IsAuthenticated]

class TopicDetailView(generics.RetrieveAPIView):
    """
    Детальная информация о теме.
    """
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    permission_classes = [permissions.IsAuthenticated]

class TopicCreateView(generics.CreateAPIView):
    """
    Создание новой темы.
    """
    serializer_class = TopicSerializer
    permission_classes = [permissions.IsAdminUser]

class TopicUpdateView(generics.UpdateAPIView):
    """
    Обновление темы.
    """
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    permission_classes = [permissions.IsAdminUser]

class TopicDeleteView(generics.DestroyAPIView):
    """
    Удаление темы.
    """
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    permission_classes = [permissions.IsAdminUser]

# Новый endpoint для мини-приложения
class TopicMiniAppListView(generics.ListAPIView):
    """
    Список всех тем для мини-приложения (без аутентификации).
    Включает дополнительные поля для UI.
    """
    queryset = Topic.objects.all()
    serializer_class = TopicMiniAppSerializer
    permission_classes = []  # Открытый доступ для мини-приложения
    
    def get_queryset(self):
        queryset = Topic.objects.all()
        
        # Поддержка поиска
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        # Поддержка фильтрации по сложности (если добавим это поле)
        # difficulty = self.request.query_params.get('difficulty', None)
        # if difficulty:
        #     queryset = queryset.filter(difficulty=difficulty)
        
        return queryset

# Views для подтем
class SubtopicListView(generics.ListAPIView):
    """
    Список подтем для конкретной темы.
    """
    serializer_class = SubtopicSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Subtopic.objects.filter(topic_id=self.kwargs['topic_id'])

class SubtopicDetailView(generics.RetrieveAPIView):
    """
    Детальная информация о подтеме.
    """
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer
    permission_classes = [permissions.IsAuthenticated]

class SubtopicCreateView(generics.CreateAPIView):
    """
    Создание новой подтемы.
    """
    serializer_class = SubtopicSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        serializer.save(topic_id=self.kwargs['topic_id'])

class SubtopicUpdateView(generics.UpdateAPIView):
    """
    Обновление подтемы.
    """
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer
    permission_classes = [permissions.IsAdminUser]

class SubtopicDeleteView(generics.DestroyAPIView):
    """
    Удаление подтемы.
    """
    queryset = Subtopic.objects.all()
    serializer_class = SubtopicSerializer
    permission_classes = [permissions.IsAdminUser]

class TopicSubtopicsView(generics.ListCreateAPIView):
    serializer_class = SubtopicWithTasksSerializer  # Используем новый сериализатор
    permission_classes = [AllowAny]  # Разрешаем доступ без аутентификации для mini_app

    def get_queryset(self):
        # Получаем язык из query параметров, по умолчанию английский
        language = self.request.query_params.get('language', 'en')
        queryset = Subtopic.objects.filter(topic_id=self.kwargs['topic_id'])
        
        # Аннотируем количество задач (distinct по задачам) на активном языке и фильтруем только те, где >0
        queryset = queryset.annotate(
            tasks_count=Count(
                'tasks',
                filter=models.Q(
                    tasks__published=True,
                    tasks__translations__language=language
                ),
                distinct=True
            )
        ).filter(tasks_count__gt=0)

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        telegram_id = self.request.query_params.get('telegram_id', None)
        context['telegram_id'] = telegram_id
        return context

    def perform_create(self, serializer):
        serializer.save(topic_id=self.kwargs['topic_id'])

# Простой тестовый endpoint для мини-приложения
@api_view(['GET'])
@permission_classes([AllowAny])
def topics_simple(request):
    """
    Простой endpoint для мини-приложения с поддержкой поиска и языка
    """
    topics = Topic.objects.all()
    
    # Добавляем поддержку поиска
    search = request.GET.get('search', None)
    if search:
        topics = topics.filter(name__icontains=search)
    
    # Получаем язык из query параметров
    language = request.GET.get('language', 'en')
    telegram_id = request.GET.get('telegram_id', None)
    
    # Аннотируем количество задач (distinct по задачам) на активном языке и оставляем только темы, где >0
    topics = topics.annotate(
        tasks_count=Count(
            'tasks',
            filter=models.Q(
                tasks__published=True,
                tasks__translations__language=language
            ),
            distinct=True
        )
    ).filter(tasks_count__gt=0)
    
    # Если передан telegram_id, аннотируем количество задач с попытками пользователя (любая попытка)
    if telegram_id:
        topics = topics.annotate(
            completed_tasks_count=Count(
                'tasks',
                filter=models.Q(
                    tasks__mini_app_statistics__mini_app_user__telegram_id=telegram_id
                ),
                distinct=True
            )
        )
    
    data = []
    for topic in topics:
        # Определяем URL медиа для карточки
        from django.conf import settings
        media_url = f'https://picsum.photos/800/800?{topic.id}'  # Fallback
        if topic.media_type == 'image' and topic.card_image:
            media_url = f"{settings.MEDIA_URL}{topic.card_image.name}"
        elif topic.media_type == 'video' and topic.card_video:
            media_url = f"{settings.MEDIA_URL}{topic.card_video.name}"
        elif topic.icon and topic.icon != '/static/blog/images/icons/default-icon.png':
            media_url = topic.icon
        
        topic_data = {
            'id': topic.id,
            'name': topic.name,
            'description': topic.description or f'Изучение {topic.name}',
            'icon': topic.icon,
            'difficulty': 'Средний',  # Временно статично
            'questions_count': topic.tasks_count, # Используем аннотированное количество
            'image_url': media_url,
            'media_type': topic.media_type,  # Добавляем тип медиа
        }
        if telegram_id:
            topic_data['completed_tasks_count'] = topic.completed_tasks_count
        data.append(topic_data)
    return Response(data)

# Endpoint для деталей темы без аутентификации
@api_view(['GET'])
@permission_classes([AllowAny])
def topic_detail_simple(request, topic_id):
    """
    Детальная информация о теме для мини-приложения (без аутентификации)
    """
    try:
        topic = Topic.objects.get(id=topic_id)
        
        # Получаем язык из query параметров
        language = request.GET.get('language', 'en')
        telegram_id = request.GET.get('telegram_id', None)
        
        # Подсчитываем количество задач на активном языке (distinct по задачам)
        tasks_count = topic.tasks.filter(
            published=True,
            translations__language=language
        ).values('id').distinct().count()
        
        completed_tasks_count = 0
        if telegram_id:
            # Считаем любые попытки пользователя по задачам темы
            from tasks.models import MiniAppTaskStatistics
            completed_tasks_count = MiniAppTaskStatistics.objects.filter(
                mini_app_user__telegram_id=telegram_id,
                task__topic=topic
            ).values('task').distinct().count()
        
        # Определяем URL медиа для карточки
        from django.conf import settings
        media_url = f'https://picsum.photos/800/800?{topic.id}'  # Fallback
        if topic.media_type == 'image' and topic.card_image:
            media_url = f"{settings.MEDIA_URL}{topic.card_image.name}"
        elif topic.media_type == 'video' and topic.card_video:
            media_url = f"{settings.MEDIA_URL}{topic.card_video.name}"
        elif topic.icon and topic.icon != '/static/blog/images/icons/default-icon.png':
            media_url = topic.icon
        
        data = {
            'id': topic.id,
            'name': topic.name,
            'description': topic.description or f'Изучение {topic.name}',
            'icon': topic.icon,
            'difficulty': 'Средний',  # Временно статично
            'questions_count': tasks_count,
            'image_url': media_url,
            'media_type': topic.media_type,  # Добавляем тип медиа
            'completed_tasks_count': completed_tasks_count
        }
        return Response(data)
    except Topic.DoesNotExist:
        return Response({'error': 'Topic not found'}, status=404)

# Endpoint для деталей подтемы без аутентификации
@api_view(['GET'])
@permission_classes([AllowAny])
def subtopic_detail_simple(request, subtopic_id):
    """
    Детальная информация о подтеме для мини-приложения (без аутентификации)
    Включает задачи для подтемы, с возможностью фильтрации по уровню сложности.
    """
    try:
        subtopic = Subtopic.objects.get(id=subtopic_id)
        
        # Получаем язык из query параметров
        language = request.GET.get('language', 'en')
        telegram_id = request.GET.get('telegram_id', None)
        level = request.GET.get('level', None) # Получаем параметр уровня сложности
        
        logger.info(f"subtopic_detail_simple: Получен запрос для subtopic_id={subtopic_id}, lang={language}, level={level}")

        # Получаем задачи с переводами на нужном языке
        from tasks.models import Task, TaskTranslation
        
        tasks = Task.objects.filter(
            subtopic=subtopic,
            published=True,
            translations__language=language
        )
        logger.info(f"subtopic_detail_simple: Задач до фильтрации по сложности: {tasks.count()}")

        # Применяем фильтр по уровню сложности, если он указан
        if level in ['easy', 'medium', 'hard']:
            tasks = tasks.filter(difficulty__iexact=level)
            logger.info(f"subtopic_detail_simple: Задач после фильтрации по сложности ('{level}'): {tasks.count()}")
            for task in tasks:
                logger.info(f"  - Task ID: {task.id}, Difficulty: {task.difficulty}")
        elif level == 'all':
            logger.info(f"subtopic_detail_simple: Уровень \'all\' указан, фильтрация по сложности не применяется.")
        else:
            logger.info(f"subtopic_detail_simple: Уровень сложности не указан или некорректен ({level}), фильтрация не применяется.")

        tasks = tasks.select_related('topic', 'subtopic').prefetch_related(
            'translations'
        )
        
        # Подсчитываем количество задач с попытками для текущей подтемы
        completed_tasks_count = 0
        if telegram_id:
            completed_tasks_count = MiniAppTaskStatistics.objects.filter(
                mini_app_user__telegram_id=telegram_id,
                task__subtopic=subtopic
            ).values('task').distinct().count()
        
        # Подготавливаем данные задач для мини-приложения
        tasks_data = []
        for task in tasks:
            translation = task.translations.filter(language=language).first()
            if translation:
                # Подготавливаем варианты ответов
                answers = [translation.correct_answer]
                if translation.answers:
                    # Добавляем неправильные ответы из JSON поля
                    import json
                    wrong_answers = translation.answers
                    if isinstance(wrong_answers, str):
                        # Если answers это JSON строка, парсим её
                        try:
                            wrong_answers = json.loads(wrong_answers)
                        except json.JSONDecodeError:
                            wrong_answers = []
                    if isinstance(wrong_answers, list):
                        # Добавляем только неправильные ответы (исключаем правильный)
                        for answer in wrong_answers:
                            if answer != translation.correct_answer:
                                answers.append(answer)
                    elif isinstance(wrong_answers, dict):
                        # Если answers это словарь, извлекаем значения
                        for answer in wrong_answers.values():
                            if answer != translation.correct_answer:
                                answers.append(answer)
                
                # Перемешиваем варианты ответов
                import random
                random.shuffle(answers)
                
                # Добавляем опцию "Не знаю, но хочу узнать"
                dont_know_options = {
                    'ru': 'Я не знаю, но хочу узнать',
                    'en': 'I don\'t know, but I want to learn'
                }
                dont_know_option = dont_know_options.get(language, dont_know_options['en'])
                answers.append(dont_know_option)
                
                # Отмечаем как решенную для мини-аппа при ЛЮБОЙ попытке пользователя
                # (одноразовая попытка — повторные клики должны быть заблокированы)
                is_solved = False
                if telegram_id:
                    is_solved = MiniAppTaskStatistics.objects.filter(
                        mini_app_user__telegram_id=telegram_id,
                        task=task
                    ).exists()
                
                task_data = {
                    'id': task.id,
                    'topic_id': task.topic.id,
                    'subtopic_id': task.subtopic.id,
                    'difficulty': task.difficulty,
                    'image_url': task.image_url,
                    'question': translation.question,
                    'answers': answers,
                    'correct_answer': translation.correct_answer,
                    'explanation': translation.explanation,
                    'is_solved': is_solved
                }
                tasks_data.append(task_data)
        
        data = {
            'id': subtopic.id,
            'name': subtopic.name,
            'description': f'Подтема: {subtopic.name}',
            'topic': subtopic.topic_id,
            'questions_count': len(tasks_data),
            'results': tasks_data,  # Добавляем задачи в поле results
            'subtopic_name': subtopic.name,
            'topic_name': subtopic.topic.name,
            'completed_tasks_count': completed_tasks_count # Добавляем для подтемы
        }
        return Response(data)
    except Subtopic.DoesNotExist:
        return Response({'error': 'Subtopic not found'}, status=404)


