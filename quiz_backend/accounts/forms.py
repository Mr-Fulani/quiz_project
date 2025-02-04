from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Profile

class CustomUserCreationForm(UserCreationForm):
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
    class Meta:
        model = Profile
        fields = [
            'avatar', 
            'bio', 
            'location', 
            'birth_date', 
            'website',
            # Социальные сети
            'telegram',
            'github',
            'instagram',
            'facebook',
            'linkedin',
            'youtube',
            # Настройки
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
                    'placeholder': f'https://'
                }) 