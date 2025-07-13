from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import SocialAccount, SocialLoginSession, SocialAuthSettings

User = get_user_model()


class SocialAccountSerializer(serializers.ModelSerializer):
    """
    Сериализатор для социальных аккаунтов.
    """
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    display_name = serializers.CharField(read_only=True)
    is_token_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = SocialAccount
        fields = [
            'id', 'provider', 'provider_display', 'provider_user_id', 'username',
            'email', 'first_name', 'last_name', 'avatar_url', 'is_active',
            'created_at', 'updated_at', 'last_login_at', 'display_name',
            'is_token_expired'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_login_at']


class TelegramAuthSerializer(serializers.Serializer):
    """
    Сериализатор для авторизации через Telegram.
    
    Обрабатывает данные от Telegram Login Widget.
    """
    id = serializers.IntegerField(help_text='Telegram ID пользователя')
    first_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    username = serializers.CharField(max_length=255, required=False, allow_blank=True)
    photo_url = serializers.URLField(required=False, allow_blank=True)
    auth_date = serializers.IntegerField(help_text='Unix timestamp авторизации')
    hash = serializers.CharField(help_text='Хеш для проверки подлинности')

    def validate(self, data):
        """
        Валидирует данные от Telegram Login Widget.
        
        Проверяет подпись запроса для безопасности.
        """
        # Здесь будет логика проверки подписи Telegram
        # Пока оставляем базовую валидацию
        if not data.get('id'):
            raise serializers.ValidationError("Telegram ID обязателен")
        
        if not data.get('auth_date'):
            raise serializers.ValidationError("Дата авторизации обязательна")
        
        if not data.get('hash'):
            raise serializers.ValidationError("Хеш обязателен")
        
        return data


class SocialLoginSessionSerializer(serializers.ModelSerializer):
    """
    Сериализатор для сессий социальной аутентификации.
    """
    social_account_info = serializers.CharField(source='social_account.display_name', read_only=True)

    class Meta:
        model = SocialLoginSession
        fields = [
            'id', 'session_id', 'social_account', 'social_account_info',
            'ip_address', 'user_agent', 'is_successful', 'error_message',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SocialAuthSettingsSerializer(serializers.ModelSerializer):
    """
    Сериализатор для настроек социальной аутентификации.
    """
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)

    class Meta:
        model = SocialAuthSettings
        fields = [
            'id', 'provider', 'provider_display', 'client_id', 'is_enabled',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'client_secret': {'write_only': True}
        }


class UserSocialAccountsSerializer(serializers.ModelSerializer):
    """
    Сериализатор для отображения социальных аккаунтов пользователя.
    """
    social_accounts = SocialAccountSerializer(many=True, read_only=True)
    has_telegram = serializers.SerializerMethodField()
    has_github = serializers.SerializerMethodField()
    has_google = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'social_accounts', 'has_telegram',
            'has_github', 'has_google'
        ]

    def get_has_telegram(self, obj):
        return obj.social_accounts.filter(provider='telegram', is_active=True).exists()

    def get_has_github(self, obj):
        return obj.social_accounts.filter(provider='github', is_active=True).exists()

    def get_has_google(self, obj):
        return obj.social_accounts.filter(provider='google', is_active=True).exists()


class SocialAuthResponseSerializer(serializers.Serializer):
    """
    Сериализатор для ответа при успешной социальной аутентификации.
    """
    success = serializers.BooleanField()
    user = UserSocialAccountsSerializer()
    social_account = SocialAccountSerializer()
    message = serializers.CharField(required=False)
    redirect_url = serializers.CharField(required=False)
