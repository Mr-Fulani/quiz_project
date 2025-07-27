# blog/models.py
import logging
import os

from PIL import Image, ImageOps
import re
from django.core.validators import URLValidator, ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.urls import reverse
from django.utils import translation
from django.utils.text import slugify
from accounts.models import CustomUser
from django.contrib.auth import get_user_model
from tinymce.models import HTMLField
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit
from django.conf import settings

User = get_user_model()

logger = logging.getLogger(__name__)


class Category(models.Model):
    """Модель категории для постов и проектов портфолио."""
    name = models.CharField(max_length=100, verbose_name="Название категории")
    slug = models.SlugField(unique=True, verbose_name="Слаг категории")
    description = models.TextField(blank=True, verbose_name="Описание категории")
    is_portfolio = models.BooleanField(
        default=False,
        verbose_name="Категория портфолио",
        help_text="Укажите, если категория предназначена для портфолио, а не блога."
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["name"]

    def __str__(self):
        """Возвращает строковое представление категории."""
        return f"{self.name} ({'Portfolio' if self.is_portfolio else 'Blog'})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Post(models.Model):
    """Модель поста блога."""
    title = models.CharField(max_length=200, verbose_name="Заголовок поста")
    slug = models.SlugField(unique=True, verbose_name="Слаг поста")
    content = HTMLField(verbose_name="Содержимое поста")
    excerpt = HTMLField(blank=True, verbose_name="Краткое описание")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        verbose_name="Категория"
    )
    video_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="Ссылка на видео",
        help_text="URL-адрес видео (например, YouTube)"
    )
    published = models.BooleanField(default=False, verbose_name="Опубликовано")
    featured = models.BooleanField(default=False, verbose_name="Избранное")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата публикации"
    )
    views_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество просмотров"
    )
    meta_description = models.CharField(max_length=160, blank=True, verbose_name="Мета-описание")
    meta_keywords = models.CharField(max_length=255, blank=True, verbose_name="Мета-ключевые слова")

    class Meta:
        verbose_name = "Пост"
        verbose_name_plural = "Посты"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_main_image(self):
        main_image = self.images.filter(is_main=True).first()
        if not main_image:
            main_image = self.images.first()
        return main_image

    def get_absolute_url(self):
        """Возвращает абсолютный URL поста."""
        return reverse('blog:post_detail', kwargs={'slug': self.slug})

    def get_likes_count(self):
        """Возвращает количество лайков поста."""
        return self.likes.count()

    def get_shares_count(self):
        """Возвращает количество репостов поста."""
        return self.shares.count()

    def is_liked_by_user(self, user):
        """Проверяет, лайкнул ли пользователь этот пост."""
        if user.is_authenticated:
            return self.likes.filter(user=user).exists()
        return False

    def is_shared_by_user(self, user):
        """Проверяет, поделился ли пользователь этим постом."""
        if user.is_authenticated:
            return self.shares.filter(user=user).exists()
        return False

    def get_og_image_url(self):
        """Возвращает URL для Open Graph изображения (генерирует если нужно)."""
        from .utils import save_og_image
        import os
        from django.conf import settings
        
        # Проверяем есть ли у поста своя картинка
        main_image = self.get_main_image()
        if main_image and main_image.photo:
            return main_image.photo.url
            
        # Проверяем есть ли уже сгенерированная OG картинка
        og_filename = f'og_post_{self.slug}.jpg'
        og_path = os.path.join(settings.MEDIA_ROOT, 'og_images', og_filename)
        
        if os.path.exists(og_path):
            return f'{settings.MEDIA_URL}og_images/{og_filename}'
        
        # Генерируем новую OG картинку
        try:
            og_url = save_og_image(
                title=self.title,
                category=self.category.name if self.category else 'Blog',
                slug=self.slug,
                content_type='post'
            )
            return og_url
        except Exception as e:
            print(f"Ошибка генерации OG изображения для поста {self.slug}: {e}")
            return f'{settings.STATIC_URL}blog/images/default-og-image.jpeg'


class PostImage(models.Model):
    """Модель медиафайлов для постов блога."""
    post = models.ForeignKey(
        Post,
        related_name="images",
        on_delete=models.CASCADE,
        verbose_name="Пост"
    )
    photo = models.ImageField(
        upload_to="blog/posts/photos/",
        blank=True,
        null=True,
        verbose_name="Фото (JPG/PNG)",
        help_text="Загрузите статичное изображение (JPG или PNG) для поста."
    )
    photo_thumbnail = ImageSpecField(
        source='photo',
        processors=[ResizeToFit(800, 800)],
        format='JPEG',
        options={'quality': 85}
    )
    gif = models.FileField(
        upload_to="blog/posts/gifs/",
        blank=True,
        null=True,
        verbose_name="GIF (анимация)",
        help_text="Загрузите анимированный GIF для поста."
    )
    video = models.FileField(
        upload_to="blog/posts/videos/",
        blank=True,
        null=True,
        verbose_name="Видео (MP4)",
        help_text="Загрузите видео в формате MP4 для поста."
    )
    is_main = models.BooleanField(
        default=False,
        verbose_name="Главное изображение",
        help_text="Отметьте, если это медиа будет отображаться как миниатюра поста."
    )
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Alt текст",
        help_text="Текст, который будет отображаться, если изображение не загрузится. Важно для SEO."
    )

    class Meta:
        verbose_name = "Медиа поста"
        verbose_name_plural = "Медиа постов"

    def __str__(self):
        """Возвращает строковое представление медиафайла поста."""
        if self.photo:
            return f"Photo for {self.post.title}"
        elif self.gif:
            return f"GIF for {self.post.title}"
        elif self.video:
            return f"Video for {self.post.title}"
        return f"Media for {self.post.title}"

    def save(self, *args, **kwargs):
        if not self.alt_text:
            self.alt_text = self.post.title
        super().save(*args, **kwargs)

        # Обработка photo
        if self.photo:
            img = Image.open(self.photo.path)
            img = ImageOps.fit(img, (800, 800), Image.LANCZOS)
            img.save(self.photo.path, quality=85, optimize=True)

        # Обработка gif (если это не анимированный GIF)
        if self.gif:
            img = Image.open(self.gif.path)
            if not getattr(img, "is_animated", False):  # Проверяем, не анимированный ли GIF
                img = ImageOps.fit(img, (800, 800), Image.LANCZOS)
                img.save(self.gif.path, quality=85, optimize=True)


class Project(models.Model):
    """Модель проекта портфолио."""
    title = models.CharField(max_length=200, verbose_name="Название проекта")
    slug = models.SlugField(unique=True, verbose_name="Слаг проекта")
    description = HTMLField(verbose_name="Описание проекта")  # Заменяем TextField на HTMLField
    technologies = models.CharField(
        max_length=200,
        verbose_name="Технологии",
        help_text="Список использованных технологий (например, Python, Django)."
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Категория"
    )
    video_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="Ссылка на видео",
        help_text="URL-адрес видео (например, YouTube)"
    )
    github_link = models.URLField(
        blank=True,
        verbose_name="Ссылка на GitHub",
        help_text="URL-адрес репозитория на GitHub"
    )
    demo_link = models.URLField(
        blank=True,
        verbose_name="Ссылка на демо",
        help_text="URL-адрес живой демонстрации проекта"
    )
    featured = models.BooleanField(default=False, verbose_name="Избранное")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    meta_description = models.CharField(max_length=160, blank=True, verbose_name="Мета-описание")
    meta_keywords = models.CharField(max_length=255, blank=True, verbose_name="Мета-ключевые слова")
    views_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество просмотров"
    )

    class Meta:
        verbose_name = "Проект"
        verbose_name_plural = "Проекты"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_main_image(self):
        main_image = self.images.filter(is_main=True).first()
        if not main_image:
            main_image = self.images.first()
        return main_image

    def get_absolute_url(self):
        """Возвращает абсолютный URL проекта."""
        return reverse('blog:project_detail', kwargs={'slug': self.slug})

    def get_likes_count(self):
        """Возвращает количество лайков проекта."""
        return self.likes.count()

    def get_shares_count(self):
        """Возвращает количество репостов проекта."""
        return self.shares.count()

    def is_liked_by_user(self, user):
        """Проверяет, лайкнул ли пользователь этот проект."""
        if user.is_authenticated:
            return self.likes.filter(user=user).exists()
        return False

    def is_shared_by_user(self, user):
        """Проверяет, поделился ли пользователь этим проектом."""
        if user.is_authenticated:
            return self.shares.filter(user=user).exists()
        return False

    def get_og_image_url(self):
        """Возвращает URL для Open Graph изображения (генерирует если нужно)."""
        from .utils import save_og_image
        import os
        from django.conf import settings
        
        # Проверяем есть ли у проекта своя картинка
        main_image = self.get_main_image()
        if main_image and main_image.photo:
            return main_image.photo.url
            
        # Проверяем есть ли уже сгенерированная OG картинка
        og_filename = f'og_project_{self.slug}.jpg'
        og_path = os.path.join(settings.MEDIA_ROOT, 'og_images', og_filename)
        
        if os.path.exists(og_path):
            return f'{settings.MEDIA_URL}og_images/{og_filename}'
        
        # Генерируем новую OG картинку
        try:
            og_url = save_og_image(
                title=self.title,
                category='Portfolio',
                slug=self.slug,
                content_type='project'
            )
            return og_url
        except Exception as e:
            print(f"Ошибка генерации OG изображения для проекта {self.slug}: {e}")
            return f'{settings.STATIC_URL}blog/images/default-og-image.jpeg'


class ProjectImage(models.Model):
    """Модель медиафайлов для проектов портфолио."""
    project = models.ForeignKey(
        Project,
        related_name="images",
        on_delete=models.CASCADE,
        verbose_name="Проект"
    )
    photo = models.ImageField(
        upload_to="blog/projects/photos/",
        blank=True,
        null=True,
        verbose_name="Фото (JPG/PNG)",
        help_text="Загрузите статичное изображение (JPG или PNG) для проекта."
    )
    photo_thumbnail = ImageSpecField(
        source='photo',
        processors=[ResizeToFit(800, 800)],
        format='JPEG',
        options={'quality': 85}
    )
    gif = models.FileField(
        upload_to="blog/projects/gifs/",
        blank=True,
        null=True,
        verbose_name="GIF (анимация)",
        help_text="Загрузите анимированный GIF для проекта."
    )
    video = models.FileField(
        upload_to="blog/projects/videos/",
        blank=True,
        null=True,
        verbose_name="Видео (MP4)",
        help_text="Загрузите видео в формате MP4 для проекта."
    )
    is_main = models.BooleanField(
        default=False,
        verbose_name="Главное изображение",
        help_text="Отметьте, если это медиа будет отображаться как миниатюра проекта."
    )
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Alt текст",
        help_text="Текст, который будет отображаться, если изображение не загрузится. Важно для SEO."
    )

    class Meta:
        verbose_name = "Медиа проекта"
        verbose_name_plural = "Медиа проектов"

    def __str__(self):
        """Возвращает строковое представление медиафайла проекта."""
        if self.photo:
            return f"Photo for {self.project.title}"
        elif self.gif:
            return f"GIF for {self.project.title}"
        elif self.video:
            return f"Video for {self.project.title}"
        return f"Media for {self.project.title}"

    def save(self, *args, **kwargs):
        if not self.alt_text:
            self.alt_text = self.project.title
        super().save(*args, **kwargs)

        # Обработка photo
        if self.photo:
            img = Image.open(self.photo.path)
            img = ImageOps.fit(img, (800, 800), Image.LANCZOS)
            img.save(self.photo.path, quality=85, optimize=True)

        # Обработка gif
        if self.gif:
            img = Image.open(self.gif.path)
            if not getattr(img, "is_animated", False):
                img = ImageOps.fit(img, (800, 800), Image.LANCZOS)
                img.save(self.gif.path, quality=85, optimize=True)


class MessageAttachment(models.Model):
    """Модель вложений для сообщений."""
    message = models.ForeignKey(
        "Message",
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Сообщение"
    )
    file = models.FileField(
        upload_to="message_attachments/%Y/%m/%d/",
        verbose_name="Файл"
    )
    filename = models.CharField(max_length=255, verbose_name="Имя файла")
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата загрузки"
    )

    class Meta:
        verbose_name = "Вложение сообщения"
        verbose_name_plural = "Вложения сообщений"

    def __str__(self):
        """Возвращает строковое представление вложения."""
        return f"Attachment {self.filename} for message {self.message.id}"

    def save(self, *args, **kwargs):
        """
        Сохраняет вложение, сжимая изображения (JPG, JPEG, PNG, неанимированный GIF).

        Сжимает изображения до размера 800x800 пикселей в формате JPEG с качеством 85.
        Анимированные GIF и другие файлы (PDF, MP4) сохраняются без изменений.
        """
        if self.file and self.filename:
            # Проверяем, является ли файл изображением
            ext = os.path.splitext(self.filename)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif']:
                try:
                    # Открываем изображение
                    img = Image.open(self.file)
                    # Проверяем, анимированный ли GIF
                    is_animated = ext == '.gif' and getattr(img, "is_animated", False)
                    if not is_animated:
                        # Конвертируем в RGB (для JPEG)
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        # Сжимаем до 800x800
                        img = ImageOps.fit(img, (800, 800), Image.LANCZOS)
                        # Сохраняем сжатое изображение
                        output_path = self.file.path
                        img.save(output_path, format='JPEG', quality=85, optimize=True)
                        # Обновляем filename, если расширение изменилось
                        if ext != '.jpg':
                            new_filename = os.path.splitext(self.filename)[0] + '.jpg'
                            self.filename = new_filename
                            # Переименовываем файл на диске
                            new_path = os.path.splitext(output_path)[0] + '.jpg'
                            os.rename(output_path, new_path)
                            self.file.name = os.path.join(
                                os.path.dirname(self.file.name), os.path.basename(new_path)
                            )
                except Exception as e:
                    # Логируем ошибку, но не прерываем сохранение
                    from django.utils import timezone
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Ошибка сжатия изображения {self.filename}: {str(e)}")
        super().save(*args, **kwargs)


class Message(models.Model):
    """Модель сообщений между пользователями."""
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True, blank=True,  # Разрешить NULL для анонимных отправителей
        related_name="sent_messages",
        verbose_name="Отправитель"
    )
    recipient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="received_messages",
        verbose_name="Получатель"
    )
    content = models.TextField(verbose_name="Содержимое сообщения")
    fullname = models.CharField(
        max_length=255,
        default="Unknown",  # Значение по умолчанию
        verbose_name="Полное имя"
    )
    email = models.EmailField(
        default="unknown@example.com",  # Значение по умолчанию
        verbose_name="Email"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    is_deleted_by_sender = models.BooleanField(
        default=False,
        verbose_name="Удалено отправителем"
    )
    is_deleted_by_recipient = models.BooleanField(
        default=False,
        verbose_name="Удалено получателем"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        """Возвращает строковое представление сообщения."""
        return f"Message from {self.fullname} ({self.email}) to {self.recipient or 'No recipient'}"

    def soft_delete(self, user):
        """Выполняет мягкое удаление сообщения для указанного пользователя."""
        if user == self.sender:
            self.is_deleted_by_sender = True
        elif user == self.recipient:
            self.is_deleted_by_recipient = True
        self.save()

    @property
    def is_completely_deleted(self):
        """Проверяет, полностью ли удалено сообщение (обоими сторонами)."""
        return self.is_deleted_by_sender and self.is_deleted_by_recipient


class PageVideo(models.Model):
    """
    Модель для хранения видео, специфичных для страниц 'index' и 'about'.

    Позволяет добавлять видео (YouTube или локальные) через админку для отображения
    на главной странице или странице "Обо мне".
    """
    PAGE_CHOICES = (
        ('index', 'Главная страница'),
        ('about', 'Страница "Обо мне"'),
    )

    page = models.CharField(
        max_length=10,
        choices=PAGE_CHOICES,
        verbose_name="Страница",
        help_text="Выберите страницу, для которой предназначено видео."
    )
    title = models.CharField(
        max_length=200,
        verbose_name="Название видео",
        help_text="Название, которое будет отображаться под видео."
    )
    video_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="Ссылка на YouTube",
        help_text="Вставьте ссылку на YouTube-видео (например, https://www.youtube.com/watch?v=xxx)."
    )
    video_file = models.FileField(
        upload_to='videos/page_videos/',
        blank=True,
        null=True,
        verbose_name="Локальный видеофайл",
        help_text="Загрузите локальный видеофайл (например, .mp4), если не используете YouTube."
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок отображения",
        help_text="Число, определяющее порядок видео в списке (меньше — выше)."
    )
    gif = models.FileField(
        upload_to='gifs/page_videos/',
        blank=True, null=True,
        verbose_name="GIF-файл")

    class Meta:
        verbose_name = "Видео для страницы"
        verbose_name_plural = "Видео для страниц"
        ordering = ['order', 'title']

    def __str__(self):
        return f"{self.title} ({self.get_page_display()})"


class Testimonial(models.Model):
    """
    Модель для хранения отзывов пользователей.

    Attributes:
        user (ForeignKey): Связь с пользователем, оставившим отзыв
        text (TextField): Текст отзыва
        created_at (DateTimeField): Дата и время создания отзыва
        is_approved (BooleanField): Статус модерации отзыва
    """
    user = models.ForeignKey(
        get_user_model(), 
        on_delete=models.CASCADE, 
        related_name='testimonials',
        verbose_name="Пользователь"
    )
    text = models.TextField(verbose_name="Текст отзыва")
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    is_approved = models.BooleanField(
        default=False,
        verbose_name="Одобрен"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"

    def __str__(self):
        return f'Отзыв от {self.user.username}'


class CustomURLValidator(URLValidator):
    """Кастомный валидатор для URL, включая tg:// протокол."""
    schemes = ['http', 'https', 'ftp', 'ftps', 'tg']

    def __call__(self, value):
        if not value:
            return value

        value = value.strip()

        if value.startswith('tg://'):
            # Валидация Telegram-ссылок
            self._validate_telegram_url(value)
            return value
        else:
            # Для обычных URL используем стандартную валидацию
            try:
                super().__call__(value)
            except (ValidationError, DjangoValidationError) as e:
                raise ValidationError(f'Недопустимый URL: {str(e)}')
            return value

    def _validate_telegram_url(self, value):
        """Валидирует Telegram URL."""
        # Паттерны для различных типов Telegram-ссылок
        patterns = [
            # tg://resolve?domain=@username
            r'^tg://resolve\?domain=@[\w\-_]+$',
            # tg://resolve?domain@username (ваш формат)
            r'^tg://resolve\?domain@[\w\-_]+$',
            # tg://resolve?domain=username (без @)
            r'^tg://resolve\?domain=[\w\-_]+$',
            # tg://msg_url?url=... (для сообщений)
            r'^tg://msg_url\?url=.+$',
            # tg://join?invite=... (для приглашений)
            r'^tg://join\?invite=[\w\-_]+$',
            # tg://addstickers?set=... (для стикеров)
            r'^tg://addstickers\?set=[\w\-_]+$',
        ]

        # Проверяем соответствие хотя бы одному паттерну
        for pattern in patterns:
            if re.match(pattern, value, re.IGNORECASE):
                return True

        # Если ни один паттерн не подошел, выбрасываем ошибку
        raise ValidationError(
            'Недопустимый формат Telegram-ссылки. '
            'Поддерживаемые форматы:\n'
            '• tg://resolve?domain=@username\n'
            '• tg://resolve?domain@username\n'
            '• tg://resolve?domain=username\n'
            '• tg://msg_url?url=...\n'
            '• tg://join?invite=...\n'
            '• tg://addstickers?set=...'
        )


class MarqueeText(models.Model):
    """
    Модель для бегущей строки с поддержкой нескольких языков.
    """
    text = models.CharField(max_length=255, blank=True, help_text="Основной текст (используется как запасной)")
    text_en = models.CharField(max_length=255, blank=True, verbose_name="Текст (английский)")
    text_ru = models.CharField(max_length=255, blank=True, verbose_name="Текст (русский)")
    text_es = models.CharField(max_length=255, blank=True, verbose_name="Текст (испанский)")
    text_fr = models.CharField(max_length=255, blank=True, verbose_name="Текст (французский)")
    text_de = models.CharField(max_length=255, blank=True, verbose_name="Текст (немецкий)")
    text_zh = models.CharField(max_length=255, blank=True, verbose_name="Текст (китайский)")
    text_ja = models.CharField(max_length=255, blank=True, verbose_name="Текст (японский)")
    text_tj = models.CharField(max_length=255, blank=True, verbose_name="Текст (таджикский)")
    text_tr = models.CharField(max_length=255, blank=True, verbose_name="Текст (турецкий)")
    text_ar = models.CharField(max_length=255, blank=True, verbose_name="Текст (арабский)")
    is_active = models.BooleanField(default=False, verbose_name="Активно")
    link_url = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="URL ссылки",
        validators=[CustomURLValidator()],  # Используем исправленный валидатор
        help_text="URL для ссылки (поддерживает http/https и Telegram-ссылки: tg://resolve?domain@username)"
    )
    link_target_blank = models.BooleanField(default=False, verbose_name="Открывать ссылку в новой вкладке")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок отображения",
                                        help_text="Число, определяющее порядок строки (меньше — выше).")

    class Meta:
        verbose_name = "Бегущая строка"
        verbose_name_plural = "Бегущие строки"
        ordering = ['order', 'text']

    def __str__(self):
        return self.text or "No text"

    def get_text(self):
        """
        Возвращает текст на текущем языке или английский по умолчанию.
        Если текст для текущего языка не заполнен, возвращает self.text.
        """
        lang_code = translation.get_language() or 'en'
        logger.info(f"get_text called: lang_code={lang_code}")
        text_field = f"text_{lang_code.split('-')[0]}"  # Учитываем en-US → en
        text = getattr(self, text_field, '')
        return text or self.text or ''

    def clean(self):
        """
        Дополнительная валидация на уровне модели.
        """
        super().clean()

        # Проверяем, что хотя бы один текст заполнен
        if not any([self.text, self.text_en, self.text_ru, self.text_es, self.text_fr,
                    self.text_de, self.text_zh, self.text_ja, self.text_tj, self.text_tr, self.text_ar]):
            raise ValidationError('Необходимо заполнить хотя бы одно текстовое поле')

    def save(self, *args, **kwargs):
        """
        Переопределяем сохранение для дополнительной обработки.
        """
        # Если основной текст пуст, но есть английский - копируем его
        if not self.text and self.text_en:
            self.text = self.text_en

        super().save(*args, **kwargs)


class PostLike(models.Model):
    """Модель лайков для постов."""
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        verbose_name="Пользователь"
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="likes",
        verbose_name="Пост"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        unique_together = ('user', 'post')
        verbose_name = "Лайк поста"
        verbose_name_plural = "Лайки постов"

    def __str__(self):
        return f"{self.user.username} лайкнул {self.post.title}"


class ProjectLike(models.Model):
    """Модель лайков для проектов."""
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        verbose_name="Пользователь"
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="likes",
        verbose_name="Проект"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        unique_together = ('user', 'project')
        verbose_name = "Лайк проекта"
        verbose_name_plural = "Лайки проектов"

    def __str__(self):
        return f"{self.user.username} лайкнул {self.project.title}"


class PostShare(models.Model):
    """Модель репостов для постов."""
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        verbose_name="Пользователь"
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="shares",
        verbose_name="Пост"
    )
    shared_url = models.URLField(
        blank=True,
        verbose_name="URL репоста",
        help_text="Ссылка на репост в социальной сети"
    )
    platform = models.CharField(
        max_length=50,
        choices=[
            ('telegram', 'Telegram'),
            ('vk', 'VKontakte'),
            ('facebook', 'Facebook'),
            ('twitter', 'Twitter'),
            ('whatsapp', 'WhatsApp'),
            ('instagram', 'Instagram'),
            ('tiktok', 'TikTok'),
            ('pinterest', 'Pinterest'),
            ('other', 'Другое'),
        ],
        default='other',
        verbose_name="Платформа"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Репост поста"
        verbose_name_plural = "Репосты постов"

    def __str__(self):
        return f"{self.user.username} поделился {self.post.title} в {self.platform}"


class ProjectShare(models.Model):
    """Модель репостов для проектов."""
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        verbose_name="Пользователь"
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="shares",
        verbose_name="Проект"
    )
    shared_url = models.URLField(
        blank=True,
        verbose_name="URL репоста",
        help_text="Ссылка на репост в социальной сети"
    )
    platform = models.CharField(
        max_length=50,
        choices=[
            ('telegram', 'Telegram'),
            ('vk', 'VKontakte'),
            ('facebook', 'Facebook'),
            ('twitter', 'Twitter'),
            ('whatsapp', 'WhatsApp'),
            ('instagram', 'Instagram'),
            ('tiktok', 'TikTok'),
            ('pinterest', 'Pinterest'),
            ('other', 'Другое'),
        ],
        default='other',
        verbose_name="Платформа"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Репост проекта"
        verbose_name_plural = "Репосты проектов"

    def __str__(self):
        return f"{self.user.username} поделился {self.project.title} в {self.platform}"


class PostView(models.Model):
    """Модель для отслеживания уникальных просмотров постов."""
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="unique_views",
        verbose_name="Пост"
    )
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Пользователь"
    )
    ip_address = models.GenericIPAddressField(verbose_name="IP адрес")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата просмотра")

    class Meta:
        verbose_name = "Просмотр поста"
        verbose_name_plural = "Просмотры постов"
        # Уникальность: один просмотр в день для пользователя или IP
        indexes = [
            models.Index(fields=['post', 'user', 'created_at']),
            models.Index(fields=['post', 'ip_address', 'created_at']),
        ]

    def __str__(self):
        return f"Просмотр {self.post.title} от {self.user or self.ip_address}"


class ProjectView(models.Model):
    """Модель для отслеживания уникальных просмотров проектов."""
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="unique_views",
        verbose_name="Проект"
    )
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Пользователь"
    )
    ip_address = models.GenericIPAddressField(verbose_name="IP адрес")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата просмотра")

    class Meta:
        verbose_name = "Просмотр проекта"
        verbose_name_plural = "Просмотры проектов"
        indexes = [
            models.Index(fields=['project', 'user', 'created_at']),
            models.Index(fields=['project', 'ip_address', 'created_at']),
        ]

    def __str__(self):
        return f"Просмотр {self.project.title} от {self.user or self.ip_address}"