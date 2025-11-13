import json
import logging

from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q, Case, When, IntegerField, Value
from django.urls import reverse
from django.utils.translation import get_language, gettext as _
from tasks.models import TaskStatistics

from blog.models import MarqueeText

logger = logging.getLogger(__name__)
User = get_user_model()


def personal_info(request):
    """
    Контекстный процессор для предоставления данных личного кабинета.

    Отключает top_users_data для страниц квизов, чтобы минимизировать SQL-запросы.
    Логирует путь запроса и состояние top_users_data для отладки.

    Args:
        request: HTTP-запрос.

    Returns:
        dict: Контекст с данными личного кабинета.
    """
    logger.info("=== DEBUG: personal_info processor called for request: %s", request.path)

    try:
        # Проверяем, нужна ли top_users_data
        top_users_data = []
        path = request.path.lower()
        if not (path.startswith('/en/quiz/') or path.startswith('/ru/quiz/') or path.startswith('/en/quizes/') or path.startswith('/ru/quizes/')):
            logger.info("=== DEBUG: top_users_data enabled for path: %s", path)
            # Оптимизированный запрос с агрегацией статистики
            # Сначала сортируем по количеству решенных задач, потом по рейтингу
            top_users = User.objects.annotate(
                tasks_completed=Count('statistics', filter=Q(statistics__successful=True)),
                total_score=User.get_rating_annotation(),
                total_attempts=Count('statistics'),
                successful_attempts=Count('statistics', filter=Q(statistics__successful=True))
            ).filter(tasks_completed__gt=0).order_by('-tasks_completed', '-total_score')[:3]
            
            # Оптимизация: получаем все favorite_topics одним запросом для всех пользователей
            user_ids = [user.id for user in top_users]
            favorite_topics_data = {}
            if user_ids:
                favorite_topics_raw = TaskStatistics.objects.filter(
                    user_id__in=user_ids,
                    successful=True
                ).values('user_id', 'task__topic__name').annotate(
                    count=Count('id')
                ).order_by('user_id', '-count')
                
                # Группируем по user_id и берем первый (самый популярный)
                for item in favorite_topics_raw:
                    if item['user_id'] not in favorite_topics_data:
                        favorite_topics_data[item['user_id']] = item['task__topic__name']

            for i, user in enumerate(top_users, 1):
                try:
                    # Используем данные из модели пользователя, если они есть, иначе используем рассчитанные
                    if user.quizzes_completed > 0 and user.average_score > 0:
                        # Используем сохраненные данные
                        avg_score = user.average_score
                        quizzes_count = user.quizzes_completed
                        total_score = user.total_points
                        favorite_category = user.favorite_category or _("Not determined")
                    else:
                        # Используем рассчитанные значения из annotate
                        total_attempts = user.total_attempts or 0
                        successful_attempts = user.successful_attempts or 0
                        avg_score = round((successful_attempts / total_attempts * 100) if total_attempts > 0 else 0, 1)
                        quizzes_count = user.tasks_completed
                        total_score = (user.total_score or 0)
                        # Используем favorite_topic из предзагруженных данных
                        favorite_category = favorite_topics_data.get(user.id) or user.favorite_category or _("Not determined")

                    avatar_url = user.get_avatar_url
                    user_data = {
                        'rank': i,
                        'username': user.username,
                        'name': f"{user.first_name} {user.last_name}".strip() or user.username,
                        'display_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                        'avatar': avatar_url,
                        'quizzes_count': quizzes_count,
                        'avg_score': avg_score,
                        'total_score': total_score,
                        'total_score_formatted': f"{total_score} pts",
                        'favorite_category': favorite_category
                    }
                    top_users_data.append(user_data)
                    logger.info(f"=== DEBUG: User {user.username} stats - tasks: {user.tasks_completed}, score: {user.total_score}, avg: {avg_score}%")
                except Exception as e:
                    logger.error(f"Error processing user {user.username}: {e}")
                    continue
        else:
            logger.info("=== DEBUG: top_users_data disabled for path: %s", path)

        personal_info_data = {
            'name': 'Anvar Sh.',
            'title': 'Web Developer',
            'email': 'fulani.dev@gmail.com',
            'phone': '+90 (552) 582-1497',
            'birthday': 'October 1, 1986',
            'location': 'Istanbul, Turkey',
            'avatar': 'blog/images/avatar/my-avatar.png',
            'social_links': {
                'facebook': 'https://www.facebook.com/badr.commerce.3',
                'telegram': 'https://t.me/Mr_Fulani',
                'whatsapp': 'whatsapp://send?phone=05525821497',
                'instagram': 'https://www.instagram.com/fulani_developer',
            },
            'resources': {
                'youtube': {
                    'url': 'https://www.youtube.com/@Mr_Fulani',
                    'icon': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/09/YouTube_full-color_icon_%282017%29.svg/800px-YouTube_full-color_icon_%282017%29.svg.png',
                    'name': 'YouTube'
                },
                'telegram': {
                    'url': 'https://t.me/+Gh7xasVaKwdlMTY0',
                    'icon': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Telegram_2019_Logo.svg/512px-Telegram_2019_Logo.svg.png',
                    'name': 'Telegram'
                },
                'vk': {
                    'url': 'https://vk.com/development_hub',
                    'icon': 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/VK_Compact_Logo_%282021-present%29.svg/512px-VK_Compact_Logo_%282021-present%29.svg.png',
                    'name': 'VKontakte'
                },
                'dzen': {
                    'url': 'https://dzen.ru/yourpage',
                    'icon': 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Yandex_Zen_logo_icon.svg/512px-Yandex_Zen_logo_icon.svg.png',
                    'name': _('Yandex Zen')
                },
                'instagram': {
                    'url': 'https://www.instagram.com/fulani_developer',
                    'icon': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Instagram_logo_2022.svg/512px-Instagram_logo_2022.svg.png',
                    'name': 'Instagram'
                },
                'tiktok': {
                    'url': 'https://www.tiktok.com/@fulani_developer',
                    'icon': '/static/blog/images/icons/tiktok.svg',
                    'name': 'TikTok'
                }
            },
            'about_text': [
                _("I create high-load web applications, functional websites, powerful Telegram bots of any complexity, business cards and other digital solutions."),
                _("I use microservice architecture, modular approach, modern databases and optimized APIs. This allows you to develop flexible, reliable and scalable projects that are easily adapted to any tasks."),
                _("This blog is not only a business card, but also a useful resource for developers. Here I share: educational materials, guides and examples that will help you improve your programming skills."),
                _("Whether it's process automation, integration with external services or creating a unique digital product - I will help bring your idea to life in a reliable and elegant solution.")
            ],
            'home_text': [
                _("Welcome to QuizHub - your resource for programming and quizzes. Here you will find the latest news, detailed guides and practical tips covering everything from Python to React."),
                _("On our site you can learn new technologies, take exciting interactive quizzes and track your progress with detailed statistics."),
                _("We strive to make learning programming accessible, interesting and effective for everyone, whether you are a beginner or a professional."),
                _("Start your learning right now - dive into the world of code, take quizzes, improve your skills and track your growth.")
            ],
            'top_users': top_users_data
        }

        logger.info("=== DEBUG: personal_info data prepared: %s", personal_info_data.keys())
        return {'personal_info': personal_info_data}

    except Exception as e:
        logger.error("=== DEBUG: Error in personal_info processor: %s", str(e))
        return {'personal_info': {}}

def unread_messages_count(request):
    """
    Контекстный процессор для количества непрочитанных сообщений пользователя.
    Объединяет логику подсчета сообщений из БД и Django messages framework.
    """
    logger.info("=== DEBUG: unread_messages_count processor called for request: %s", request.path)
    if request.user.is_authenticated:
        # Сообщения из БД (модель Message)
        db_messages_count = request.user.get_unread_messages_count()
        
        # Сообщения из Django messages framework
        django_messages = messages.get_messages(request)
        django_messages_count = len(list(django_messages))
        
        total_count = db_messages_count + django_messages_count
        logger.info("=== DEBUG: DB messages: %d, Django messages: %d, Total: %d", 
                   db_messages_count, django_messages_count, total_count)
        return {'unread_messages_count': total_count}
    return {'unread_messages_count': 0}

def user_statistics(request):
    """
    Контекстный процессор для статистики пользователя с кэшированием.
    """
    if not request.user.is_authenticated:
        return {
            'user_statistics': {
                'solved_tasks': 0,
                'rating': 0,
                'total_attempts': 0
            }
        }
    
    try:
        # Кэшируем статистику на 5 минут для каждого пользователя
        from django.core.cache import cache
        cache_key = f'user_stats_{request.user.id}'
        stats = cache.get(cache_key)
        
        if stats is None:
            stats = request.user.get_statistics()
            cache.set(cache_key, stats, 300)  # 5 минут
            logger.info("=== DEBUG: User statistics cached for user %s: %s", request.user.username, stats)
        else:
            logger.info("=== DEBUG: User statistics from cache for user %s: %s", request.user.username, stats)
            
        return {'user_statistics': stats}
    except Exception as e:
        logger.error("=== DEBUG: Error in user_statistics processor: %s", str(e))
        return {
            'user_statistics': {
                'solved_tasks': 0,
                'rating': 0,
                'total_attempts': 0
            }
        }



def seo_context(request):
    """
    Контекстный процессор для предоставления SEO-тегов для статических страниц.
    Поддерживает многоязычность через request.LANGUAGE_CODE.
    """
    language = get_language() or 'en'
    path = request.path
    host = request.get_host()
    
    # ИСПРАВЛЕНИЕ: Используем HTTPS в продакшене
    scheme = 'https' if request.is_secure() else 'http'
    
    # ИСПРАВЛЕНИЕ: Для mini app всегда используем основной домен в canonical
    if host == 'mini.quiz-code.com':
        base_url = f"{scheme}://quiz-code.com"  # canonical на основной домен
        is_mini_app = True
    else:
        base_url = f"{scheme}://{host}"
        is_mini_app = False

    # Базовые SEO данные
    seo_data = {
        'meta_title': _('Quiz Python, Go, JavaScript, Java, C# | Programming Quizzes & Learning'),
        'meta_description': _('Master programming with interactive quizzes in Python, JavaScript, Go, Java, C#. Free coding challenges, tutorials, and skill assessment. Improve your developer skills with our comprehensive quiz platform.'),
        'meta_keywords': _('programming quiz, Python quiz, JavaScript quiz, Java quiz, C# quiz, Go quiz, coding challenges, programming learning, developer skills, interactive coding'),
        'canonical_url': base_url + reverse('blog:home'),
        'hreflang_url': base_url + reverse('blog:home'),
        'og_title': _('QuizHub - Interactive Programming Quizzes & Learning Platform'),
        'og_description': _('Master programming with interactive quizzes in Python, JavaScript, Go, Java, C#. Free coding challenges, tutorials, and skill assessment.'),
        'og_image': request.build_absolute_uri(getattr(settings, 'DEFAULT_OG_IMAGE', '/static/blog/images/default-og-image.jpeg')),
        'og_url': base_url + reverse('blog:home'),
        'og_site_name': 'QuizHub',
        'og_locale': 'en_US' if language == 'en' else 'ru_RU',
        'is_mini_app': is_mini_app,
        'robots_content': 'noindex, follow' if is_mini_app else 'index, follow',
        # Добавляем Twitter Card данные
        'twitter_card': 'summary_large_image',
        'twitter_site': '@quiz_code_hub',  # замените на ваш Twitter handle
        'twitter_creator': '@mr_fulani',   # замените на ваш Twitter handle
        'twitter_title': _('QuizHub - Interactive Programming Quizzes'),
        'twitter_description': _('Master programming with interactive quizzes in Python, JavaScript, Go, Java, C#.'),
        'twitter_image': request.build_absolute_uri(getattr(settings, 'DEFAULT_OG_IMAGE', '/static/blog/images/default-og-image.jpeg')),
        # Добавляем дополнительные мета теги
        'meta_author': 'Anvar Sh.',
        'meta_copyright': f'© {timezone.now().year} QuizHub. All rights reserved.',
        'meta_rating': 'general',
        'meta_distribution': 'global',
        'meta_revisit_after': '7 days',
        # Языковые альтернативы
        'hreflang_en': f"{base_url}/en/",
        'hreflang_ru': f"{base_url}/ru/",
        'hreflang_x_default': f"{base_url}/en/",
    }

    # Специфичные SEO данные для разных страниц
    if path == reverse('blog:resume'):
        seo_data.update({
            'meta_title': _('Anvar Sh. - Full Stack Web Developer Resume | Python, Django, React'),
            'meta_description': _('Experienced Full Stack Developer specializing in Python, Django, React, and modern web technologies. View my professional resume and portfolio.'),
            'meta_keywords': _('full stack developer, Python developer, Django developer, React developer, web developer resume, portfolio'),
            'canonical_url': base_url + reverse('blog:resume'),
            'hreflang_url': base_url + reverse('blog:resume'),
            'og_title': _('Anvar Sh. - Full Stack Web Developer Resume'),
            'og_description': _('Experienced Full Stack Developer specializing in Python, Django, React, and modern web technologies.'),
            'og_url': base_url + reverse('blog:resume'),
            'og_type': 'profile',
            'twitter_title': _('Anvar Sh. - Full Stack Developer Resume'),
            'twitter_description': _('Experienced developer specializing in Python, Django, React, and modern web technologies.'),
        })
    elif path == reverse('blog:about'):
        seo_data.update({
            'meta_title': _('About Anvar Sh. - Web Developer & Programming Instructor'),
            'meta_description': _('Learn about Anvar Sh., a passionate web developer and programming instructor creating educational content and powerful web applications.'),
            'meta_keywords': _('about developer, programming instructor, web developer story, coding mentor, educational content creator'),
            'canonical_url': base_url + reverse('blog:about'),
            'hreflang_url': base_url + reverse('blog:about'),
            'og_title': _('About Anvar Sh. - Web Developer & Programming Instructor'),
            'og_description': _('Learn about Anvar Sh., a passionate web developer and programming instructor.'),
            'og_url': base_url + reverse('blog:about'),
            'og_type': 'profile',
            'twitter_title': _('About Anvar Sh. - Web Developer'),
            'twitter_description': _('Passionate web developer and programming instructor creating educational content.'),
        })
    elif path == reverse('blog:contact'):
        seo_data.update({
            'meta_title': _('Contact Anvar Sh. - Web Development Services & Collaboration'),
            'meta_description': _('Get in touch for web development services, collaboration opportunities, or programming consultation. Available for freelance projects.'),
            'meta_keywords': _('contact developer, web development services, freelance developer, programming consultation, collaboration'),
            'canonical_url': base_url + reverse('blog:contact'),
            'hreflang_url': base_url + reverse('blog:contact'),
            'og_title': _('Contact Anvar Sh. - Web Development Services'),
            'og_description': _('Get in touch for web development services, collaboration opportunities, or programming consultation.'),
            'og_url': base_url + reverse('blog:contact'),
            'twitter_title': _('Contact Anvar Sh. - Web Development Services'),
            'twitter_description': _('Get in touch for web development services and collaboration opportunities.'),
        })

    # Добавляем структурированные данные JSON-LD
    
    website_data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "QuizHub",
        "alternateName": "Quiz Code Hub",
        "url": request.build_absolute_uri('/'),
        "description": seo_data['meta_description'],
        "inLanguage": ["en", "ru"],
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": request.build_absolute_uri('/?search={search_term_string}')
            },
            "query-input": "required name=search_term_string"
        },
        "author": {
            "@type": "Person",
            "name": "Anvar Sh.",
            "url": request.build_absolute_uri('/'),
            "sameAs": [
                "https://www.youtube.com/@Mr_Fulani",
                "https://t.me/Mr_Fulani",
                "https://www.instagram.com/fulani_developer"
            ]
        }
    }
    
    organization_data = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "QuizHub",
        "url": request.build_absolute_uri('/'),
        "logo": request.build_absolute_uri('/static/blog/images/logo.png'),
        "foundingDate": "2024",
        "description": seo_data['meta_description'],
        "contactPoint": {
            "@type": "ContactPoint",
            "telephone": "+90-552-582-1497",
            "contactType": "customer service",
            "availableLanguage": ["English", "Russian"]
        },
        "sameAs": [
            "https://www.youtube.com/@Mr_Fulani",
            "https://t.me/Mr_Fulani",
            "https://www.instagram.com/fulani_developer"
        ]
    }

    # Добавляем WebApplication schema для мини-приложения
    if is_mini_app:
        webapp_data = {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": "QuizHub Mini App",
            "description": "Interactive programming quizzes in Telegram Mini App",
            "url": f"{scheme}://mini.quiz-code.com",
            "applicationCategory": "EducationalApplication",
            "operatingSystem": "Web",
            "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "USD"
            }
        }
        seo_data['webapp_json_ld'] = json.dumps(webapp_data, ensure_ascii=False, indent=2)
    
    seo_data['website_json_ld'] = json.dumps(website_data, ensure_ascii=False, indent=2)
    seo_data['organization_json_ld'] = json.dumps(organization_data, ensure_ascii=False, indent=2)

    return seo_data



def marquee_text(request):
    return {
        'marquee_text': MarqueeText.objects.filter(is_active=True).first()
    }



def analytics_context(request):
    """
    Добавляет переменные аналитики и социальных сетей в контекст всех шаблонов
    """
    ga_id = settings.GOOGLE_ANALYTICS_PROPERTY_ID
    yandex_id = settings.YANDEX_METRICA_ID
    
    # Отладочное логирование
    logger.info(f"=== DEBUG: analytics_context - GOOGLE_ANALYTICS_PROPERTY_ID: '{ga_id}'")
    logger.info(f"=== DEBUG: analytics_context - YANDEX_METRICA_ID: '{yandex_id}'")
    
    # Проверяем переменные окружения напрямую
    import os
    env_ga_id = os.getenv('GOOGLE_ANALYTICS_ID', 'NOT_SET')
    logger.info(f"=== DEBUG: analytics_context - env GOOGLE_ANALYTICS_ID: '{env_ga_id}'")
    
    return {
        'GOOGLE_ANALYTICS_PROPERTY_ID': ga_id,
        'YANDEX_METRICA_ID': yandex_id,
        'twitter_username': getattr(settings, 'TWITTER_USERNAME', None),
    }


def page_meta_context(request):
    """
    Добавляет переменные времени публикации и изменения страниц в контекст.
    Автоматически определяет даты для постов и проектов на основе URL.
    """
    context = {}
    
    # Пытаемся определить тип объекта на основе URL
    path = request.path
    
    try:
        # Для постов блога
        if '/post/' in path or '/blog/' in path:
            from blog.models import Post
            # Извлекаем slug из URL
            slug = path.split('/')[-2] if path.endswith('/') else path.split('/')[-1]
            if slug and slug != 'blog':
                try:
                    post = Post.objects.get(slug=slug)
                    context['page_published_time'] = post.published_at or post.created_at
                    context['page_modified_time'] = post.updated_at
                except Post.DoesNotExist:
                    pass
        
        # Для проектов портфолио
        elif '/project/' in path or '/portfolio/' in path:
            from blog.models import Project
            # Извлекаем slug из URL
            slug = path.split('/')[-2] if path.endswith('/') else path.split('/')[-1]
            if slug and slug != 'portfolio':
                try:
                    project = Project.objects.get(slug=slug)
                    context['page_published_time'] = project.created_at
                    context['page_modified_time'] = project.updated_at
                except Project.DoesNotExist:
                    pass
    
    except Exception as e:
        logger.error(f"Error in page_meta_context for path {path}: {e}")
    
    return context


def dynamic_seo_context(request):
    """
    Динамический SEO контекст для постов и проектов.
    Генерирует оптимизированные SEO теги на основе контента.
    """
    seo_data = {}
    path = request.path
    host = request.get_host()

    # ДОБАВЛЕНО: Отладочная информация
    logger.info(f"=== DEBUG: dynamic_seo_context called for path: {path}, host: {host}")

    scheme = 'https' if request.is_secure() else 'http'

    # ИСПРАВЛЕНИЕ: Для mini app всегда используем основной домен в canonical
    if host == 'mini.quiz-code.com':
        base_url = f"{scheme}://quiz-code.com"  # canonical на основной домен
        is_mini_app = True
    else:
        base_url = f"{scheme}://{host}"
        is_mini_app = False

    # ДОБАВЛЕНО: Отладочная информация
    logger.info(f"=== DEBUG: base_url: {base_url}, is_mini_app: {is_mini_app}")

    try:
        # SEO для постов блога (включая share URL)
        if '/post/' in path or path.endswith('/post/') or '/share/post/' in path:
            from blog.models import Post
            from django.db import connection, transaction
            # Извлекаем slug из пути, учитывая share URL
            path_parts = [part for part in path.split('/') if part]
            if '/share/post/' in path:
                # Для /ru/share/post/krutoj-promt-dlya-gpt/ берем последнюю часть
                slug = path_parts[-1]
            else:
                # Для обычного /ru/post/krutoj-promt-dlya-gpt/ берем последнюю часть
                slug = path_parts[-1]
            
            # ДОБАВЛЕНО: Отладочная информация
            logger.info(f"=== DEBUG: Processing post with slug: {slug}")
            
            if slug:
                try:
                    # ДОБАВЛЕНО: Принудительно обновляем кеш базы данных и транзакцию
                    connection.close()
                    logger.info(f"=== DEBUG: Database connection closed and reopened")
                    
                    # ДОБАВЛЕНО: Проверяем все посты с этим slug в новой транзакции
                    with transaction.atomic():
                        all_posts_with_slug = Post.objects.filter(slug=slug)
                        logger.info(f"=== DEBUG: Found {all_posts_with_slug.count()} posts with slug '{slug}'")
                        
                        for post in all_posts_with_slug:
                            logger.info(f"=== DEBUG: Post ID: {post.id}, Title: '{post.title}', Published: {post.published}")
                        
                        # Теперь ищем только опубликованные
                        post = Post.objects.filter(slug=slug, published=True).select_related('category').prefetch_related('images').first()
                        
                        # ДОБАВЛЕНО: Отладочная информация
                        if post:
                            logger.info(f"=== DEBUG: Found published post: {post.title} (ID: {post.id})")
                        else:
                            logger.warning(f"=== DEBUG: No published post found for slug: {slug}")
                            # ДОБАВЛЕНО: Проверяем, есть ли вообще посты с этим slug
                            any_post = Post.objects.filter(slug=slug).first()
                            if any_post:
                                logger.warning(f"=== DEBUG: Post exists but not published: ID={any_post.id}, Title='{any_post.title}', Published={any_post.published}")
                            else:
                                logger.error(f"=== DEBUG: No post found at all for slug: {slug}")
                    
                    if post:
                        # Используем custom meta fields или генерируем автоматически
                        # Очищаем HTML теги из контента для корректного отображения в превью
                        clean_content = strip_tags(post.content) if post.content else ""
                        clean_excerpt = strip_tags(post.excerpt) if post.excerpt else ""
                        
                        meta_description = post.meta_description or (clean_excerpt[:160] if clean_excerpt else f"Read {post.title} - {clean_content[:100]}...")
                        meta_keywords = post.meta_keywords or f"{post.title}, {post.category.name}, blog, programming, quiz"

                        # ДОБАВЛЕНО: Отладочная информация для изображений
                        main_image = post.get_main_image()
                        logger.info(f"=== DEBUG: Main image: {main_image}")
                        if main_image:
                            logger.info(f"=== DEBUG: Main image photo: {main_image.photo}")
                            logger.info(f"=== DEBUG: Main image photo URL: {main_image.photo.url if main_image.photo else 'None'}")
                        else:
                            logger.info(f"=== DEBUG: No main image found")
                        
                        # ДОБАВЛЕНО: Проверяем все изображения поста
                        all_images = post.images.all()
                        logger.info(f"=== DEBUG: Total images for post: {all_images.count()}")
                        for i, img in enumerate(all_images):
                            logger.info(f"=== DEBUG: Image {i+1}: photo={img.photo}, gif={img.gif}, video={img.video}, is_main={img.is_main}")
                        
                        # ДОБАВЛЕНО: Используем метод get_og_image_url() из модели
                        og_image = post.get_og_image_url()
                        logger.info(f"=== DEBUG: OG image from get_og_image_url(): {og_image}")

                        # Формируем полный URL для OG изображения
                        if og_image:
                            # Если URL уже полный (начинается с http), используем как есть
                            if og_image.startswith('http'):
                                og_image_full_url = og_image
                            # Если относительный, формируем полный URL
                            elif og_image.startswith('/'):
                                og_image_full_url = f"{scheme}://{host}{og_image}"
                            else:
                                # Если путь без слеша, добавляем MEDIA_URL
                                og_image_full_url = f"{scheme}://{host}{og_image}"
                            
                            # Добавляем кэш-бюстинг
                            cache_buster = int(post.updated_at.timestamp())
                            if '?' in og_image_full_url:
                                og_image_final = f"{og_image_full_url}&v={cache_buster}"
                            else:
                                og_image_final = f"{og_image_full_url}?v={cache_buster}"
                        else:
                            # Если изображения нет, используем дефолтное
                            og_image_final = request.build_absolute_uri(getattr(settings, 'DEFAULT_OG_IMAGE', '/static/blog/images/default-og-image.jpeg'))
                        
                        logger.info(f"=== DEBUG: Final OG image URL: {og_image_final}")

                        seo_data.update({
                            'meta_title': f"{post.title} | Quiz Project Blog",
                            'meta_description': meta_description[:160],
                            'meta_keywords': meta_keywords,
                            'canonical_url': base_url + post.get_absolute_url(),
                            'og_title': post.title,
                            'og_description': meta_description[:160],
                            'og_image': og_image_final,
                            'og_url': base_url + post.get_absolute_url(),
                            'og_type': 'article',
                            'article_author': 'Anvar Sh.',
                            'article_published_time': (post.published_at or post.created_at).isoformat(),
                            'article_modified_time': post.updated_at.isoformat(),
                            'article_section': post.category.name,
                            'article_tag': meta_keywords.split(', ') if meta_keywords else [post.category.name],
                            'is_mini_app': is_mini_app,  # ДОБАВЛЕНО: флаг для mini app
                            'robots_content': 'noindex, follow' if is_mini_app else 'index, follow',  # ДОБАВЛЕНО: robots для mini app
                            # VK Meta Tags
                            'vk_title': post.title,
                            'vk_description': meta_description[:160],
                            'vk_image': og_image_final,
                            # Twitter Card Tags
                            'twitter_title': post.title,
                            'twitter_description': meta_description[:160],
                            'twitter_image': og_image_final,
                        })

                        # ДОБАВЛЕНО: Отладочная информация
                        logger.info(f"=== DEBUG: SEO data updated for post: {post.title}")
                        logger.info(f"=== DEBUG: vk_title: {post.title}")
                        logger.info(f"=== DEBUG: vk_description: {meta_description[:160]}")
                        logger.info(f"=== DEBUG: vk_image: {og_image_final}")

                        # JSON-LD для статьи
                        article_data = {
                            "@context": "https://schema.org",
                            "@type": "Article",
                            "headline": post.title,
                            "description": meta_description[:160],
                            "image": og_image_final,
                            "url": base_url + post.get_absolute_url(),
                            "author": {
                                "@type": "Person",
                                "name": "Anvar Sh."
                            },
                            "publisher": {
                                "@type": "Organization",
                                "name": "Quiz Project",
                                "logo": {
                                    "@type": "ImageObject",
                                    "url": request.build_absolute_uri('/static/blog/images/logo.png')
                                }
                            },
                            "datePublished": (post.published_at or post.created_at).isoformat(),
                            "dateModified": post.updated_at.isoformat(),
                            "mainEntityOfPage": {
                                "@type": "WebPage",
                                "@id": base_url + post.get_absolute_url()
                            }
                        }

                        seo_data['article_json_ld'] = json.dumps(article_data, ensure_ascii=False, indent=2)
                        
                except Exception as e:
                    logger.error(f"Error processing post SEO for {slug}: {e}")
                    import traceback
                    logger.error(f"=== DEBUG: Full traceback: {traceback.format_exc()}")
        
        # SEO для проектов портфолио
        elif '/project/' in path:
            from blog.models import Project
            slug = path.split('/')[-2] if path.endswith('/') else path.split('/')[-1]
            
            # ДОБАВЛЕНО: Отладочная информация
            logger.info(f"=== DEBUG: Processing project with slug: {slug}")
            
            if slug:
                try:
                    project = Project.objects.filter(slug=slug).select_related('category').prefetch_related('images').first()
                    
                    # ДОБАВЛЕНО: Отладочная информация
                    if project:
                        logger.info(f"=== DEBUG: Found project: {project.title}")
                    else:
                        logger.warning(f"=== DEBUG: Project not found for slug: {slug}")
                    
                    if project:
                        # Очищаем HTML теги из описания для корректного отображения в превью
                        clean_description = strip_tags(project.description) if project.description else ""
                        
                        meta_description = project.meta_description or f"{project.title} - {clean_description[:100]}..."
                        meta_keywords = project.meta_keywords or f"{project.title}, {project.technologies}, portfolio, project, web development"

                        main_image = project.get_main_image()
                        if main_image and main_image.photo:
                            try:
                                og_image = main_image.photo.url
                            except (AttributeError, ValueError):
                                og_image = getattr(settings, 'DEFAULT_OG_IMAGE', '/static/blog/images/default-og-image.jpeg')
                        else:
                            og_image = getattr(settings, 'DEFAULT_OG_IMAGE', '/static/blog/images/default-og-image.jpeg')

                        # Добавляем версию к изображению для кэширования
                        if og_image and not og_image.startswith('http'):
                            # Для относительных URL добавляем версию
                            og_image_with_version = f"{og_image}?v={int(project.updated_at.timestamp())}"
                        else:
                            og_image_with_version = og_image

                        # ДОБАВЛЕНО: Отладочная информация для VK
                        vk_image_url = f"{getattr(settings, 'PUBLIC_URL', 'https://quiz-code.com')}{og_image_with_version}" if og_image_with_version.startswith('/') else og_image_with_version
                        logger.info(f"=== DEBUG: VK image URL: {vk_image_url}")

                        seo_data.update({
                            'meta_title': f"{project.title} | Portfolio - Quiz Project",
                            'meta_description': meta_description[:160],
                            'meta_keywords': meta_keywords,
                            'canonical_url': base_url + project.get_absolute_url(),
                            'og_title': project.title,
                            'og_description': meta_description[:160],
                            'og_image': request.build_absolute_uri(og_image_with_version),
                            'og_url': base_url + project.get_absolute_url(),
                            'og_type': 'website',
                            'is_mini_app': is_mini_app,  # ДОБАВЛЕНО: флаг для mini app
                            'robots_content': 'noindex, follow' if is_mini_app else 'index, follow',  # ДОБАВЛЕНО: robots для mini app
                            # VK Meta Tags
                            'vk_title': project.title,
                            'vk_description': meta_description[:160],
                            'vk_image': vk_image_url,
                            # Twitter Card Tags
                            'twitter_title': project.title,
                            'twitter_description': meta_description[:160],
                            'twitter_image': request.build_absolute_uri(og_image_with_version),
                        })

                        # ДОБАВЛЕНО: Отладочная информация
                        logger.info(f"=== DEBUG: SEO data updated for project: {project.title}")

                        # JSON-LD для проекта
                        project_data = {
                            "@context": "https://schema.org",
                            "@type": "CreativeWork",
                            "name": project.title,
                            "description": meta_description[:160],
                            "image": request.build_absolute_uri(og_image),
                            "url": base_url + project.get_absolute_url(),
                            "author": {
                                "@type": "Person",
                                "name": "Anvar Sh."
                            },
                            "dateCreated": project.created_at.isoformat(),
                            "dateModified": project.updated_at.isoformat(),
                            "mainEntityOfPage": {
                                "@type": "WebPage",
                                "@id": base_url + project.get_absolute_url()
                            }
                        }

                        seo_data['project_json_ld'] = json.dumps(project_data, ensure_ascii=False, indent=2)

                except Exception as e:
                    logger.error(f"Error processing project SEO for {slug}: {e}")
        else:
            # ДОБАВЛЕНО: Отладочная информация
            logger.info(f"=== DEBUG: Path {path} does not match post or project patterns")

    except Exception as e:
        logger.error(f"Error in dynamic_seo_context: {e}")
        import traceback
        logger.error(f"=== DEBUG: Full traceback: {traceback.format_exc()}")

    # ДОБАВЛЕНО: Отладочная информация
    logger.info(f"=== DEBUG: Final SEO data keys: {list(seo_data.keys())}")

    return {'dynamic_seo': seo_data}

"""
Контекстные процессоры для приложения blog.
"""

from django.conf import settings


def telegram_settings(request):
    """
    Добавляет настройки Telegram в контекст всех шаблонов.
    """
    username = getattr(settings, 'TELEGRAM_BOT_USERNAME', '')
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    
    # Отладочная информация в консоли Django
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Telegram settings: username='{username}', token='{token[:10] if token else 'None'}...'")
    
    return {
        'TELEGRAM_BOT_USERNAME': username,
        'TELEGRAM_BOT_TOKEN': token,
    }