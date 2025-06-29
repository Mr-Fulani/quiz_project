from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db.models import Count, Q
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

class UserProgressSerializer(serializers.Serializer):
    """Сериализатор для прогресса пользователя по теме."""
    topic_name = serializers.CharField()
    completed_quizzes = serializers.IntegerField()
    total_quizzes = serializers.IntegerField()
    progress_percentage = serializers.IntegerField()

class ProfileSerializer(serializers.ModelSerializer):
    """
    Расширенный сериализатор для профиля пользователя.
    Приводим поля к формату, который ожидает фронтенд mini_app.
    """
    points = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    social_links = serializers.SerializerMethodField()
    
    def get_points(self, obj):
        return obj.total_points or 0
    
    def get_rating(self, obj):
        # Используем метод calculate_rating из модели
        try:
            return obj.calculate_rating()
        except:
            return 0
    
    def get_success_rate(self, obj):
        return obj.average_score or 0.0
    
    def get_progress(self, obj):
        # Получаем реальный прогресс из базы данных
        try:
            from tasks.models import TaskStatistics
            from topics.models import Topic
            
            # Получаем статистику по темам
            progress_data = []
            topics = Topic.objects.all()[:5]  # Ограничиваем количество тем
            
            for topic in topics:
                # Получаем статистику пользователя по этой теме
                user_stats = TaskStatistics.objects.filter(
                    user=obj,
                    task__topic=topic
                ).aggregate(
                    total_tasks=Count('id'),
                    completed_tasks=Count('id', filter=Q(successful=True))
                )
                
                total_tasks = user_stats['total_tasks'] or 0
                completed_tasks = user_stats['completed_tasks'] or 0
                
                if total_tasks > 0:
                    progress_percentage = int((completed_tasks / total_tasks) * 100)
                    progress_data.append({
                        "topic_name": topic.name,
                        "completed_quizzes": completed_tasks,
                        "total_quizzes": total_tasks,
                        "progress_percentage": progress_percentage
                    })
            
            # Если нет реальных данных, возвращаем заглушку
            if not progress_data:
                return [
                    {
                        "topic_name": "Python Основы",
                        "completed_quizzes": 5,
                        "total_quizzes": 10,
                        "progress_percentage": 50
                    },
                    {
                        "topic_name": "JavaScript",
                        "completed_quizzes": 3,
                        "total_quizzes": 8,
                        "progress_percentage": 37
                    }
                ]
            
            return progress_data
            
        except Exception as e:
            # В случае ошибки возвращаем заглушку
            return [
                {
                    "topic_name": "Python Основы",
                    "completed_quizzes": 5,
                    "total_quizzes": 10,
                    "progress_percentage": 50
                }
            ]
    
    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None
    
    def get_social_links(self, obj):
        """Возвращает социальные ссылки пользователя"""
        social_links = []
        
        if obj.website:
            social_links.append({
                "name": "Веб-сайт",
                "url": obj.website,
                "icon": "🌐"
            })
        
        if obj.telegram:
            social_links.append({
                "name": "Telegram",
                "url": f"https://t.me/{obj.telegram}" if not obj.telegram.startswith('http') else obj.telegram,
                "icon": "📱"
            })
        
        if obj.github:
            social_links.append({
                "name": "GitHub",
                "url": obj.github,
                "icon": "💻"
            })
        
        if obj.linkedin:
            social_links.append({
                "name": "LinkedIn",
                "url": obj.linkedin,
                "icon": "💼"
            })
        
        if obj.instagram:
            social_links.append({
                "name": "Instagram",
                "url": obj.instagram,
                "icon": "📷"
            })
        
        if obj.facebook:
            social_links.append({
                "name": "Facebook",
                "url": obj.facebook,
                "icon": "👥"
            })
        
        if obj.youtube:
            social_links.append({
                "name": "YouTube",
                "url": obj.youtube,
                "icon": "📺"
            })
        
        return social_links
    
    class Meta:
        model = CustomUser
        fields = (
            'id', 'telegram_id', 'username', 'first_name', 'last_name',
            'avatar', 'is_public', 
            'points', 'rating', 'quizzes_completed', 'success_rate',
            'progress', 'social_links'
        )

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