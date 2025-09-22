from urllib.parse import unquote
import logging
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db.models import Count, Q
from .models import CustomUser, UserChannelSubscription, TelegramAdmin, DjangoAdmin, MiniAppUser, TelegramUser

logger = logging.getLogger(__name__)

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
        # obj is CustomUser instance
        # Сначала пытаемся получить аватар из MiniAppUser, если он связан
        mini_app_profile = getattr(obj, 'mini_app_profile', None)
        avatar_field = None
        if mini_app_profile and mini_app_profile.avatar:
            avatar_field = mini_app_profile.avatar
        elif obj.avatar:
            avatar_field = obj.avatar

        if avatar_field and hasattr(avatar_field, 'url'):
            avatar_url = avatar_field.url
            # Декодируем URL на случай, если он закодирован
            decoded_url = unquote(avatar_url)
            
            # Проверяем, является ли декодированный URL абсолютным
            if decoded_url.startswith('http://') or decoded_url.startswith('https://'):
                return decoded_url
            
            # Если это относительный путь, строим полный URL
            request = self.context.get('request')
            if request:
                # Приоритет: X-Forwarded-Host > Host заголовок > fallback
                forwarded_host = request.headers.get('X-Forwarded-Host')
                host_header = request.headers.get('Host')
                
                if forwarded_host:
                    host = forwarded_host
                elif host_header and not host_header.startswith('localhost'):
                    host = host_header
                else:
                    # Fallback для продакшена
                    host = 'mini.quiz-code.com'
                
                scheme = request.headers.get('X-Forwarded-Proto', 'https')
                return f"{scheme}://{host}{avatar_url}"
            return avatar_url
        return None
    
    def get_social_links(self, obj):
        """Возвращает социальные ссылки пользователя"""
        social_links = []
        
        if obj.website and obj.website.strip():
            social_links.append({
                "name": "Веб-сайт",
                "url": obj.website,
                "icon": "🌐"
            })
        
        if obj.telegram and obj.telegram.strip():
            # Убираем @ если он есть в начале
            telegram_username = obj.telegram.lstrip('@')
            social_links.append({
                "name": "Telegram",
                "url": f"https://t.me/{telegram_username}" if not obj.telegram.startswith('http') else obj.telegram,
                "icon": "📱"
            })
        
        if obj.github and obj.github.strip():
            social_links.append({
                "name": "GitHub",
                "url": obj.github,
                "icon": "💻"
            })
        
        if obj.linkedin and obj.linkedin.strip():
            social_links.append({
                "name": "LinkedIn",
                "url": obj.linkedin,
                "icon": "💼"
            })
        
        if obj.instagram and obj.instagram.strip():
            social_links.append({
                "name": "Instagram",
                "url": obj.instagram,
                "icon": "📷"
            })
        
        if obj.facebook and obj.facebook.strip():
            social_links.append({
                "name": "Facebook",
                "url": obj.facebook,
                "icon": "👥"
            })
        
        if obj.youtube and obj.youtube.strip():
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


class MiniAppUserSerializer(serializers.ModelSerializer):
    """
    Сериализатор для пользователей Mini App.
    
    Предоставляет полную информацию о пользователе Mini App,
    включая связи с другими типами пользователей и статус админа.
    """
    full_name = serializers.CharField(read_only=True)
    is_admin = serializers.BooleanField(read_only=True)
    admin_type = serializers.CharField(read_only=True)
    avatar = serializers.SerializerMethodField() # Добавляем это поле
    social_links = serializers.SerializerMethodField() # Добавляем это поле
    
    # Связи с другими типами пользователей
    telegram_user_id = serializers.IntegerField(source='telegram_user.telegram_id', read_only=True)
    telegram_admin_id = serializers.IntegerField(source='telegram_admin.telegram_id', read_only=True)
    django_admin_username = serializers.CharField(source='django_admin.username', read_only=True)
    
    class Meta:
        model = MiniAppUser
        fields = (
            'id', 'telegram_id', 'username', 'first_name', 'last_name',
            'full_name', 'language', 'avatar', 'created_at', 'last_seen',
            'is_admin', 'admin_type',
            'telegram_user_id', 'telegram_admin_id', 'django_admin_username',
            'social_links' # Добавляем social_links
        )
        read_only_fields = ('id', 'created_at', 'last_seen', 'full_name', 'is_admin', 'admin_type', 'avatar', 'social_links')
    
    def get_avatar(self, obj):
        """
        Возвращает абсолютный URL к аватару пользователя.
        Приоритет: 1) загруженный avatar, 2) telegram_photo_url, 3) None
        """
        # Сначала проверяем загруженный аватар
        if obj.avatar and hasattr(obj.avatar, 'url'):
            avatar_url = obj.avatar.url
            # Декодируем URL
            decoded_url = unquote(avatar_url)
            
            if decoded_url.startswith('http://') or decoded_url.startswith('https://'):
                return decoded_url

            request = self.context.get('request')
            if request:
                # Приоритет: X-Forwarded-Host > Host заголовок > fallback
                forwarded_host = request.headers.get('X-Forwarded-Host')
                host_header = request.headers.get('Host')
                
                if forwarded_host:
                    host = forwarded_host
                elif host_header and not host_header.startswith('localhost'):
                    host = host_header
                else:
                    # Fallback для продакшена
                    host = 'mini.quiz-code.com'
                
                scheme = request.headers.get('X-Forwarded-Proto', 'https')
                return f"{scheme}://{host}{avatar_url}"
            return avatar_url
        
        # Если загруженного аватара нет, используем URL из Telegram
        if obj.telegram_photo_url:
            return obj.telegram_photo_url
            
        return None
    
    def get_social_links(self, obj):
        """Возвращает социальные ссылки пользователя Mini App."""
        # Используем метод из модели MiniAppUser
        return obj.get_social_links()


class MiniAppUserCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания пользователя Mini App.
    
    Используется при первом входе пользователя в Mini App.
    Автоматически связывает с существующими пользователями.
    """
    photo_url = serializers.URLField(required=False, write_only=True)
    language_code = serializers.CharField(source='language', required=False)
    
    class Meta:
        model = MiniAppUser
        fields = ('telegram_id', 'username', 'first_name', 'last_name', 'language', 'language_code', 'avatar', 'photo_url', 'telegram_photo_url')
        extra_kwargs = {
            'telegram_photo_url': {'write_only': True}
        }
    
    def create(self, validated_data):
        """
        Создает пользователя Mini App и автоматически связывает с существующими пользователями.
        """
        # Обрабатываем photo_url из Telegram
        photo_url = validated_data.pop('photo_url', None)
        if photo_url:
            validated_data['telegram_photo_url'] = photo_url
            
        # Создаем пользователя
        mini_app_user = MiniAppUser.objects.create(**validated_data)
        
        # Автоматически связываем с существующими пользователями
        try:
            # Связываем с TelegramUser
            telegram_user = TelegramUser.objects.filter(
                telegram_id=mini_app_user.telegram_id
            ).first()
            if telegram_user:
                mini_app_user.link_to_telegram_user(telegram_user)
            
            # Связываем с TelegramAdmin
            telegram_admin = TelegramAdmin.objects.filter(
                telegram_id=mini_app_user.telegram_id
            ).first()
            if telegram_admin:
                mini_app_user.link_to_telegram_admin(telegram_admin)
            
            # Связываем с DjangoAdmin (по username)
            if mini_app_user.username:
                django_admin = DjangoAdmin.objects.filter(
                    username=mini_app_user.username
                ).first()
                if django_admin:
                    mini_app_user.link_to_django_admin(django_admin)
            
            # Связываем с CustomUser (основным пользователем сайта) по telegram_id
            custom_user = CustomUser.objects.filter(
                telegram_id=mini_app_user.telegram_id
            ).first()
            if custom_user:
                mini_app_user.linked_custom_user = custom_user
                mini_app_user.save(update_fields=['linked_custom_user'])
            elif mini_app_user.username: # Если CustomUser не найден по telegram_id, пробуем по username
                 custom_user = CustomUser.objects.filter(
                    username=mini_app_user.username
                ).first()
                 if custom_user:
                    mini_app_user.linked_custom_user = custom_user
                    mini_app_user.save(update_fields=['linked_custom_user'])
                    
        except Exception as e:
            # Логируем ошибку, но не прерываем создание пользователя
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Ошибка при автоматическом связывании MiniAppUser {mini_app_user.telegram_id}: {e}")
        
        return mini_app_user


class MiniAppUserUpdateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для обновления пользователя Mini App.
    
    Позволяет обновлять основные данные пользователя, включая социальные сети.
    """
    photo_url = serializers.URLField(required=False, write_only=True)
    social_links = serializers.SerializerMethodField()
    
    class Meta:
        model = MiniAppUser
        fields = (
            'username', 'first_name', 'last_name', 'language', 'avatar', 'telegram_photo_url', 'photo_url',
            'website', 'telegram', 'github', 'linkedin', 'instagram', 'facebook', 'youtube', 'social_links'
        )
        extra_kwargs = {
            'telegram_photo_url': {'write_only': True}
        }
    
    def update(self, instance, validated_data):
        """
        Обновляет данные пользователя и время последнего визита.
        """
        # Обрабатываем photo_url из Telegram
        photo_url = validated_data.pop('photo_url', None)
        if photo_url:
            validated_data['telegram_photo_url'] = photo_url
            # Если приходит новый URL от Telegram, очищаем загруженный avatar
            validated_data['avatar'] = None
            
        # Обновляем данные
        for attr, value in validated_data.items():
            # Для социальных сетей: очищаем пустые строки и пробелы
            if attr in ['website', 'telegram', 'github', 'linkedin', 'instagram', 'facebook', 'youtube']:
                if value is not None:
                    cleaned_value = value.strip() if value else ''
                    setattr(instance, attr, cleaned_value)
            else:
                # Для остальных полей обновляем как обычно
                setattr(instance, attr, value)
        
        # Сохраняем изменения
        instance.save()
        
        # Обновляем время последнего визита
        instance.update_last_seen()
        
        return instance 
    
    def get_social_links(self, obj):
        """Возвращает социальные ссылки пользователя Mini App."""
        # Используем метод из модели MiniAppUser
        return obj.get_social_links()


class MiniAppTopUserSerializer(serializers.ModelSerializer):
    """
    Сериализатор для топ-пользователей Mini App, включающий рейтинг и базовые данные.
    """
    avatar_url = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    quizzes_completed = serializers.SerializerMethodField()
    average_score = serializers.SerializerMethodField() # Это success_rate
    is_online = serializers.SerializerMethodField()

    class Meta:
        model = MiniAppUser
        fields = (
            'id', 'telegram_id', 'username', 'first_name', 'last_name',
            'avatar_url', 'rating', 'quizzes_completed', 'average_score', 'is_online'
        )

    def get_avatar_url(self, obj):
        """
        Возвращает URL аватара пользователя Mini App.
        Приоритет: 1) загруженный avatar, 2) telegram_photo_url, 3) None
        """
        # Сначала проверяем загруженный аватар
        if obj.avatar and hasattr(obj.avatar, 'url'):
            avatar_url = obj.avatar.url
            # Декодируем URL
            decoded_url = unquote(avatar_url)
            
            logger.info(f"[DEBUG AVATAR] raw avatar_url: {avatar_url}")
            logger.info(f"[DEBUG AVATAR] decoded_url: {decoded_url}")

            if decoded_url.startswith('http://') or decoded_url.startswith('https://'):
                logger.info(f"[DEBUG AVATAR] returning decoded: {decoded_url}")
                return decoded_url

            request = self.context.get('request')
            if request:
                logger.info(f"[DEBUG AVATAR] all request headers: {dict(request.headers)}")
                # Приоритет: X-Forwarded-Host > Host заголовок > fallback
                forwarded_host = request.headers.get('X-Forwarded-Host')
                host_header = request.headers.get('Host')
                
                if forwarded_host:
                    host = forwarded_host
                    logger.info(f"[DEBUG AVATAR] Using forwarded_host: {forwarded_host}")
                elif host_header and not host_header.startswith('localhost'):
                    host = host_header
                    logger.info(f"[DEBUG AVATAR] Using host_header: {host_header}")
                else:
                    # Fallback для продакшена
                    host = 'mini.quiz-code.com'
                    logger.info(f"[DEBUG AVATAR] Using fallback host: {host}")
                
                scheme = request.headers.get('X-Forwarded-Proto', 'https')
                final_url = f"{scheme}://{host}{avatar_url}"
                logger.info(f"[DEBUG AVATAR] headers: forwarded_host={forwarded_host}, host_header={host_header}, final_host={host}, scheme={scheme}")
                logger.info(f"[DEBUG AVATAR] final_url: {final_url}")
                return final_url
            return avatar_url
        
        # Если загруженного аватара нет, используем URL из Telegram
        if obj.telegram_photo_url:
            logger.info(f"[DEBUG AVATAR] Using telegram_photo_url: {obj.telegram_photo_url}")
            return obj.telegram_photo_url
            
        return None
    
    def get_rating(self, obj):
        """
        Возвращает рейтинг пользователя Mini App.
        """
        return obj.calculate_rating()

    def get_quizzes_completed(self, obj):
        """
        Возвращает количество завершенных квизов для Mini App пользователя.
        """
        return obj.quizzes_completed

    def get_average_score(self, obj):
        """
        Возвращает средний балл (процент успешности) для Mini App пользователя.
        """
        return obj.average_score

    def get_is_online(self, obj):
        """
        Проверяет, онлайн ли пользователь Mini App.
        """
        return obj.is_online 