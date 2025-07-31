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


