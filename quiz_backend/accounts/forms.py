import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Profile

class CustomUserCreationForm(UserCreationForm):
    """
    Форма для регистрации нового пользователя (CustomUser).
    """
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = UserCreationForm.Meta.fields + ('email',)

    def save(self, commit=True):
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
    birth_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    website = forms.URLField(required=False)
    github = forms.URLField(required=False)
    linkedin = forms.URLField(required=False)
    telegram = forms.URLField(required=False)
    twitter = forms.URLField(required=False)
    instagram = forms.URLField(required=False)
    facebook = forms.URLField(required=False)
    youtube = forms.URLField(required=False)

    class Meta:
        model = Profile
        fields = ['avatar', 'bio', 'location', 'birth_date', 'website', 'github', 'linkedin',
                  'telegram', 'twitter', 'instagram', 'facebook', 'youtube']

    def __init__(self, *args, **kwargs):
        """
        Инициализация формы.
        Подтягивает username и email из request.user.
        Если avatar_only=True, отключает валидацию username и email.
        """
        self.user = kwargs.pop('user', None)
        self.avatar_only = kwargs.pop('avatar_only', False)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['username'].initial = self.user.username
            self.fields['email'].initial = self.user.email

    def clean(self):
        """
        Валидация формы.
        Пропускает username и email, если они не изменены или avatar_only=True.
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
        Сохранение формы.
        Обновляет username и email в CustomUser, остальные поля в Profile.
        """
        profile = super().save(commit=False)
        user = self.user
        if not self.avatar_only:
            user.username = self.cleaned_data['username']
            user.email = self.cleaned_data['email']
            user.first_name = self.cleaned_data.get('first_name', '')
            user.last_name = self.cleaned_data.get('last_name', '')
            if commit:
                user.save()
        if self.cleaned_data.get('birth_date'):
            profile.birth_date = self.cleaned_data['birth_date']
        if commit:
            profile.save()
        return profile

