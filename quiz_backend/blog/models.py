from django.db import models
from django.utils.text import slugify
from accounts.models import CustomUser  # Оставляем только нужные импорты

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_portfolio = models.BooleanField(default=False, verbose_name='Portfolio Category')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({'Portfolio' if self.is_portfolio else 'Blog'})"

class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    excerpt = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    image = models.ImageField(upload_to='blog/posts/', blank=True)
    published = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    views_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Пост'
        verbose_name_plural = 'Посты'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

class Project(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    technologies = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category, 
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    image = models.ImageField(upload_to='blog/projects/')
    github_link = models.URLField(blank=True)
    demo_link = models.URLField(blank=True)
    featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

class MessageAttachment(models.Model):
    message = models.ForeignKey('Message', on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='message_attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

class Message(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    is_deleted_by_sender = models.BooleanField(default=False)
    is_deleted_by_recipient = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def soft_delete(self, user):
        if user == self.sender:
            self.is_deleted_by_sender = True
        elif user == self.recipient:
            self.is_deleted_by_recipient = True
        self.save()

    @property
    def is_completely_deleted(self):
        return self.is_deleted_by_sender and self.is_deleted_by_recipient
