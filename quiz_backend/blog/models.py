# blog/models.py
from django.db import models
from django.utils.text import slugify
from accounts.models import CustomUser
from django.contrib.auth import get_user_model

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
    content = models.TextField(verbose_name="Содержимое поста")
    excerpt = models.TextField(blank=True, verbose_name="Краткое описание")
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

    class Meta:
        verbose_name = "Пост"
        verbose_name_plural = "Посты"
        ordering = ["-created_at"]

    def __str__(self):
        """Возвращает строковое представление поста."""
        return self.title

    def save(self, *args, **kwargs):
        """Сохраняет пост, автоматически генерируя слаг, если он не указан."""
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_main_image(self):
        """Возвращает главное изображение поста или первое доступное."""
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
        """Сохраняет медиафайл, обеспечивая уникальность главной миниатюры."""
        if self.is_main:
            # Сбрасываем is_main для всех остальных медиа этого поста
            PostImage.objects.filter(post=self.post).exclude(id=self.id).update(is_main=False)
        else:
            # Если главный не выбран, делаем текущий главным, если других нет
            if not PostImage.objects.filter(post=self.post, is_main=True).exists():
                self.is_main = True
        super().save(*args, **kwargs)


class Project(models.Model):
    """Модель проекта портфолио."""
    title = models.CharField(max_length=200, verbose_name="Название проекта")
    slug = models.SlugField(unique=True, verbose_name="Слаг проекта")
    description = models.TextField(verbose_name="Описание проекта")
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

    class Meta:
        verbose_name = "Проект"
        verbose_name_plural = "Проекты"
        ordering = ["-created_at"]

    def __str__(self):
        """Возвращает строковое представление проекта."""
        return self.title

    def save(self, *args, **kwargs):
        """Сохраняет проект, автоматически генерируя слаг, если он не указан."""
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_main_image(self):
        """Возвращает главное изображение проекта или первое доступное."""
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
        """Сохраняет медиафайл, обеспечивая уникальность главной миниатюры."""
        if self.is_main:
            # Сбрасываем is_main для всех остальных медиа этого проекта
            ProjectImage.objects.filter(project=self.project).exclude(id=self.id).update(is_main=False)
        else:
            # Если главный не выбран, делаем текущий главным, если других нет
            if not ProjectImage.objects.filter(project=self.project, is_main=True).exists():
                self.is_main = True
        super().save(*args, **kwargs)


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

    def __str__(self):
        """Возвращает строковое представление вложения."""
        return f"Attachment {self.filename} for message {self.message.id}"


class Message(models.Model):
    """Модель сообщений между пользователями."""
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        verbose_name="Отправитель"
    )
    recipient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="received_messages",
        verbose_name="Получатель"
    )
    content = models.TextField(verbose_name="Содержимое сообщения")
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
        return f"Message from {self.sender} to {self.recipient}"

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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='testimonials')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)  # Для модерации отзывов

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Отзыв от {self.user.username}'