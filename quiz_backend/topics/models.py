from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator


def validate_file_size(value):
    """
    Валидатор для проверки размера файла (максимум 50 МБ)
    """
    filesize = value.size
    max_size_mb = 50
    max_size_bytes = max_size_mb * 1024 * 1024  # 50 МБ в байтах
    
    if filesize > max_size_bytes:
        raise ValidationError(f'Максимальный размер файла {max_size_mb} МБ. Размер вашего файла: {filesize / (1024 * 1024):.2f} МБ')
    return value




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
    
    # Медиа для карточки темы в карусели мини-приложения
    card_image = models.ImageField(
        upload_to='topic_cards/images/',
        null=True,
        blank=True,
        validators=[
            validate_file_size,
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])
        ],
        help_text='Изображение или GIF для карточки темы (макс. 50 МБ). Поддерживаемые форматы: JPG, PNG, GIF'
    )
    
    card_video = models.FileField(
        upload_to='topic_cards/videos/',
        null=True,
        blank=True,
        validators=[
            validate_file_size,
            FileExtensionValidator(allowed_extensions=['mp4', 'webm', 'mov'])
        ],
        help_text='Видео для карточки темы (макс. 50 МБ). Поддерживаемые форматы: MP4, WEBM, MOV'
    )
    
    video_poster = models.ImageField(
        upload_to='topic_cards/posters/',
        null=True,
        blank=True,
        validators=[
            validate_file_size,
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])
        ],
        help_text='Постер для видео (превью перед воспроизведением). Опционально. Поддерживаемые форматы: JPG, PNG'
    )
    
    MEDIA_TYPE_CHOICES = [
        ('default', 'По умолчанию (picsum.photos)'),
        ('image', 'Изображение/GIF'),
        ('video', 'Видео'),
    ]
    
    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        default='default',
        help_text='Тип медиа для отображения в карусели'
    )

    def __str__(self):
        return self.name
    
    def clean(self):
        """
        Валидация модели: проверяем соответствие media_type и загруженных файлов
        """
        super().clean()
        
        if self.media_type == 'image' and not self.card_image:
            raise ValidationError({
                'card_image': 'Необходимо загрузить изображение, если выбран тип медиа "Изображение/GIF"'
            })
        
        if self.media_type == 'video' and not self.card_video:
            raise ValidationError({
                'card_video': 'Необходимо загрузить видео, если выбран тип медиа "Видео"'
            })
        
        # Предупреждаем, если загружены оба файла
        if self.card_image and self.card_video:
            if self.media_type == 'default':
                raise ValidationError(
                    'Вы загрузили и изображение, и видео. Выберите тип медиа для отображения.'
                )

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


