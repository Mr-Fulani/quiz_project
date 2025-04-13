import logging

from django.db.models import Count, Avg, Sum, Q, Case, When, FloatField, IntegerField, F, Value
from tasks.models import TaskStatistics
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib import messages



logger = logging.getLogger(__name__)
User = get_user_model()



def personal_info(request):
    # Получаем топ пользователей (оставляем как есть — 5 карточек по total_score)
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
    ).order_by('-total_score')[:5]


    # Формируем данные
    top_users_data = []
    for i, user in enumerate(top_users, 1):
        try:
            favorite_topic = TaskStatistics.objects.filter(
                user=user,
                successful=True
            ).values('task__topic__name').annotate(count=Count('id')).order_by('-count').first()

            # Исправляем аватарку: загруженная или default_avatar.png
            avatar_url = user.profile.avatar.url if hasattr(user, 'profile') and user.profile and user.profile.avatar else '/static/blog/images/avatar/default_avatar.png'

            user_data = {
                'rank': i,
                'name': f"{user.first_name} {user.last_name}".strip() if user.first_name else user.username,
                'avatar': avatar_url,
                'quizzes_count': user.tasks_completed,
                'avg_score': 0,
                'total_score': (user.total_score or 0) * 100,
                'favorite_category': favorite_topic['task__topic__name'] if favorite_topic else "Не определено"
            }
            top_users_data.append(user_data)
            logger.info("=== DEBUG: Added user %s: %s", user.username, user_data)
        except Exception as e:
            logger.error("=== DEBUG: Error processing user %s: %s", user.username, str(e))
            continue



    return {
        'personal_info': {
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
    }




def unread_messages(request):
    if request.user.is_authenticated:
        return {
            'unread_messages_count': request.user.get_unread_messages_count()
        }
    return {'unread_messages_count': 0}

def unread_messages_count(request):
    if request.user.is_authenticated:
        count = messages.get_messages(request)._loaded_messages
        return {'unread_messages_count': len(list(count))}
    return {'unread_messages_count': 0}
