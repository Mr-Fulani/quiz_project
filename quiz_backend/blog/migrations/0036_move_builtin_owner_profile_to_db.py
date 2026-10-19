"""
Профиль владельца и ресурсы, которые раньше были зашиты в blog/context_processors.py
для тенанта quiz-code, переносятся в «Данные владельца» (TenantInfo) и «Ресурсы платформы».
Существующие записи не трогаем: создаём только то, чего у тенанта ещё нет.
"""
from django.contrib.staticfiles import finders
from django.core.files import File
from django.db import migrations

TENANT_SLUG = 'quiz-code'

ABOUT_EN = [
    "I create high-load web applications, functional websites, powerful Telegram bots of any complexity, business cards and other digital solutions.",
    "I use microservice architecture, modular approach, modern databases and optimized APIs. This allows you to develop flexible, reliable and scalable projects that are easily adapted to any tasks.",
    "This blog is not only a business card, but also a useful resource for developers. Here I share: educational materials, guides and examples that will help you improve your programming skills.",
    "Whether it's process automation, integration with external services or creating a unique digital product - I will help bring your idea to life in a reliable and elegant solution.",
]
ABOUT_RU = [
    "Я создаю высоконагруженные веб-приложения, функциональные сайты, мощные Telegram-боты любой сложности, визитки и другие цифровые решения.",
    "Я использую микросервисную архитектуру, модульный подход, современные базы данных и оптимизированные API. Это позволяет разрабатывать гибкие, надежные и масштабируемые проекты, легко адаптируемые под любые задачи.",
    "Этот блог — не только визитка, но и полезный ресурс для разработчиков. Здесь я делюсь: учебными материалами, руководствами и примерами, которые помогут улучшить ваши навыки программирования.",
    "Будь то автоматизация процессов, интеграция с внешними сервисами или создание уникального цифрового продукта — я помогу воплотить вашу идею в надежное и элегантное решение.",
]
HOME_EN = [
    "Welcome to QuizHub - your resource for programming and quizzes. Here you will find the latest news, detailed guides and practical tips covering everything from Python to React.",
    "On our site you can learn new technologies, take exciting interactive quizzes and track your progress with detailed statistics.",
    "We strive to make learning programming accessible, interesting and effective for everyone, whether you are a beginner or a professional.",
    "Start your learning right now - dive into the world of code, take quizzes, improve your skills and track your growth.",
]
HOME_RU = [
    "Добро пожаловать в QuizHub — ваш ресурс для программирования и квизов. Здесь вы найдете последние новости, подробные руководства и практические советы, охватывающие все — от Python до React.",
    "На нашем сайте вы можете изучать новые технологии, проходить увлекательные интерактивные квизы и отслеживать свой прогресс с помощью подробной статистики.",
    "Мы стремимся сделать изучение программирования доступным, интересным и эффективным для всех, будь вы новичок или профессионал.",
    "Начните обучение прямо сейчас — погрузитесь в мир кода, проходите квизы, улучшайте свои навыки и отслеживайте свой рост.",
]

OWNER = {
    'name_ru': 'Anvar Sh.',
    'name_en': 'Anvar Sh.',
    'title_ru': 'Web Developer',
    'title_en': 'Web Developer',
    'email': 'fulani.dev@gmail.com',
    'phone': '+90 (552) 582-1497',
    'birthday_ru': 'October 1, 1986',
    'birthday_en': 'October 1, 1986',
    'location_ru': 'Istanbul, Turkey',
    'location_en': 'Istanbul, Turkey',
    'bio_ru': '\n\n'.join(ABOUT_RU),
    'bio_en': '\n\n'.join(ABOUT_EN),
    'home_text_ru': '\n\n'.join(HOME_RU),
    'home_text_en': '\n\n'.join(HOME_EN),
    'facebook': 'https://www.facebook.com/Mr.Fulani.Developer/',
    'telegram': 'https://t.me/Mr_Fulani',
    'whatsapp': 'https://wa.me/905525821497',
    'instagram': 'https://www.instagram.com/fulani_developer',
    'github': 'https://github.com/Mr-Fulani',
    'linkedin': 'https://www.linkedin.com/in/mr-fulani/',
    'youtube': 'https://www.youtube.com/@Mr_Fulani',
}
OWNER_AVATAR = 'blog/images/avatar/my-avatar.webp'

# (title_en, title_ru, description, url, иконка в static)
RESOURCES = [
    ('YouTube', 'YouTube', 'Educational videos', 'https://www.youtube.com/@Mr_Fulani', 'blog/images/icons/yt.svg'),
    ('Telegram', 'Telegram', 'Developer community', 'https://t.me/+Gh7xasVaKwdlMTY0', 'blog/images/icons/tg.svg'),
    ('VKontakte', 'VKontakte', 'Social updates', 'https://vk.com/development_hub', 'blog/images/icons/vk-logo.svg'),
    ('Yandex Zen', 'Яндекс Дзен', 'Articles', 'https://dzen.ru/id/692b2112399a32774d42939f', 'blog/images/icons/zen.svg'),
    ('Instagram', 'Instagram', 'Photos', 'https://www.instagram.com/fulani_developer', 'blog/images/icons/inst.svg'),
    ('TikTok', 'TikTok', 'Short clips', 'https://www.tiktok.com/@fulani_developer', 'blog/images/icons/tiktok.svg'),
]


def _attach_static(field_file, static_path):
    """Копирует файл из static в медиа-хранилище; без файла поле остаётся пустым."""
    source = finders.find(static_path)
    if not source:
        return
    with open(source, 'rb') as fh:
        field_file.save(static_path.rsplit('/', 1)[-1], File(fh), save=False)


def move_profile(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    TenantInfo = apps.get_model('blog', 'TenantInfo')
    PlatformResource = apps.get_model('blog', 'PlatformResource')

    tenant = Tenant.objects.filter(slug=TENANT_SLUG).first()
    if tenant is None:
        return

    if not TenantInfo.objects.filter(tenant=tenant).exists():
        info = TenantInfo(tenant=tenant, **OWNER)
        _attach_static(info.avatar, OWNER_AVATAR)
        info.save()

    if not PlatformResource.objects.filter(tenant=tenant, is_active=True).exists():
        for order, (title_en, title_ru, description, url, icon) in enumerate(RESOURCES):
            resource = PlatformResource(
                tenant=tenant, title_en=title_en, title_ru=title_ru,
                description_en=description, description_ru=description,
                url=url, order=order, is_active=True,
            )
            _attach_static(resource.icon_image, icon)
            resource.save()


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0035_tenantinfo_home_text'),
        ('tenants', '0004_fill_tenant_image_settings'),
    ]

    operations = [
        migrations.RunPython(move_profile, migrations.RunPython.noop),
    ]
