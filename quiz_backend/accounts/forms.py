# accounts/forms.py
import re
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm
from django.core.exceptions import ValidationError
from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    """
    Форма для регистрации нового пользователя.
    """
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = UserCreationForm.Meta.fields + ('email',)

    def save(self, commit=True):
        """Сохранение пользователя с email."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class PersonalInfoForm(forms.ModelForm):
    """
    Форма для редактирования личной информации и аватара.
    Поддерживает загрузку только аватара с параметром avatar_only.
    """
    username = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    bio = forms.CharField(widget=forms.Textarea, required=False)
    location = forms.CharField(max_length=100, required=False)
    birth_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False,
        input_formats=['%Y-%m-%d']
    )
    website = forms.URLField(required=False, widget=forms.URLInput(attrs={'placeholder': 'https://example.com'}))
    github = forms.URLField(required=False, widget=forms.URLInput(attrs={'placeholder': 'https://github.com/username'}))
    linkedin = forms.URLField(required=False, widget=forms.URLInput(attrs={'placeholder': 'https://linkedin.com/in/username'}))
    telegram = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'placeholder': '@username или https://t.me/username'}))
    instagram = forms.URLField(required=False, widget=forms.URLInput(attrs={'placeholder': 'https://instagram.com/username'}))
    facebook = forms.URLField(required=False, widget=forms.URLInput(attrs={'placeholder': 'https://facebook.com/username'}))
    youtube = forms.URLField(required=False, widget=forms.URLInput(attrs={'placeholder': 'https://youtube.com/channel/username'}))

    class Meta:
        model = CustomUser
        fields = [
            'avatar', 'bio', 'location', 'birth_date', 'website', 'github', 'linkedin',
            'telegram', 'instagram', 'facebook', 'youtube'
        ]

    def __init__(self, *args, **kwargs):
        """
        Инициализация формы с данными пользователя.
        """
        self.user = kwargs.pop('user', None)
        self.avatar_only = kwargs.pop('avatar_only', False)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['username'].initial = self.user.username
            self.fields['email'].initial = self.user.email
            self.fields['first_name'].initial = self.user.first_name or ''
            self.fields['last_name'].initial = self.user.last_name or ''
            if self.instance and self.instance.birth_date:
                self.fields['birth_date'].initial = self.instance.birth_date.strftime('%Y-%m-%d')

    def clean_telegram(self):
        """
        Валидация поля Telegram (@username или URL).
        """
        telegram = self.cleaned_data.get('telegram', '').strip()
        if not telegram:
            return telegram
        if telegram.startswith('@'):
            if not re.match(r'^@[A-Za-z0-9_]{5,}$', telegram):
                raise ValidationError('Имя пользователя Telegram должно начинаться с @ и содержать минимум 5 символов.')
            return f'https://t.me/{telegram[1:]}'
        if not re.match(r'^https?://(t\.me|telegram\.me)/[A-Za-z0-9_]{5,}$', telegram):
            raise ValidationError('Введите корректный URL Telegram или имя пользователя.')
        return telegram

    def clean_website(self):
        """
        Валидация и нормализация URL сайта.
        """
        website = self.cleaned_data.get('website')
        if isinstance(website, list):
            website = next((item for item in website if item), '')
        if website:
            website = website.strip()
            if website and not website.startswith(('http://', 'https://')):
                website = f'https://{website}'
        return website or ''
    
    def clean_github(self):
        """Валидация и нормализация GitHub URL."""
        github = self.cleaned_data.get('github', '').strip() if self.cleaned_data.get('github') else ''
        if github and not github.startswith(('http://', 'https://')):
            github = f'https://{github}'
        return github or ''
    
    def clean_linkedin(self):
        """Валидация и нормализация LinkedIn URL."""
        linkedin = self.cleaned_data.get('linkedin', '').strip() if self.cleaned_data.get('linkedin') else ''
        if linkedin and not linkedin.startswith(('http://', 'https://')):
            linkedin = f'https://{linkedin}'
        return linkedin or ''
    
    def clean_instagram(self):
        """Валидация и нормализация Instagram URL."""
        instagram = self.cleaned_data.get('instagram', '').strip() if self.cleaned_data.get('instagram') else ''
        if instagram and not instagram.startswith(('http://', 'https://')):
            instagram = f'https://{instagram}'
        return instagram or ''
    
    def clean_facebook(self):
        """Валидация и нормализация Facebook URL."""
        facebook = self.cleaned_data.get('facebook', '').strip() if self.cleaned_data.get('facebook') else ''
        if facebook and not facebook.startswith(('http://', 'https://')):
            facebook = f'https://{facebook}'
        return facebook or ''
    
    def clean_youtube(self):
        """Валидация и нормализация YouTube URL."""
        youtube = self.cleaned_data.get('youtube', '').strip() if self.cleaned_data.get('youtube') else ''
        if youtube and not youtube.startswith(('http://', 'https://')):
            youtube = f'https://{youtube}'
        return youtube or ''

    def clean_email(self):
        """
        Валидация email: проверка уникальности, если email изменился.
        """
        email = self.cleaned_data.get('email', '').strip() if self.cleaned_data.get('email') else ''
        if not email:
            # Если email пустой, возвращаем текущий email пользователя
            return self.user.email if self.user and self.user.email else ''
        
        # Если email не изменился, возвращаем его как есть
        if self.user and self.user.email == email:
            return email
        
        # Проверяем уникальность email
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if User.objects.filter(email=email).exclude(id=self.user.id if self.user else None).exists():
            from django.core.exceptions import ValidationError
            raise ValidationError('Пользователь с таким email уже существует.')
        
        return email
    
    def clean_username(self):
        """
        Валидация username: проверка уникальности, если username изменился.
        """
        username = self.cleaned_data.get('username', '').strip() if self.cleaned_data.get('username') else ''
        if not username:
            # Если username пустой, возвращаем текущий username пользователя
            return self.user.username if self.user and self.user.username else ''
        
        # Если username не изменился, возвращаем его как есть
        if self.user and self.user.username == username:
            return username
        
        # Проверяем уникальность username
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if User.objects.filter(username=username).exclude(id=self.user.id if self.user else None).exists():
            from django.core.exceptions import ValidationError
            raise ValidationError('Пользователь с таким username уже существует.')
        
        return username
    
    def clean(self):
        """
        Валидация формы, установка дефолтных значений.
        """
        cleaned_data = super().clean()
        if self.avatar_only:
            return cleaned_data
        
        # Email и username уже проверены в clean_email и clean_username
        # Здесь только устанавливаем дефолтные значения если они пустые
        username = cleaned_data.get('username')
        email = cleaned_data.get('email')
        if not username and self.user:
            cleaned_data['username'] = self.user.username
        if not email and self.user:
            cleaned_data['email'] = self.user.email
        return cleaned_data

    def save(self, commit=True):
        """
        Сохранение изменений в CustomUser.
        После сохранения автоматически синхронизирует данные с MiniAppUser если есть связь.
        """
        user = super().save(commit=False)
        if not self.avatar_only:
            user.username = self.cleaned_data['username']
            user.email = self.cleaned_data['email']
            user.first_name = self.cleaned_data.get('first_name', '')
            user.last_name = self.cleaned_data.get('last_name', '')
        if commit:
            user.save()
            # Синхронизация с MiniAppUser выполняется автоматически через сигнал post_save
            # Но можно добавить логирование для отладки
            if hasattr(user, 'mini_app_profile') and user.mini_app_profile:
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Данные CustomUser (id={user.id}, username={user.username}) сохранены через форму. Синхронизация с MiniAppUser выполняется через сигнал post_save.")
        return user


class CustomPasswordResetForm(PasswordResetForm):
    """Кастомная форма для сброса пароля с поддержкой HTML email"""
    pass
