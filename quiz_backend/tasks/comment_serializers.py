"""
Сериализаторы для системы комментариев к задачам.
Поддерживают древовидную структуру комментариев с изображениями.
"""
from rest_framework import serializers
from .models import TaskComment, TaskCommentImage, TaskCommentReport


class TaskCommentImageSerializer(serializers.ModelSerializer):
    """
    Сериализатор для изображений комментариев.
    """
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskCommentImage
        fields = ['id', 'image', 'image_url', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']
    
    def get_image_url(self, obj):
        """Возвращает URL изображения (относительный для корректной работы через nginx proxy)"""
        if obj.image and hasattr(obj.image, 'url'):
            return obj.image.url
        return None


class RecursiveCommentSerializer(serializers.Serializer):
    """
    Рекурсивный сериализатор для вложенных комментариев.
    Используется для отображения древовидной структуры.
    """
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class TaskCommentSerializer(serializers.ModelSerializer):
    """
    Основной сериализатор для комментариев к задачам.
    Поддерживает рекурсивную структуру для отображения ответов.
    """
    images = TaskCommentImageSerializer(many=True, read_only=True)
    replies = RecursiveCommentSerializer(many=True, read_only=True)
    replies_count = serializers.SerializerMethodField()
    depth = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    created_at_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskComment
        fields = [
            'id',
            'task_translation',
            'author_telegram_id',
            'author_username',
            'text',
            'parent_comment',
            'created_at',
            'created_at_formatted',
            'updated_at',
            'is_deleted',
            'reports_count',
            'images',
            'replies',
            'replies_count',
            'depth',
            'can_delete'
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'is_deleted',
            'reports_count'
        ]
    
    def get_replies_count(self, obj):
        """Возвращает количество ответов (не удалённых)"""
        return obj.get_replies_count()
    
    def get_depth(self, obj):
        """Возвращает глубину вложенности комментария"""
        return obj.get_depth()
    
    def get_can_delete(self, obj):
        """Проверяет, может ли текущий пользователь удалить комментарий"""
        request = self.context.get('request')
        if not request:
            return False
        
        # Получаем telegram_id из запроса (из query params или из validated data)
        telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            # Пытаемся получить из данных запроса
            telegram_id = getattr(request, 'telegram_id', None)
        
        if telegram_id:
            return obj.author_telegram_id == int(telegram_id)
        return False
    
    def get_created_at_formatted(self, obj):
        """Возвращает отформатированное время создания"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff < timedelta(minutes=1):
            return "только что"
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} мин. назад"
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} ч. назад"
        elif diff < timedelta(days=30):
            days = diff.days
            return f"{days} дн. назад"
        else:
            return obj.created_at.strftime('%d.%m.%Y')


class TaskCommentListSerializer(TaskCommentSerializer):
    """
    Сериализатор для списка комментариев.
    Загружает только корневые комментарии (без parent_comment).
    """
    def get_fields(self):
        fields = super().get_fields()
        # Для списка показываем только первый уровень ответов
        fields['replies'] = TaskCommentSerializer(many=True, read_only=True)
        return fields


class TaskCommentCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания комментариев.
    Изображения обрабатываются отдельно в view.
    """
    
    class Meta:
        model = TaskComment
        fields = [
            'task_translation',
            'author_telegram_id',
            'author_username',
            'text',
            'parent_comment'
        ]
    
    def validate_text(self, value):
        """Валидация текста комментария"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError(
                "Комментарий должен содержать минимум 3 символа"
            )
        if len(value) > 2000:
            raise serializers.ValidationError(
                "Комментарий не может быть длиннее 2000 символов"
            )
        return value.strip()
    
    def validate_parent_comment(self, value):
        """Валидация родительского комментария"""
        if value:
            # Проверяем глубину вложенности (максимум 3 уровня)
            if value.get_depth() >= 2:
                raise serializers.ValidationError(
                    "Достигнут максимальный уровень вложенности комментариев"
                )
            
            # Проверяем, что родительский комментарий не удалён
            if value.is_deleted:
                raise serializers.ValidationError(
                    "Нельзя ответить на удалённый комментарий"
                )
            
            # Проверяем, что комментарий относится к той же задаче
            task_translation = self.initial_data.get('task_translation')
            if task_translation and value.task_translation_id != int(task_translation):
                raise serializers.ValidationError(
                    "Родительский комментарий должен относиться к той же задаче"
                )
        
        return value


class TaskCommentUpdateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для обновления комментариев.
    Позволяет редактировать только текст.
    """
    class Meta:
        model = TaskComment
        fields = ['text']
    
    def validate_text(self, value):
        """Валидация текста комментария"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError(
                "Комментарий должен содержать минимум 3 символа"
            )
        if len(value) > 2000:
            raise serializers.ValidationError(
                "Комментарий не может быть длиннее 2000 символов"
            )
        return value.strip()


class TaskCommentReportSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания жалоб на комментарии.
    """
    class Meta:
        model = TaskCommentReport
        fields = [
            'id',
            'comment',
            'reporter_telegram_id',
            'reason',
            'description',
            'created_at',
            'is_reviewed'
        ]
        read_only_fields = ['id', 'created_at', 'is_reviewed']
    
    def validate_description(self, value):
        """Валидация описания жалобы"""
        if value and len(value) > 500:
            raise serializers.ValidationError(
                "Описание не может быть длиннее 500 символов"
            )
        return value
    
    def validate(self, data):
        """Проверка на дубликаты жалоб"""
        comment = data.get('comment')
        reporter_telegram_id = data.get('reporter_telegram_id')
        
        # Проверяем, не подавал ли пользователь уже жалобу на этот комментарий
        if TaskCommentReport.objects.filter(
            comment=comment,
            reporter_telegram_id=reporter_telegram_id
        ).exists():
            raise serializers.ValidationError(
                "Вы уже подали жалобу на этот комментарий"
            )
        
        return data

