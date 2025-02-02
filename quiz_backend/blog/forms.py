from django import forms
from accounts.models import Profile


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