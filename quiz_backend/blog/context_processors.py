import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q, Case, When, IntegerField, Value
from django.urls import reverse
from django.utils.translation import get_language
from tasks.models import TaskStatistics

logger = logging.getLogger(__name__)
User = get_user_model()


def personal_info(request):
    """
    Контекстный процессор для предоставления данных личного кабинета и топа пользователей.
    """
    logger.info("=== DEBUG: personal_info processor called for request: %s", request.path)

    try:
        # Получаем топ пользователей (3 карточки по total_score)
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

        # Формируем данные
        top_users_data = []
        for i, user in enumerate(top_users, 1):
            try:
                favorite_topic = TaskStatistics.objects.filter(
                    user=user,
                    successful=True
                ).values('task__topic__name').annotate(count=Count('id')).order_by('-count').first()

                # Используем get_avatar_url из CustomUser
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
                    'favorite_category': favorite_topic['task__topic__name'] if favorite_topic else "Не определено"
                }
                top_users_data.append(user_data)
            except Exception as e:
                logger.error(f"Error processing user {user.username}: {e}")
                continue

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
                'telegram': 'tg://resolve?domain@Mr-Fulani',
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
                    'name': 'Яндекс Дзен'
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
                "Создаю высоконагруженные веб-приложения, функциональные сайты, мощные Telegram-боты любой сложности, сайты-визитки и другие цифровые решения.",
                "Использую микросервисную архитектуру, модульный подход, современные базы данных и оптимизированные API. Это позволяет разрабатывать гибкие, надежные и масштабируемые проекты, которые легко адаптируются под любые задачи.",
                "Этот блог – не только визитка, но и полезный ресурс для разработчиков. Здесь я делюсь: обучающими материалами, гайдами и примерами, которые помогут прокачать навыки в программировании.",
                "Будь то автоматизация процессов, интеграция с внешними сервисами или создание уникального цифрового продукта – я помогу воплотить вашу идею в надежное и элегантное решение."
            ],
            'home_text': [
                "Добро пожаловать на QuizHub – ваш ресурс для программирования и викторин. Здесь вы найдете последние новости, подробные руководства и практические советы, охватывающие всё от Python до React.",
                "На нашем сайте вы сможете изучать новые технологии, проходить увлекательные интерактивные викторины и отслеживать свой прогресс с подробной статистикой.",
                "Мы стремимся сделать обучение программированию доступным, интересным и эффективным для каждого, будь вы новичком или профессионалом.",
                "Начните своё обучение прямо сейчас – погрузитесь в мир кода, проходите викторины, совершенствуйте свои навыки и отслеживать свой рост."
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
    language = get_language() or 'ru'
    path = request.path
    base_url = f"http://{request.get_host()}"

    seo_data = {
        'meta_title': 'Quiz Project',
        'meta_description': 'Добро пожаловать в Quiz Project — блог и портфолио с квизами и проектами.',
        'meta_keywords': 'quiz, блог, портфолио, проекты, программирование',
        'canonical_url': base_url + reverse('blog:home'),
        'hreflang_url': base_url + reverse('blog:home'),
        'og_title': 'Quiz Project',
        'og_description': 'Добро пожаловать в Quiz Project — блог и портфолио с квизами и проектами.',
        'og_image': request.build_absolute_uri('/static/blog/images/default-og-image.jpg'),
        'og_url': base_url + reverse('blog:home'),
    }

    if path == reverse('blog:resume'):
        seo_data.update({
            'meta_title': 'Резюме — Quiz Project' if language == 'ru' else 'Resume — Quiz Project',
            'meta_description': 'Мое профессиональное резюме с опытом и навыками.' if language == 'ru' else 'My professional resume with experience and skills.',
            'meta_keywords': 'резюме, программист, портфолио' if language == 'ru' else 'resume, programmer, portfolio',
            'canonical_url': base_url + reverse('blog:resume'),
            'hreflang_url': base_url + reverse('blog:resume'),
            'og_title': seo_data['meta_title'],
            'og_description': seo_data['meta_description'],
            'og_url': base_url + reverse('blog:resume'),
        })
    elif path == reverse('blog:about'):
        seo_data.update({
            'meta_title': 'Обо мне — Quiz Project' if language == 'ru' else 'About Me — Quiz Project',
            'meta_description': 'Узнайте больше обо мне и моих проектах.' if language == 'ru' else 'Learn more about me and my projects.',
            'meta_keywords': 'обо мне, разработчик, программирование' if language == 'ru' else 'about me, developer, programming',
            'canonical_url': base_url + reverse('blog:about'),
            'hreflang_url': base_url + reverse('blog:about'),
            'og_title': seo_data['meta_title'],
            'og_description': seo_data['meta_description'],
            'og_url': base_url + reverse('blog:about'),
        })
    elif path == reverse('blog:contact'):
        seo_data.update({
            'meta_title': 'Контакты — Quiz Project' if language == 'ru' else 'Contact — Quiz Project',
            'meta_description': 'Свяжитесь со мной для сотрудничества или вопросов.' if language == 'ru' else 'Contact me for collaboration or questions.',
            'meta_keywords': 'контакты, программист, сотрудничество' if language == 'ru' else 'contact, programmer, collaboration',
            'canonical_url': base_url + reverse('blog:contact'),
            'hreflang_url': base_url + reverse('blog:contact'),
            'og_title': seo_data['meta_title'],
            'og_description': seo_data['meta_description'],
            'og_url': base_url + reverse('blog:contact'),
        })

    logger.info("=== DEBUG: seo_context data prepared: %s", seo_data.keys())
    return seo_data