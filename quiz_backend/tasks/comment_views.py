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
from django.utils.translation import activate, gettext as _
from django.db import IntegrityError
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
        
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
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
        # Активируем язык на основе параметра запроса (как в методе list)
        app_language = request.query_params.get('language')
        logger.info(f"🌐 Language from query_params: {app_language}")
        if not app_language:
            # Пробуем получить язык из данных запроса (если передается в теле)
            app_language = request.data.get('language') if hasattr(request.data, 'get') else None
            logger.info(f"🌐 Language from request.data: {app_language}")
        if not app_language or app_language not in ['en', 'ru']:
            app_language = 'ru'  # Fallback на русский
            logger.info(f"🌐 Language fallback to: {app_language}")
        
        # Активируем язык для перевода
        activate(app_language)
        from django.utils.translation import get_language
        logger.info(f"🌐 Language activated: {app_language}, current language: {get_language()}")
        
        # Логирование для отладки
        logger.info(f"Create comment request data: {request.data}")
        logger.info(f"Create comment request FILES: {request.FILES}")
        logger.info(f"Content-Type: {request.content_type}")
        
        # Проверка бана пользователя
        telegram_id = request.data.get('author_telegram_id')
        if telegram_id:
            try:
                from accounts.models import MiniAppUser
                user = MiniAppUser.objects.get(telegram_id=telegram_id)
                
                # Проверяем, не истёк ли бан
                user.check_ban_expired()
                
                # Если пользователь забанен, запрещаем создание комментария
                if user.is_banned:
                    from django.utils import timezone
                    from django.utils.translation import get_language
                    
                    # Убеждаемся, что язык активирован (активирован в начале метода)
                    current_lang = get_language()
                    if current_lang != app_language:
                        activate(app_language)
                        current_lang = get_language()
                    
                    logger.info(f"🔍 Ban check: app_language={app_language}, current_lang={current_lang}, user.is_banned={user.is_banned}")
                    
                    if user.banned_until:
                        remaining = user.banned_until - timezone.now()
                        hours = int(remaining.total_seconds() // 3600)
                        minutes = int((remaining.total_seconds() % 3600) // 60)
                        
                        # Формируем текст времени с учетом языка приложения
                        if hours > 24:
                            days = hours // 24
                            if app_language == 'en':
                                time_text = f"{days} day" if days == 1 else f"{days} days"
                            else:
                                # Русский: правильное склонение
                                if days == 1:
                                    time_text = f"{days} день"
                                elif 2 <= days <= 4:
                                    time_text = f"{days} дня"
                                else:
                                    time_text = f"{days} дней"
                        elif hours > 0:
                            if app_language == 'en':
                                time_text = f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
                            else:
                                # Русский: правильное склонение
                                hours_text = "час" if hours == 1 else ("часа" if 2 <= hours <= 4 else "часов")
                                minutes_text = "минута" if minutes == 1 else ("минуты" if 2 <= minutes <= 4 else "минут")
                                time_text = f"{hours} {hours_text} {minutes} {minutes_text}"
                        else:
                            if app_language == 'en':
                                time_text = f"{minutes} minute{'s' if minutes != 1 else ''}"
                            else:
                                # Русский: правильное склонение
                                if minutes == 1:
                                    time_text = f"{minutes} минута"
                                elif 2 <= minutes <= 4:
                                    time_text = f"{minutes} минуты"
                                else:
                                    time_text = f"{minutes} минут"
                        
                        # Переводим сообщение о бане (gettext автоматически выберет правильный перевод)
                        ban_message = _("You are banned until {date}. Time remaining: {time}.").format(
                            date=user.banned_until.strftime('%d.%m.%Y %H:%M'),
                            time=time_text
                        )
                        logger.info(f"🌐 Ban message (temp): app_lang={app_language}, current_lang={get_language()}, message={ban_message}")
                    else:
                        # Постоянный бан
                        ban_message = _("You are banned permanently.")
                        logger.info(f"🌐 Ban message (permanent): app_lang={app_language}, current_lang={get_language()}, message={ban_message}")
                    
                    if user.ban_reason:
                        reason_text = _("Reason:")
                        ban_message += f"\n\n{reason_text} {user.ban_reason}"
                    
                    logger.info(f"🌐 Final ban message: {ban_message}")
                    
                    return Response(
                        {
                            'error': ban_message,
                            'is_banned': True,
                            'banned_until': user.banned_until.isoformat() if user.banned_until else None,
                            'ban_reason': user.ban_reason
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )
            except MiniAppUser.DoesNotExist:
                # Пользователь не найден - пропускаем проверку
                logger.warning(f"Пользователь с telegram_id={telegram_id} не найден в базе MiniAppUser")
            except Exception as e:
                logger.error(f"Ошибка при проверке бана пользователя: {e}")
        
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
        
        # Отправляем уведомления
        try:
            from accounts.utils_folder.telegram_notifications import create_notification, notify_all_admins
            from accounts.models import MiniAppUser
            from django.db import models as django_models
            
            # Получаем список telegram_id всех админов, чтобы избежать дублирования
            admin_ids = set()
            try:
                admins = MiniAppUser.objects.filter(
                    notifications_enabled=True
                ).filter(
                    django_models.Q(telegram_admin__isnull=False) |
                    django_models.Q(django_admin__isnull=False)
                ).values_list('telegram_id', flat=True)
                admin_ids = set(admins)
                logger.info(f"📋 Найдено {len(admin_ids)} админов: {admin_ids}")
            except Exception as e:
                logger.warning(f"Не удалось получить список админов: {e}")
            
            # Если это ответ на комментарий, уведомляем автора родительского комментария
            # НО только если он не админ (чтобы избежать дублирования)
            if comment.parent_comment:
                parent_author_id = comment.parent_comment.author_telegram_id
                logger.info(f"🔍 Проверка уведомления об ответе: parent_author_id={parent_author_id}, comment_author_id={comment.author_telegram_id}, is_admin={parent_author_id in admin_ids}")
                
                # Не отправляем уведомление самому себе и не админам (они получат как админы)
                if parent_author_id != comment.author_telegram_id:
                    if parent_author_id not in admin_ids:
                        # Пользователь не админ - отправляем персональное уведомление
                        notification_title = "💬 Новый ответ на ваш комментарий"
                        notification_message = f"{comment.author_username} ответил на ваш комментарий:\n\n{comment.text[:200]}"
                        
                        notification = create_notification(
                            recipient_telegram_id=parent_author_id,
                            notification_type='comment_reply',
                            title=notification_title,
                            message=notification_message,
                            related_object_id=comment.id,
                            related_object_type='comment',
                            send_to_telegram=True
                        )
                        if notification:
                            logger.info(f"📤 Отправлено уведомление об ответе на комментарий для {parent_author_id}")
                        else:
                            logger.warning(f"⚠️ Не удалось создать уведомление для {parent_author_id}")
                    else:
                        logger.info(f"ℹ️ Пользователь {parent_author_id} является админом, персональное уведомление не отправляется (получит как админ)")
                else:
                    logger.info(f"ℹ️ Пользователь ответил сам себе, уведомление не отправляется")
            
            # Уведомляем админов о новом комментарии
            from tasks.notification_service import format_comment_notification, send_to_all_admins
            
            # Используем красивый формат из notification_service с правильным request
            notification_message = format_comment_notification(comment, request=request)
            send_to_all_admins(notification_message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомлений: {e}")
        
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
        
        # Проверяем, не подавал ли пользователь уже жалобу (до валидации сериализатора)
        reporter_telegram_id = data.get('reporter_telegram_id')
        if reporter_telegram_id:
            try:
                reporter_telegram_id = int(reporter_telegram_id)
                from .models import TaskCommentReport
                if TaskCommentReport.objects.filter(
                    comment=comment,
                    reporter_telegram_id=reporter_telegram_id
                ).exists():
                    return Response(
                        {'non_field_errors': ['Вы уже подали жалобу на этот комментарий']},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (ValueError, TypeError):
                pass
        
        serializer = TaskCommentReportSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        # Пытаемся сохранить и перехватываем IntegrityError
        try:
            report = serializer.save()
        except IntegrityError as e:
            # Перехватываем ошибки уникальности (unique_together)
            logger.warning(f"Попытка создать дубликат жалобы: {e}")
            return Response(
                {'non_field_errors': ['Вы уже подали жалобу на этот комментарий']},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            # Перехватываем другие ошибки
            logger.error(f"Ошибка сохранения жалобы: {e}")
            return Response(
                {'error': 'Произошла ошибка при отправке жалобы. Попробуйте позже.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        logger.info(
            f"Жалоба на комментарий {comment.id} от пользователя "
            f"{data.get('reporter_telegram_id')}: {data.get('reason')}"
        )
        
        # Уведомляем админов о новой жалобе
        try:
            from accounts.utils_folder.telegram_notifications import notify_all_admins, escape_markdown, escape_username_for_markdown, get_base_url, format_markdown_link
            from accounts.models import MiniAppUser
            from tasks.models import TaskCommentReport
            from django.urls import reverse
            
            # Получаем информацию о задаче
            task = comment.task_translation.task
            topic_name = task.topic.name if task.topic else "Неизвестная тема"
            subtopic_name = task.subtopic.name if task.subtopic else "Без подтемы"
            
            # Получаем username репортера из MiniAppUser
            reporter_username = "Без username"
            try:
                reporter_user = MiniAppUser.objects.filter(telegram_id=report.reporter_telegram_id).first()
                if reporter_user:
                    reporter_username = reporter_user.username or "Без username"
            except Exception:
                pass
            
            # Формируем ссылку на жалобу в админке с динамическим URL
            # Используем request из view напрямую
            base_url = get_base_url(request)
            admin_path = reverse('admin:tasks_taskcommentreport_change', args=[report.id])
            admin_url = f"{base_url}{admin_path}"
            
            reason_display = dict(TaskCommentReport.REASON_CHOICES).get(report.reason, report.reason)

            # Экранируем значения для Markdown
            # Для username используем специальную функцию, которая НЕ экранирует подчеркивания
            escaped_reporter = escape_username_for_markdown(reporter_username or "Без username")
            reporter_display = f"@{escaped_reporter}" if reporter_username else escaped_reporter
            escaped_reason = escape_markdown(str(reason_display))
            escaped_comment_author = escape_username_for_markdown(comment.author_username or "Без username")
            comment_author_display = f"@{escaped_comment_author}" if comment.author_username else escaped_comment_author
            escaped_topic = escape_markdown(topic_name)
            escaped_subtopic = escape_markdown(subtopic_name)
            escaped_comment_text = escape_markdown(comment.text[:150] if comment.text else "")
            escaped_description = escape_markdown(report.description[:100]) if report.description else ""

            admin_title = "🚨 Новая жалоба на комментарий"
            admin_message = (
                f"От: {reporter_display} (ID: {report.reporter_telegram_id})\n"
                f"Причина: {escaped_reason}\n\n"
                f"Комментарий от: {comment_author_display} (ID: {comment.author_telegram_id})\n"
                f"Тема: {escaped_topic} → {escaped_subtopic}\n\n"
                f"Текст комментария: {escaped_comment_text}"
            )
            
            if report.description:
                admin_message += f"\n\nДополнительно: {escaped_description}"
            
            admin_message += f"\n\n👉 {format_markdown_link('Посмотреть в админке', admin_url)}"
            
            notify_all_admins(
                notification_type='report',
                title=admin_title,
                message=admin_message,
                related_object_id=report.id,
                related_object_type='report'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о жалобе: {e}")
        
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

