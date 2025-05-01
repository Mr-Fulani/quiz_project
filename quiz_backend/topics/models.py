from django.db import models
from django.core.exceptions import ValidationError




class Topic(models.Model):
    class Meta:
        db_table = 'topics'
        verbose_name = 'Тема'
        verbose_name_plural = 'Темы'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]

    id = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text='Название темы (например, Python, Golang и т.д.)'
    )
    description = models.TextField(
        null=True,
        help_text='Описание темы'
    )
    icon = models.CharField(
        max_length=255,
        default='/static/blog/images/icons/default-icon.png',
        help_text='Путь к иконке темы (например, blog/images/icons/java-icon.png)'
    )

    def __str__(self):
        return self.name

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        queryset |= self.__class__.objects.filter(name__icontains=search_term)
        return queryset, use_distinct
    



class Subtopic(models.Model):
    class Meta:
        db_table = 'subtopics'
        verbose_name = 'Подтема'
        verbose_name_plural = 'Подтемы'
        ordering = ['topic', 'name']
        indexes = [
            models.Index(fields=['topic', 'name']),
        ]

    id = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=255,
        help_text='Название подтемы'
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='subtopics',
        help_text='Родительская тема'
    )

    def __str__(self):
        return f"{self.topic.name} - {self.name}"

    def clean(self):
        if Subtopic.objects.filter(
            topic=self.topic,
            name=self.name
        ).exclude(id=self.id).exists():
            raise ValidationError('Подтема с таким названием уже существует в данной теме')


