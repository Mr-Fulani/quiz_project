# blog/models.py
import os

from PIL import Image, ImageOps
from django.db import models
from django.utils.text import slugify
from accounts.models import CustomUser
from django.contrib.auth import get_user_model
from tinymce.models import HTMLField
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit

User = get_user_model()


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


class Post(models.Model):
    """Модель поста блога."""
    title = models.CharField(max_length=200, verbose_name="Заголовок поста")
    slug = models.SlugField(unique=True, verbose_name="Слаг поста")
    content = HTMLField(verbose_name="Содержимое поста")  # Заменяем TextField на HTMLField
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
    