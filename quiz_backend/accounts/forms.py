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


class ProfileEditForm(forms.ModelForm):
    """
    Форма для редактирования профиля: avatar, bio, location, birth_date и т.д.
    """

    class Meta:
        model = Profile
        fields = [
            'avatar',
            'bio',
            'location',
            'birth_date',
            'website',
            'telegram',
            'github',
            'instagram',
            'facebook',
            'linkedin',
            'youtube',
            'email_notifications',
            'is_public',
            'theme_preference'
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
            'avatar': forms.FileInput(attrs={'accept': 'image/*'}),
            'theme_preference': forms.Select(attrs={'class': 'form-select'}),
            'telegram': forms.TextInput(attrs={'placeholder': '@username'}),
        }
        labels = {
            'telegram': 'Telegram Username',
            'is_public': 'Public Profile',
            'email_notifications': 'Email Notifications',
            'theme_preference': 'Theme',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем все поля необязательными
        for field in self.fields:
            self.fields[field].required = False
            if isinstance(self.fields[field], forms.URLField):
                self.fields[field].widget.attrs.update({
                    'placeholder': 'https://'
                })


class PersonalInfoForm(forms.ModelForm):
    """
    Форма для редактирования основных данных пользователя:
    username, email, first_name, last_name, bio, соц.сети и т.д.
    """
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    bio = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)
    github = forms.URLField(required=False)
    linkedin = forms.URLField(required=False)
    twitter = forms.URLField(required=False)
    website = forms.URLField(required=False)

    class Meta:
        model = Profile
        fields = ['avatar', 'location', 'bio']
        widgets = {
            'location': forms.TextInput(attrs={'class': 'location-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['username'].initial = user.username
            self.fields['email'].initial = user.email
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name