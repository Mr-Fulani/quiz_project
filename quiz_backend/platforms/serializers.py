from rest_framework import serializers
from .models import TelegramChannel

class TelegramChannelSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели TelegramChannel.
    """
    class Meta:
        model = TelegramChannel
        fields = (
            'id', 'group_name', 'group_id', 'topic_id',
            'language', 'location_type'
        )
        read_only_fields = ('id',) 