from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import CustomUser, UserChannelSubscription, TelegramAdmin, DjangoAdmin

class UserSerializer(serializers.ModelSerializer):
    """
    Базовый сериализатор пользователя.
    """
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'language', 'subscription_status')
        read_only_fields = ('id', 'subscription_status')

class LoginSerializer(serializers.Serializer):
    """
    Сериализатор для входа в систему.
    """
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if user and user.is_active:
            data['user'] = user
            return data
        raise serializers.ValidationError("Неверные учетные данные.")

class RegisterSerializer(serializers.ModelSerializer):
    """
    Сериализатор для регистрации.
    """
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password', 'password_confirm', 'language')

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Пароли не совпадают.")
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = CustomUser.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user

class ProfileSerializer(serializers.ModelSerializer):
    """
    Расширенный сериализатор для профиля пользователя с социальными сетями.
    """
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'bio', 'location', 'birth_date', 'website',
            'telegram', 'github', 'linkedin', 'instagram', 
            'facebook', 'youtube', 'avatar', 'avatar_url',
            'language', 'subscription_status', 'created_at',
            'theme_preference', 'is_public', 'email_notifications',
            'total_points', 'quizzes_completed', 'average_score'
        )
        read_only_fields = ('id', 'created_at', 'subscription_status')
    
    def get_avatar_url(self, obj):
        """Возвращает URL аватара"""
        return obj.get_avatar_url

class SocialLinksSerializer(serializers.ModelSerializer):
    """
    Отдельный сериализатор только для социальных сетей.
    """
    class Meta:
        model = CustomUser
        fields = (
            'website', 'telegram', 'github', 'linkedin', 
            'instagram', 'facebook', 'youtube'
        )

class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Сериализатор для подписок на каналы.
    """
    channel_name = serializers.CharField(source='channel.group_name', read_only=True)

    class Meta:
        model = UserChannelSubscription
        fields = ('id', 'channel', 'channel_name', 'subscription_status', 'subscribed_at')
        read_only_fields = ('id', 'subscribed_at')

class AdminSerializer(serializers.ModelSerializer):
    """
    Сериализатор для администраторов.
    """
    admin_type = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = (
            'id', 'username', 'email', 'is_active',
            'admin_type', 'created_at'
        )
        read_only_fields = ('id', 'created_at')

    def get_admin_type(self, obj):
        if isinstance(obj, TelegramAdmin):
            return 'telegram'
        elif isinstance(obj, DjangoAdmin):
            return 'django'
        return 'unknown'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if isinstance(instance, TelegramAdmin):
            data['telegram_id'] = instance.telegram_id
        return data 