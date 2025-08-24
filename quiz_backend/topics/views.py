from django.shortcuts import render
from rest_framework import generics, permissions
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import Topic, Subtopic
from .serializers import TopicSerializer, SubtopicSerializer, TopicMiniAppSerializer, SubtopicWithTasksSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

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
        
        # Временно показываем все подтемы, даже без задач
        # TODO: Восстановить фильтрацию когда будут добавлены задачи
        return queryset

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
    
    data = []
    for topic in topics:
        # Подсчитываем количество задач с переводами на указанном языке
        tasks_count = topic.tasks.filter(
            published=True,
            translations__language=language
        ).distinct().count()
        
        data.append({
            'id': topic.id,
            'name': topic.name,
            'description': topic.description or f'Изучение {topic.name}',
            'icon': topic.icon,
            'difficulty': 'Средний',  # Временно статично
            'questions_count': tasks_count,
            'image_url': f'https://picsum.photos/400/400?{topic.id}',
        })
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
        
        # Подсчитываем количество задач с переводами на указанном языке
        tasks_count = topic.tasks.filter(
            published=True,
            translations__language=language
        ).distinct().count()
        
        data = {
            'id': topic.id,
            'name': topic.name,
            'description': topic.description or f'Изучение {topic.name}',
            'icon': topic.icon,
            'difficulty': 'Средний',  # Временно статично
            'questions_count': tasks_count,
            'image_url': f'https://picsum.photos/400/400?{topic.id}',
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
    Включает задачи для подтемы
    """
    try:
        subtopic = Subtopic.objects.get(id=subtopic_id)
        
        # Получаем язык из query параметров
        language = request.GET.get('language', 'en')
        
        # Получаем задачи с переводами на нужном языке
        from tasks.models import Task, TaskTranslation
        
        tasks = Task.objects.filter(
            subtopic=subtopic,
            published=True,
            translations__language=language
        ).select_related('topic', 'subtopic').prefetch_related(
            'translations'
        )
        
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
                    'is_solved': False  # TODO: Добавить проверку решения пользователем
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
            'topic_name': subtopic.topic.name
        }
        return Response(data)
    except Subtopic.DoesNotExist:
        return Response({'error': 'Subtopic not found'}, status=404)


