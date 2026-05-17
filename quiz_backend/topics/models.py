from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from .utils import normalize_subtopic_name


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
            models.Index(fields=['tenant', 'name']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_topic_name_per_tenant'
            )
        ]

    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='topics',
        null=True,
        blank=True,
        verbose_name=_('Тенант'),
        help_text=_('Тенант (инстанс платформы), которому принадлежит эта тема')
    )
    name = models.CharField(
        max_length=255,
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
    icon_svg = models.TextField(
        null=True, 
        blank=True, 
        verbose_name="SVG код иконки",
        help_text="Если указано, будет использоваться вместо стандартной иконки. Можно вставить SVG код целиком."
    )
    icon_image = models.ImageField(
        upload_to='topic_icons/',
        null=True,
        blank=True,
        verbose_name="Файл иконки",
        validators=[
            validate_file_size,
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'svg'])
        ],
        help_text="Загрузите файл иконки (PNG, JPG или SVG). Используется, если не указан SVG код."
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

    def get_translation(self, language_code=None):
        """
        Возвращает наиболее подходящий перевод темы с fallback:
        1. запрошенный язык
        2. английский
        3. любой доступный перевод
        """
        translations = list(self.translations.all())
        if not translations:
            return None

        requested = (language_code or '').strip().lower()
        if requested:
            for translation in translations:
                if translation.language_code == requested:
                    return translation

        for translation in translations:
            if translation.language_code == 'en':
                return translation

        return translations[0]

    def get_localized_name(self, language_code=None):
        translation = self.get_translation(language_code)
        return translation.name if translation and translation.name else self.name

    def get_localized_description(self, language_code=None):
        translation = self.get_translation(language_code)
        if translation and translation.description:
            return translation.description
        return self.description
    
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
        constraints = [
            models.UniqueConstraint(fields=['topic', 'name'], name='unique_subtopic_per_topic')
        ]
        # Примечание: tenant изоляция работает автоматически через topic FK
        # topic.tenant → subtopic принадлежит тому же тенанту

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

    def get_translation(self, language_code=None):
        """
        Возвращает наиболее подходящий перевод подтемы с fallback:
        1. запрошенный язык
        2. английский
        3. любой доступный перевод
        """
        translations = list(self.translations.all())
        if not translations:
            return None

        requested = (language_code or '').strip().lower()
        if requested:
            for translation in translations:
                if translation.language_code == requested:
                    return translation

        for translation in translations:
            if translation.language_code == 'en':
                return translation

        return translations[0]

    def get_localized_name(self, language_code=None):
        translation = self.get_translation(language_code)
        return translation.name if translation and translation.name else self.name

    def get_localized_description(self, language_code=None):
        translation = self.get_translation(language_code)
        if translation and translation.description:
            return translation.description
        return None

    def clean(self):
        self.name = normalize_subtopic_name(self.name)
        if Subtopic.objects.filter(
            topic=self.topic,
            name=self.name
        ).exclude(id=self.id).exists():
            raise ValidationError('Подтема с таким названием уже существует в данной теме')

    def save(self, *args, **kwargs):
        """
        Нормализует имя при каждом сохранении.
        """
        self.name = normalize_subtopic_name(self.name)
        super().save(*args, **kwargs)

class TopicTranslation(models.Model):
    class Meta:
        db_table = 'topic_translations'
        verbose_name = 'Перевод темы'
        verbose_name_plural = 'Переводы тем'
        indexes = [
            models.Index(fields=['language_code']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['topic', 'language_code'],
                name='unique_topic_translation_per_language'
            )
        ]

    id = models.AutoField(primary_key=True)
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='translations',
        help_text='Связанная тема'
    )
    language_code = models.CharField(
        max_length=10,
        help_text='Код языка перевода'
    )
    name = models.CharField(
        max_length=255,
        help_text='Локализованное название темы'
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text='Локализованное описание темы'
    )

    def save(self, *args, **kwargs):
        self.language_code = (self.language_code or '').strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.topic_id} [{self.language_code}] {self.name}"


class SubtopicTranslation(models.Model):
    class Meta:
        db_table = 'subtopic_translations'
        verbose_name = 'Перевод подтемы'
        verbose_name_plural = 'Переводы подтем'
        indexes = [
            models.Index(fields=['language_code']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['subtopic', 'language_code'],
                name='unique_subtopic_translation_per_language'
            )
        ]

    id = models.AutoField(primary_key=True)
    subtopic = models.ForeignKey(
        Subtopic,
        on_delete=models.CASCADE,
        related_name='translations',
        help_text='Связанная подтема'
    )
    language_code = models.CharField(
        max_length=10,
        help_text='Код языка перевода'
    )
    name = models.CharField(
        max_length=255,
        help_text='Локализованное название подтемы'
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text='Локализованное описание подтемы'
    )

    def save(self, *args, **kwargs):
        self.language_code = (self.language_code or '').strip().lower()
        self.name = normalize_subtopic_name(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.subtopic_id} [{self.language_code}] {self.name}"

