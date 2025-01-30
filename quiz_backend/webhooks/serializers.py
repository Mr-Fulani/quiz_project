from rest_framework import serializers
from .models import Webhook, DefaultLink, MainFallbackLink

class WebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Webhook
        fields = [
            'id', 
            'url', 
            'service_name', 
            'is_active',
            'created_at', 
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class DefaultLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefaultLink
        fields = [
            'id',
            'language',
            'topic',
            'link'
        ]
        read_only_fields = ['id']

class MainFallbackLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = MainFallbackLink
        fields = [
            'id',
            'language',
            'link'
        ]
        read_only_fields = ['id']

    def validate_language(self, value):
        """
        Приводим язык к нижнему регистру перед валидацией
        """
        return value.lower() if value else value 