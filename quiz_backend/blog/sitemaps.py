from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.conf import settings
from django.utils import translation
from .models import Post, Project

class I18nSitemap(Sitemap):
    """
    Базовый класс для мультиязычных карт сайта.
    """
    def get_urls(self, page=1, site=None, protocol=None):
        # Получаем стандартные URL
        urls = super().get_urls(page, site, protocol)
        
        # Добавляем hreflang к каждому URL
        for url in urls:
            item = url['item']
            # Получаем URL для всех языков
            hreflangs = []
            for lang_code, _ in settings.LANGUAGES:
                with translation.override(lang_code):
                    try:
                        # Используем location из дочернего класса
                        location = self.location(item)
                        hreflangs.append({'lang': lang_code, 'location': location})
                    except Exception:
                        # Если для какого-то языка нет URL, пропускаем
                        continue
            url['alternates'] = hreflangs
            
        return urls

class PostSitemap(I18nSitemap):
    """
    Карта сайта для постов блога с поддержкой hreflang.
    """
    changefreq = "weekly"
    priority = 0.8
    protocol = 'https'

    def items(self):
        return Post.objects.filter(published=True).order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('blog:post_detail', kwargs={'slug': obj.slug})

class ProjectSitemap(I18nSitemap):
    """
    Карта сайта для проектов портфолио с поддержкой hreflang.
    """
    changefreq = "monthly"
    priority = 0.7
    protocol = 'https'

    def items(self):
        return Project.objects.all().order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('blog:project_detail', kwargs={'slug': obj.slug})

class MainPagesSitemap(I18nSitemap):
    """
    Карта сайта для основных страниц с поддержкой hreflang.
    """
    protocol = 'https'

    def items(self):
        return [
            {'name': 'home', 'priority': 1.0, 'changefreq': 'daily'},
            {'name': 'blog', 'priority': 0.9, 'changefreq': 'daily'},
            {'name': 'quizes', 'priority': 0.95, 'changefreq': 'daily'},
            {'name': 'portfolio', 'priority': 0.8, 'changefreq': 'weekly'},
            {'name': 'resume', 'priority': 0.6, 'changefreq': 'monthly'},
            {'name': 'about', 'priority': 0.6, 'changefreq': 'monthly'},
            {'name': 'contact', 'priority': 0.6, 'changefreq': 'monthly'},
        ]

    def location(self, item):
        return reverse(f'blog:{item["name"]}')

    def priority(self, item):
        return item['priority']
    
    def changefreq(self, item):
        return item['changefreq']

class QuizSitemap(I18nSitemap):
    """
    Карта сайта для квизов с поддержкой hreflang.
    """
    changefreq = "weekly"
    priority = 0.9
    protocol = 'https'

    def items(self):
        try:
            from topics.models import Topic
            return Topic.objects.filter(tasks__published=True).distinct().order_by('name')
        except ImportError:
            return []

    def lastmod(self, obj):
        return obj.updated_at if hasattr(obj, 'updated_at') else None

    def location(self, obj):
        return reverse('blog:quiz_detail', kwargs={'quiz_type': obj.name})

class ImageSitemap(Sitemap):
    """
    Карта сайта для изображений постов и проектов.
    Помогает Google индексировать изображения.
    """
    changefreq = "weekly"
    priority = 0.5
    protocol = 'https'

    def items(self):
        images = []
        
        # Изображения из постов
        posts_with_images = Post.objects.filter(
            published=True,
            images__isnull=False
        ).prefetch_related('images')
        
        for post in posts_with_images:
            for image in post.images.all():
                if image.photo:
                    images.append({
                        'type': 'post',
                        'object': post,
                        'image': image,
                        'url': reverse('blog:post_detail', kwargs={'slug': post.slug})
                    })
        
        # Изображения из проектов
        projects_with_images = Project.objects.filter(
            images__isnull=False
        ).prefetch_related('images')
        
        for project in projects_with_images:
            for image in project.images.all():
                if image.photo:
                    images.append({
                        'type': 'project',
                        'object': project,
                        'image': image,
                        'url': reverse('blog:project_detail', kwargs={'slug': project.slug})
                    })
        
        return images

    def location(self, item):
        return item['url']

    def lastmod(self, item):
        return item['object'].updated_at

    # Добавляем метод для извлечения URL изображений
    def _urls(self, page, protocol, domain):
        urls = []
        # Получаем сайт из настроек, чтобы строить полные URL
        latest_lastmod = None
        all_items_lastmod = True  # флаг для проверки
        
        # Получаем полные URL для изображений
        for item in self.paginator.page(page).object_list:
            loc = f"{protocol}://{domain}{self.location(item)}"
            priority = self.priority
            lastmod = self.lastmod(item)

            if all_items_lastmod:
                if lastmod is not None:
                    if latest_lastmod is None:
                        latest_lastmod = lastmod
                    else:
                        latest_lastmod = max(latest_lastmod, lastmod)
                else:
                    all_items_lastmod = False
            
            # Собираем данные для <image:image>
            image_data = {
                'loc': item['image'].photo.url,
                'title': item['object'].title,
                'caption': item['image'].alt_text or item['object'].title,
            }
            
            # Создаем XML-структуру
            url_info = {
                'item': item,
                'location': loc,
                'lastmod': lastmod,
                'changefreq': self.changefreq,
                'priority': f'{priority:.1f}',
                'images': [image_data]  # Список изображений для одной страницы
            }
            urls.append(url_info)
            
        return urls