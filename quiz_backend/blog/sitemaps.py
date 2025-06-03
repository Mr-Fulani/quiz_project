from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Post, Project

class PostSitemap(Sitemap):
    """
    Карта сайта для постов блога.
    Включает все опубликованные посты с частотой обновления "weekly" и приоритетом 0.8.
    """
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Post.objects.filter(published=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('blog:post_detail', kwargs={'slug': obj.slug})

class ProjectSitemap(Sitemap):
    """
    Карта сайта для проектов портфолио.
    Включает все проекты с частотой обновления "monthly" и приоритетом 0.7.
    """
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Project.objects.all()

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('blog:project_detail', kwargs={'slug': obj.slug})

class StaticSitemap(Sitemap):
    """
    Карта сайта для статических страниц.
    Включает страницы "Резюме", "Обо мне" и "Контакты" с частотой обновления "monthly" и приоритетом 0.6.
    """
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return ['resume', 'about', 'contact']

    def location(self, item):
        return reverse(f'blog:{item}')