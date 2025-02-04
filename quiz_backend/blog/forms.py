from django import forms
from accounts.models import Profile, CustomUser


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar', 'bio', 'location', 'birth_date', 'website', 'email_notifications', 'is_public', 'theme_preference']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
            'website': forms.URLInput(attrs={'placeholder': 'https://'}),
            'location': forms.TextInput(attrs={'placeholder': 'City, Country'})
        }

class PersonalInfoForm(forms.ModelForm):
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