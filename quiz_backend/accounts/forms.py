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
        if website and not website.startswith(('http://', 'https://')):
            website = f'https://{website}'
        return website

    def clean(self):
        """
        Валидация формы, установка дефолтных значений.
        """
        cleaned_data = super().clean()
        if self.avatar_only:
            return cleaned_data
        username = cleaned_data.get('username')
        email = cleaned_data.get('email')
        if not username:
            cleaned_data['username'] = self.user.username
        if not email:
            cleaned_data['email'] = self.user.email
        return cleaned_data

    def save(self, commit=True):
        """
        Сохранение изменений в CustomUser.
        """
        user = super().save(commit=False)
        if not self.avatar_only:
            user.username = self.cleaned_data['username']
            user.email = self.cleaned_data['email']
            user.first_name = self.cleaned_data.get('first_name', '')
            user.last_name = self.cleaned_data.get('last_name', '')
        if commit:
            user.save()
        return user


class CustomPasswordResetForm(PasswordResetForm):
    """Кастомная форма для сброса пароля с поддержкой HTML email"""
    pass
