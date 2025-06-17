import logging

from django.conf import settings
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
            top_users = User.objects.annotate(
                tasks_completed=Count('statistics', filter=Q(statistics__successful=True)),
                total_score=Sum(
                    Case(
                        When(statistics__successful=True, then=Case(
                            When(statistics__task__difficulty='easy', then=Value(1)),
                            When(statistics__task__difficulty='medium', then=Value(2)),
                            When(statistics__task__difficulty='hard', then=Value(3)),
                            default=Value(1),
                            output_field=IntegerField(),
                        )),
                        default=0,
                        output_field=IntegerField(),
                    )
                )
            ).order_by('-total_score')[:3]

            for i, user in enumerate(top_users, 1):
                try:
                    favorite_topic = TaskStatistics.objects.filter(
                        user=user,
                        successful=True
                    ).values('task__topic__name').annotate(count=Count('id')).order_by('-count').first()

                    avatar_url = user.get_avatar_url
                    user_data = {
                        'rank': i,
                        'username': user.username,
                        'name': f"{user.first_name} {user.last_name}".strip() or user.username,
                        'display_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                        'avatar': avatar_url,
                        'quizzes_count': user.tasks_completed,
                        'avg_score': 0,
                        'total_score': (user.total_score or 0) * 100,
                        'favorite_category': favorite_topic['task__topic__name'] if favorite_topic else _("Not determined")
                    }
                    top_users_data.append(user_data)
                except Exception as e:
                    logger.error(f"Error processing user {user.username}: {e}")
                    continue
        else:
            logger.info("=== DEBUG: top_users_data disabled for path: %s", path)

        personal_info_data = {
            'name': 'Anvar Sh.',
            'title': 'Web Developer',
            'email': 'anvar.sharipov.1986@gmail.com',
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

def unread_messages(request):
    """
    Контекстный процессор для количества непрочитанных сообщений пользователя.
    """
    logger.info("=== DEBUG: unread_messages processor called for request: %s", request.path)
    if request.user.is_authenticated:
        count = request.user.get_unread_messages_count()
        logger.info("=== DEBUG: unread_messages count: %d", count)
        return {'unread_messages_count': count}
    return {'unread_messages_count': 0}

def unread_messages_count(request):
    """
    Контекстный процессор для количества непрочитанных сообщений из Django messages framework.
    """
    logger.info("=== DEBUG: unread_messages_count processor called for request: %s", request.path)
    if request.user.is_authenticated:
        count = messages.get_messages(request)._loaded_messages
        logger.info("=== DEBUG: unread_messages_count from messages framework: %d", len(list(count)))
        return {'unread_messages_count': len(list(count))}
    return {'unread_messages_count': 0}



def seo_context(request):
    """
    Контекстный процессор для предоставления SEO-тегов для статических страниц.
    Поддерживает многоязычность через request.LANGUAGE_CODE.
    """
    logger.info("=== DEBUG: seo_context processor called for request: %s", request.path)
    language = get_language() or 'en'
    path = request.path
    base_url = f"http://{request.get_host()}"

    seo_data = {
        'meta_title': _('Quiz Python, Go, JavaScript, Java, C#'),
        'meta_description': _('Welcome to Quiz Project — blog and portfolio with quizzes and projects.'),
        'meta_keywords': _('quiz, blog, portfolio, projects, programming'),
        'canonical_url': base_url + reverse('blog:home'),
        'hreflang_url': base_url + reverse('blog:home'),
        'og_title': _('Quiz Project'),
        'og_description': _('Welcome to Quiz Project — blog and portfolio with quizzes and projects.'),
        'og_image': request.build_absolute_uri('/static/blog/images/default-og-image.jpg'),
        'og_url': base_url + reverse('blog:home'),
    }

    if path == reverse('blog:resume'):
        seo_data.update({
            'meta_title': _('Resume — web developer'),
            'meta_description': _('My professional resume with experience and skills.'),
            'meta_keywords': _('resume, programmer, portfolio'),
            'canonical_url': base_url + reverse('blog:resume'),
            'hreflang_url': base_url + reverse('blog:resume'),
            'og_title': seo_data['meta_title'],
            'og_description': seo_data['meta_description'],
            'og_url': base_url + reverse('blog:resume'),
        })
    elif path == reverse('blog:about'):
        seo_data.update({
            'meta_title': _('About Me — web developer'),
            'meta_description': _('Learn more about me and my projects.'),
            'meta_keywords': _('about me, developer, programming'),
            'canonical_url': base_url + reverse('blog:about'),
            'hreflang_url': base_url + reverse('blog:about'),
            'og_title': seo_data['meta_title'],
            'og_description': seo_data['meta_description'],
            'og_url': base_url + reverse('blog:about'),
        })
    elif path == reverse('blog:contact'):
        seo_data.update({
            'meta_title': _('Contact — web developer'),
            'meta_description': _('Contact me for collaboration or questions.'),
            'meta_keywords': _('contact, programmer, collaboration'),
            'canonical_url': base_url + reverse('blog:contact'),
            'hreflang_url': base_url + reverse('blog:contact'),
            'og_title': seo_data['meta_title'],
            'og_description': seo_data['meta_description'],
            'og_url': base_url + reverse('blog:contact'),
        })

    logger.info("=== DEBUG: seo_context data prepared: %s", seo_data.keys())
    return seo_data



def marquee_text(request):
    return {
        'marquee_text': MarqueeText.objects.filter(is_active=True).first()
    }



def analytics_context(request):
    """
    Добавляет переменные аналитики в контекст всех шаблонов
    """
    return {
        'GOOGLE_ANALYTICS_PROPERTY_ID': settings.GOOGLE_ANALYTICS_PROPERTY_ID,
        'YANDEX_METRICA_ID': settings.YANDEX_METRICA_ID,
    }