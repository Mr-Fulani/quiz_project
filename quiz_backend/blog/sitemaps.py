from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.conf import settings
from django.utils import translation
from django.utils.html import format_html
from .models import Post, Project

class I18nSitemap(Sitemap):
    """
    Базовый класс для мультиязычных карт сайта с поддержкой hreflang.
    Генерирует полные URL для всех языковых версий страниц.
    """
    def get_urls(self, page=1, site=None, protocol=None):
        # Получаем стандартные URL
        urls = super().get_urls(page, site, protocol)
        
        # Определяем домен и протокол
        if site is None:
            from django.contrib.sites.models import Site
            site = Site.objects.get_current()
        
        if protocol is None:
            protocol = self.protocol or 'https'
        
        domain = site.domain
        
        # Добавляем hreflang к каждому URL
        for url in urls:
            item = url['item']
            # Получаем текущий location
            current_location = url.get('location', '')
            
            # Определяем язык текущего URL
            current_lang = None
            for lang_code, _ in settings.LANGUAGES:
                lang_prefix = lang_code[:2]
                if f"/{lang_prefix}/" in current_location:
                    current_lang = lang_prefix
                    break
            
            # Если язык не определен, используем язык по умолчанию
            if current_lang is None:
                current_lang = settings.LANGUAGE_CODE[:2]
            
            # Получаем базовый путь без языкового префикса
            base_path = current_location
            for lang_code, _ in settings.LANGUAGES:
                lang_prefix = lang_code[:2]
                if base_path.startswith(f"/{lang_prefix}/"):
                    base_path = base_path[len(f"/{lang_prefix}"):]
                    break
            
            # Получаем URL для всех языков
            hreflangs = []
            for lang_code, _ in settings.LANGUAGES:
                lang_prefix = lang_code[:2]
                with translation.override(lang_code):
                    try:
                        # Используем location из дочернего класса
                        location = self.location(item)
                        # Убираем языковой префикс если он есть
                        if location.startswith(f"/{lang_prefix}/"):
                            location = location[len(f"/{lang_prefix}"):]
                        # Создаем полный URL с правильным языковым префиксом
                        full_url = f"{protocol}://{domain}/{lang_prefix}{location}"
                        hreflangs.append({'lang': lang_prefix, 'location': full_url})
                    except Exception:
                        # Если для какого-то языка нет URL, пропускаем
                        continue
            
            # Убеждаемся, что текущий URL тоже в списке
            if current_location and not current_location.startswith('http'):
                current_full_url = f"{protocol}://{domain}{current_location}"
            else:
                current_full_url = current_location
            
            # Добавляем текущий URL в alternates если его там еще нет
            if not any(alt['lang'] == current_lang and alt['location'] == current_full_url for alt in hreflangs):
                hreflangs.append({'lang': current_lang, 'location': current_full_url})
            
            # Устраняем дубликаты и формируем структуру для шаблона
            ordered_alternates = {}
            for alt in hreflangs:
                lang = alt.get('lang')
                location = alt.get('location')
                if not lang or not location:
                    continue
                if lang not in ordered_alternates:
                    ordered_alternates[lang] = location

            # Добавляем x-default согласно рекомендациям Google
            default_lang = settings.LANGUAGE_CODE[:2]
            default_location = ordered_alternates.get(default_lang)
            if not default_location and ordered_alternates:
                default_location = next(iter(ordered_alternates.values()))
            if default_location:
                ordered_alternates.setdefault('x-default', default_location)

            alternates_list = [
                {'lang': lang_key, 'location': location}
                for lang_key, location in ordered_alternates.items()
            ]

            url['alternates'] = alternates_list
            url['alternate_links'] = [
                format_html(
                    '<xhtml:link rel="alternate" hreflang="{}" href="{}" />',
                    alt['lang'],
                    alt['location'],
                )
                for alt in alternates_list
            ]
 
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

class ImageSitemap(I18nSitemap):
    """
    Карта сайта для изображений постов и проектов.
    Помогает Google индексировать изображения.
    Наследуется от I18nSitemap для поддержки hreflang тегов.
    """
    changefreq = "weekly"
    priority = 0.5
    protocol = 'https'

    def items(self):
        """
        Возвращает список страниц с изображениями, группируя изображения по страницам.
        Это предотвращает дублирование URL в sitemap.
        """
        pages_with_images = {}
        
        # Изображения из постов
        posts_with_images = Post.objects.filter(
            published=True,
            images__isnull=False
        ).prefetch_related('images')
        
        for post in posts_with_images:
            post_url = reverse('blog:post_detail', kwargs={'slug': post.slug})
            if post_url not in pages_with_images:
                pages_with_images[post_url] = {
                    'type': 'post',
                    'object': post,
                    'images': []
                }
            
            for image in post.images.all():
                if image.photo:
                    pages_with_images[post_url]['images'].append(image)
        
        # Изображения из проектов
        projects_with_images = Project.objects.filter(
            images__isnull=False
        ).prefetch_related('images')
        
        for project in projects_with_images:
            project_url = reverse('blog:project_detail', kwargs={'slug': project.slug})
            if project_url not in pages_with_images:
                pages_with_images[project_url] = {
                    'type': 'project',
                    'object': project,
                    'images': []
                }
            
            for image in project.images.all():
                if image.photo:
                    pages_with_images[project_url]['images'].append(image)
        
        # Преобразуем в список
        return [{'url': url, **data} for url, data in pages_with_images.items()]

    def location(self, item):
        return item['url']

    def lastmod(self, item):
        return item['object'].updated_at
    
    def get_urls(self, page=1, site=None, protocol=None):
        """
        Переопределяем get_urls для правильной обработки изображений и hreflang тегов.
        Сначала получаем URL с hreflang из родительского класса I18nSitemap,
        затем добавляем информацию об изображениях.
        """
        # Получаем URL с hreflang тегами из родительского класса
        urls = super().get_urls(page=page, site=site, protocol=protocol)
        
        if site is None:
            from django.contrib.sites.models import Site
            site = Site.objects.get_current()
        
        if protocol is None:
            protocol = self.protocol or 'https'
        
        domain = site.domain
        
        # Добавляем информацию об изображениях к каждому URL
        for url_info in urls:
            item = url_info.get('item', {})
            
            # Получаем объект (post или project) из item
            obj = item.get('object') if isinstance(item, dict) else None
            
            if obj:
                # Собираем данные для всех изображений страницы
                images_data = []
                images_list = item.get('images', [])
                
                for image in images_list:
                    if image and hasattr(image, 'photo') and image.photo:
                        try:
                            photo_url = image.photo.url
                            images_data.append({
                                'loc': photo_url if photo_url.startswith('http') else f"{protocol}://{domain}{photo_url}",
                                'title': obj.title if hasattr(obj, 'title') else '',
                                'caption': (image.alt_text if hasattr(image, 'alt_text') and image.alt_text else 
                                          (obj.title if hasattr(obj, 'title') else '')),
                            })
                        except (AttributeError, ValueError):
                            # Пропускаем изображение, если не удалось получить URL
                            continue
                
                # Добавляем изображения к URL информации
                if images_data:
                    url_info['images'] = images_data
        
        return urls