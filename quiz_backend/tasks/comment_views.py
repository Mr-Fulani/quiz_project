"""
Views для системы комментариев к задачам.
Поддерживает CRUD операции, древовидную структуру и модерацию.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.utils.translation import activate
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import TaskComment, TaskCommentReport, TaskTranslation, TaskCommentImage
from .comment_serializers import (
    TaskCommentSerializer,
    TaskCommentListSerializer,
    TaskCommentCreateSerializer,
    TaskCommentUpdateSerializer,
    TaskCommentReportSerializer
)

logger = logging.getLogger(__name__)


class CommentPagination(PageNumberPagination):
    """
    Пагинация для комментариев.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


class TaskCommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet для работы с комментариями к задачам.
    
    Поддерживает:
    - Получение списка комментариев с древовидной структурой
    - Создание комментариев и ответов
    - Редактирование собственных комментариев
    - Мягкое удаление комментариев
    - Отправку жалоб на комментарии
    """
    queryset = TaskComment.objects.all()
    pagination_class = CommentPagination
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def get_serializer_class(self):
        """Выбор сериализатора в зависимости от действия"""
        if self.action == 'list':
            return TaskCommentListSerializer
        elif self.action == 'create':
            return TaskCommentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TaskCommentUpdateSerializer
        elif self.action == 'report':
            return TaskCommentReportSerializer
        return TaskCommentSerializer
    
    def get_queryset(self):
        """
        Фильтрация комментариев по translation_id.
        Возвращает только корневые комментарии (без parent_comment).
        """
        queryset = TaskComment.objects.filter(is_deleted=False)
        
        # Фильтрация по translation_id
        translation_id = self.kwargs.get('translation_id')
        if translation_id:
            queryset = queryset.filter(task_translation_id=translation_id)
        
        # Для списка показываем только корневые комментарии
        if self.action == 'list':
            queryset = queryset.filter(parent_comment__isnull=True)
        
        # Сортировка
        ordering = self.request.query_params.get('ordering', '-created_at')
        if ordering in ['created_at', '-created_at', 'reports_count', '-reports_count']:
            queryset = queryset.order_by(ordering)
        
        return queryset.select_related(
            'task_translation',
            'parent_comment'
        ).prefetch_related(
            'images',
            'replies',
            'replies__images'
        )
    
    @swagger_auto_schema(
        operation_description="Получить список комментариев для перевода задачи",
        manual_parameters=[
            openapi.Parameter(
                'translation_id',
                openapi.IN_PATH,
                description="ID перевода задачи",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'ordering',
                openapi.IN_QUERY,
                description="Сортировка (created_at, -created_at, reports_count, -reports_count)",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'language',
                openapi.IN_QUERY,
                description="Язык пользователя (en, ru)",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        """
        Получение списка комментариев для конкретного перевода задачи.
        Возвращает только корневые комментарии с вложенными ответами.
        """
        # Активируем язык на основе параметра запроса
        language = request.query_params.get('language')
        if language and language in ['en', 'ru']:
            activate(language)
        
        return super().list(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Создать новый комментарий или ответ",
        request_body=TaskCommentCreateSerializer,
        manual_parameters=[
            openapi.Parameter(
                'translation_id',
                openapi.IN_PATH,
                description="ID перевода задачи",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ]
    )
    def create(self, request, *args, **kwargs):
        """
        Создание нового комментария или ответа на существующий комментарий.
        
        Поддерживает загрузку до 3 изображений.
        """
        # Логирование для отладки
        logger.info(f"Create comment request data: {request.data}")
        logger.info(f"Create comment request FILES: {request.FILES}")
        logger.info(f"Content-Type: {request.content_type}")
        
        # Проверяем, что translation_id существует
        translation_id = kwargs.get('translation_id')
        get_object_or_404(TaskTranslation, pk=translation_id)
        
        # Добавляем translation_id в данные
        data = request.data.copy()
        data['task_translation'] = translation_id
        
        # Обрабатываем изображения отдельно
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
        
        # Удаляем images из data для сериализатора
        if 'images' in data:
            del data['images']
        
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            logger.error(f"Serializer validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_create(serializer)
        comment = serializer.instance
        
        # Теперь добавляем изображения к созданному комментарию
        if images:
            for image in images:
                TaskCommentImage.objects.create(
                    comment=comment,
                    image=image
                )
        response_serializer = TaskCommentSerializer(
            comment,
            context={'request': request}
        )
        
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @swagger_auto_schema(
        operation_description="Обновить текст комментария",
        request_body=TaskCommentUpdateSerializer,
        manual_parameters=[
            openapi.Parameter(
                'telegram_id',
                openapi.IN_QUERY,
                description="Telegram ID пользователя для проверки прав",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ]
    )
    def update(self, request, *args, **kwargs):
        """
        Обновление текста комментария.
        Пользователь может редактировать только свои комментарии.
        """
        comment = self.get_object()
        telegram_id = request.query_params.get('telegram_id')
        
        if not telegram_id:
            return Response(
                {'error': 'telegram_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверка прав доступа
        if comment.author_telegram_id != int(telegram_id):
            return Response(
                {'error': 'Вы можете редактировать только свои комментарии'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """PATCH запрос для частичного обновления"""
        return self.update(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Удалить комментарий (мягкое удаление)",
        manual_parameters=[
            openapi.Parameter(
                'telegram_id',
                openapi.IN_QUERY,
                description="Telegram ID пользователя для проверки прав",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ]
    )
    def destroy(self, request, *args, **kwargs):
        """
        Мягкое удаление комментария.
        Пользователь может удалять только свои комментарии.
        """
        comment = self.get_object()
        telegram_id = request.query_params.get('telegram_id')
        
        if not telegram_id:
            return Response(
                {'error': 'telegram_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверка прав доступа
        if comment.author_telegram_id != int(telegram_id):
            return Response(
                {'error': 'Вы можете удалять только свои комментарии'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Мягкое удаление
        comment.is_deleted = True
        comment.text = "[Комментарий удалён]"
        comment.save(update_fields=['is_deleted', 'text'])
        
        # Удаляем изображения
        comment.images.all().delete()
        
        logger.info(
            f"Комментарий {comment.id} удалён пользователем {telegram_id}"
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Отправить жалобу на комментарий",
        request_body=TaskCommentReportSerializer,
        responses={
            201: TaskCommentReportSerializer,
            400: "Неверные данные или жалоба уже существует"
        }
    )
    @action(detail=True, methods=['post'])
    def report(self, request, pk=None, translation_id=None):
        """
        Отправка жалобы на комментарий.
        
        Один пользователь может подать только одну жалобу на комментарий.
        """
        comment = self.get_object()
        
        # Проверяем, что комментарий не удалён
        if comment.is_deleted:
            return Response(
                {'error': 'Нельзя пожаловаться на удалённый комментарий'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Добавляем comment в данные
        data = request.data.copy()
        data['comment'] = comment.id
        
        serializer = TaskCommentReportSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        logger.info(
            f"Жалоба на комментарий {comment.id} от пользователя "
            f"{data.get('reporter_telegram_id')}: {data.get('reason')}"
        )
        
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @swagger_auto_schema(
        method='get',
        operation_description="Получить количество комментариев для перевода задачи",
        manual_parameters=[
            openapi.Parameter(
                'translation_id',
                openapi.IN_PATH,
                description="ID перевода задачи",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ]
    )
    @action(detail=False, methods=['get'], url_path='count')
    def comments_count(self, request, translation_id=None):
        """
        Получение количества комментариев для перевода задачи.
        """
        count = TaskComment.objects.filter(
            task_translation_id=translation_id,
            is_deleted=False
        ).count()
        
        return Response({'count': count})

