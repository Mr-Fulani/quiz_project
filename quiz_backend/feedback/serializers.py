from rest_framework import serializers
from .models import FeedbackMessage

class FeedbackSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели FeedbackMessage.
    """
    short_message = serializers.CharField(read_only=True)

    class Meta:
        model = FeedbackMessage
        fields = [
            'id', 
            'user_id', 
            'username', 
            'message', 
            'short_message',
            'created_at', 
            'is_processed'
        ]
        read_only_fields = ['id', 'created_at', 'is_processed']

    def create(self, validated_data):
        """
        Создание нового сообщения обратной связи.
        Автоматически заполняет user_id из текущего пользователя.
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['user_id'] = request.user.id
            # Если у пользователя есть username, используем его
            if hasattr(request.user, 'username'):
                validated_data['username'] = request.user.username
        return super().create(validated_data) 