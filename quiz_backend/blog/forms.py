from django import forms
from .models import Post, Project, Testimonial


class ContactForm(forms.Form):
    fullname = forms.CharField(max_length=100, label="Полное имя")
    email = forms.EmailField(label="Email")
    message = forms.CharField(widget=forms.Textarea, label="Сообщение")


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'content', 'category', 'published']


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'description', 'category', 'featured']


class TestimonialForm(forms.ModelForm):
    class Meta:
        model = Testimonial
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 4}),
        }

class TaskFilterForm(forms.Form):
    difficulty = forms.ChoiceField(choices=[('', 'Любая сложность'), ('easy', 'Легкий'), ('medium', 'Средний'), ('hard', 'Сложный')], required=False)
    # Другие поля для фильтрации можно добавить здесь 