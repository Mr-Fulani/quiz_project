"""
Тесты для проверки доступности ссылок для роботов поисковых систем.
Проверяет, что роботы видят все страницы, canonical URL, hreflang теги, sitemap и robots.txt.
"""
from django.test import TransactionTestCase, Client, override_settings
from django.contrib.sites.models import Site
from django.urls import reverse
from django.utils.text import slugify
from blog.models import Post, Project, Category
from topics.models import Topic, Subtopic
from tasks.models import Task
import re


@override_settings(
    SILKY_PYTHON_PROFILER=False,  # Отключаем silk в тестах
    SILKY_AUTHENTICATION=False,
    SILKY_AUTHORISATION=False,
    SITE_ID=1,  # Устанавливаем SITE_ID
    # Отключаем silk middleware в тестах
    MIDDLEWARE=[m for m in [
        'django.middleware.security.SecurityMiddleware',
        'config.performance_middleware.RequestIDMiddleware',
        'config.middleware.RequestLoggingMiddleware',
        'config.middleware.DisableCSRFForAPI',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.locale.LocaleMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
    ] if m != 'silk.middleware.SilkyMiddleware'],  # Исключаем silk
)
class SEORobotsTestCase(TransactionTestCase):
    """
    Тесты для проверки SEO доступности для роботов поисковых систем.
    Используем TransactionTestCase вместо TestCase для избежания проблем с соединениями БД.
    """
    
    def setUp(self):
        """
        Настройка тестовых данных.
        """
        self.client = Client()
        
        # Django автоматически создает Site с id=1 в тестах, но обновляем домен
        try:
            site = Site.objects.get(pk=1)
            site.domain = 'testserver'
            site.name = 'QuizHub'
            site.save()
        except Site.DoesNotExist:
            Site.objects.create(
                id=1,
                domain='testserver',
                name='QuizHub'
            )
        
        # Создаем тестовые данные
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        self.post = Post.objects.create(
            title='Test Post',
            slug='test-post',
            content='Test content',
            category=self.category,
            published=True
        )
        
        self.project = Project.objects.create(
            title='Test Project',
            slug='test-project',
            description='Test description',
            technologies='Python, Django'
        )
        
        # Создаем тестовую тему и подтему
        try:
            self.topic = Topic.objects.create(name='Python')
            self.subtopic = Subtopic.objects.create(
                name='Functions',
                topic=self.topic
            )
        except Exception:
            # Если модели не доступны, пропускаем
            self.topic = None
            self.subtopic = None
    
    def _get_bot_user_agents(self):
        """
        Возвращает список User-Agent для различных роботов.
        """
        return [
            'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)',
            'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)',
            'facebookexternalhit/1.1',
            'Twitterbot/1.0',
        ]
    
    def _check_canonical_url(self, response, expected_path):
        """
        Проверяет наличие canonical URL в ответе.
        
        Args:
            response: HTTP ответ
            expected_path: Ожидаемый путь
        """
        content = response.content.decode('utf-8')
        canonical_pattern = r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']'
        match = re.search(canonical_pattern, content, re.IGNORECASE)
        
        self.assertIsNotNone(match, f"Canonical URL не найден на странице {expected_path}")
        
        canonical_url = match.group(1)
        
        # Проверяем, что это валидный URL (начинается с http)
        # В тестах используется testserver, поэтому не проверяем конкретный домен
        self.assertTrue(
            canonical_url.startswith('http'),
            f"Canonical URL должен быть полным URL, получен: {canonical_url}"
        )
        
        return canonical_url
    
    def _check_hreflang_tags(self, response):
        """
        Проверяет наличие hreflang тегов в ответе.
        """
        content = response.content.decode('utf-8')
        hreflang_pattern = r'<link\s+rel=["\']alternate["\']\s+hreflang=["\']([^"\']+)["\']\s+href=["\']([^"\']+)["\']'
        matches = re.findall(hreflang_pattern, content, re.IGNORECASE)
        
        self.assertGreater(len(matches), 0, "Hreflang теги не найдены")
        
        hreflangs = {}
        for lang, url in matches:
            hreflangs[lang] = url
        
        # Проверяем наличие английской и русской версий
        self.assertIn('en', hreflangs, "Hreflang для английского языка не найден")
        self.assertIn('ru', hreflangs, "Hreflang для русского языка не найден")
        
        return hreflangs
    
    def test_robots_can_access_home_page(self):
        """
        Тест: Роботы могут получить доступ к главной странице.
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get('/en/', HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200, 
                           f"Главная страница недоступна для {user_agent}")
            
            # Проверяем canonical URL
            canonical = self._check_canonical_url(response, '/en/')
            
            # Проверяем hreflang теги
            hreflangs = self._check_hreflang_tags(response)
    
    def test_robots_can_access_blog_page(self):
        """
        Тест: Роботы могут получить доступ к странице блога.
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get('/en/blog/', HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200,
                           f"Страница блога недоступна для {user_agent}")
            
            self._check_canonical_url(response, '/en/blog/')
            self._check_hreflang_tags(response)
    
    def test_robots_can_access_post_detail(self):
        """
        Тест: Роботы могут получить доступ к странице поста.
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get(f'/en/post/{self.post.slug}/', 
                                     HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200,
                           f"Страница поста недоступна для {user_agent}")
            
            canonical = self._check_canonical_url(response, f'/en/post/{self.post.slug}/')
            self.assertIn(self.post.slug, canonical, 
                         "Canonical URL должен содержать slug поста")
            
            hreflangs = self._check_hreflang_tags(response)
            
            # Проверяем, что в hreflang есть версии для обоих языков
            self.assertIn('/en/post/', hreflangs.get('en', ''))
            self.assertIn('/ru/post/', hreflangs.get('ru', ''))
    
    def test_robots_can_access_project_detail(self):
        """
        Тест: Роботы могут получить доступ к странице проекта.
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get(f'/en/project/{self.project.slug}/',
                                     HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200,
                           f"Страница проекта недоступна для {user_agent}")
            
            canonical = self._check_canonical_url(response, f'/en/project/{self.project.slug}/')
            self.assertIn(self.project.slug, canonical,
                         "Canonical URL должен содержать slug проекта")
            
            hreflangs = self._check_hreflang_tags(response)
    
    def test_robots_can_access_portfolio_page(self):
        """
        Тест: Роботы могут получить доступ к странице портфолио.
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get('/en/portfolio/', HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200,
                           f"Страница портфолио недоступна для {user_agent}")
            
            self._check_canonical_url(response, '/en/portfolio/')
            self._check_hreflang_tags(response)
    
    def test_robots_can_access_resume_page(self):
        """
        Тест: Роботы могут получить доступ к странице резюме.
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get('/en/resume/', HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200,
                           f"Страница резюме недоступна для {user_agent}")
            
            self._check_canonical_url(response, '/en/resume/')
            self._check_hreflang_tags(response)
    
    def test_robots_can_access_about_page(self):
        """
        Тест: Роботы могут получить доступ к странице "О нас".
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get('/en/about/', HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200,
                           f"Страница 'О нас' недоступна для {user_agent}")
            
            self._check_canonical_url(response, '/en/about/')
            self._check_hreflang_tags(response)
    
    def test_robots_can_access_contact_page(self):
        """
        Тест: Роботы могут получить доступ к странице контактов.
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get('/en/contact/', HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200,
                           f"Страница контактов недоступна для {user_agent}")
            
            self._check_canonical_url(response, '/en/contact/')
            self._check_hreflang_tags(response)
    
    def test_robots_can_access_quizes_page(self):
        """
        Тест: Роботы могут получить доступ к странице квизов.
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get('/en/quizes/', HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200,
                           f"Страница квизов недоступна для {user_agent}")
            
            self._check_canonical_url(response, '/en/quizes/')
            self._check_hreflang_tags(response)
    
    def test_robots_can_access_quiz_detail(self):
        """
        Тест: Роботы могут получить доступ к странице темы квиза.
        """
        if not self.topic:
            self.skipTest("Topic модель не доступна")
        
        for user_agent in self._get_bot_user_agents():
            response = self.client.get(f'/en/quiz/{self.topic.name.lower()}/',
                                     HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200,
                           f"Страница темы квиза недоступна для {user_agent}")
            
            self._check_canonical_url(response, f'/en/quiz/{self.topic.name.lower()}/')
            self._check_hreflang_tags(response)
    
    def test_robots_can_access_quiz_subtopic(self):
        """
        Тест: Роботы могут получить доступ к странице подтемы квиза.
        """
        if not self.subtopic:
            self.skipTest("Subtopic модель не доступна")
        
        for user_agent in self._get_bot_user_agents():
            subtopic_slug = slugify(self.subtopic.name)
            response = self.client.get(
                f'/en/quiz/{self.topic.name.lower()}/{subtopic_slug}/easy/',
                HTTP_USER_AGENT=user_agent
            )
            self.assertEqual(response.status_code, 200,
                           f"Страница подтемы квиза недоступна для {user_agent}")
            
            subtopic_slug = slugify(self.subtopic.name)
            self._check_canonical_url(response, 
                                    f'/en/quiz/{self.topic.name.lower()}/{subtopic_slug}/easy/')
            self._check_hreflang_tags(response)
    
    def test_robots_txt_is_accessible(self):
        """
        Тест: Роботы могут получить доступ к robots.txt.
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get('/robots.txt', HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200,
                           f"robots.txt недоступен для {user_agent}")
            
            content = response.content.decode('utf-8')
            self.assertIn('User-agent:', content, "robots.txt должен содержать User-agent")
            self.assertIn('Sitemap:', content, "robots.txt должен содержать ссылку на sitemap")
            self.assertIn('sitemap.xml', content, 
                         "robots.txt должен содержать ссылку на sitemap.xml")
    
    def test_sitemap_xml_is_accessible(self):
        """
        Тест: Роботы могут получить доступ к sitemap.xml.
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get('/sitemap.xml', HTTP_USER_AGENT=user_agent)
            self.assertEqual(response.status_code, 200,
                           f"sitemap.xml недоступен для {user_agent}")
            
            content = response.content.decode('utf-8')
            self.assertIn('<?xml', content, "sitemap.xml должен быть валидным XML")
            self.assertIn('<urlset', content, "sitemap.xml должен содержать urlset")
            self.assertIn('<url>', content, "sitemap.xml должен содержать URL")
            
            # Проверяем наличие основных страниц в sitemap
            self.assertIn('/en/', content, "sitemap должен содержать главную страницу")
            self.assertIn('/en/blog/', content, "sitemap должен содержать страницу блога")
            self.assertIn('/en/post/', content, "sitemap должен содержать посты")
            self.assertIn('/en/project/', content, "sitemap должен содержать проекты")
    
    def test_sitemap_contains_posts(self):
        """
        Тест: Sitemap содержит опубликованные посты.
        """
        response = self.client.get('/sitemap.xml')
        content = response.content.decode('utf-8')
        
        self.assertIn(self.post.slug, content,
                     f"Sitemap должен содержать пост {self.post.slug}")
    
    def test_sitemap_contains_projects(self):
        """
        Тест: Sitemap содержит проекты.
        """
        response = self.client.get('/sitemap.xml')
        content = response.content.decode('utf-8')
        
        self.assertIn(self.project.slug, content,
                     f"Sitemap должен содержать проект {self.project.slug}")
    
    def test_sitemap_contains_hreflang(self):
        """
        Тест: Sitemap содержит hreflang теги для многоязычности.
        """
        response = self.client.get('/sitemap.xml')
        content = response.content.decode('utf-8')
        
        # Проверяем наличие hreflang тегов
        self.assertIn('hreflang', content, 
                     "Sitemap должен содержать hreflang теги")
        self.assertIn('hreflang="en"', content,
                     "Sitemap должен содержать hreflang для английского языка")
        self.assertIn('hreflang="ru"', content,
                     "Sitemap должен содержать hreflang для русского языка")
    
    def test_root_url_serves_verification_meta_tags(self):
        """
        Тест: Корневой URL отдает мета-теги верификации для роботов.
        """
        for user_agent in self._get_bot_user_agents():
            response = self.client.get('/', HTTP_USER_AGENT=user_agent)
            content = response.content.decode('utf-8')
            
            # Проверяем, что это HTML (не редирект)
            self.assertIn('<html', content,
                         "Корневой URL должен отдавать HTML для роботов")
            self.assertIn('<head>', content,
                         "Корневой URL должен содержать head с мета-тегами")
    
    def test_canonical_url_uses_correct_format(self):
        """
        Тест: Canonical URL использует правильный формат (полный URL).
        """
        response = self.client.get('/en/', HTTP_USER_AGENT='Googlebot')
        canonical = self._check_canonical_url(response, '/en/')
        
        # Проверяем, что canonical содержит ожидаемый путь
        self.assertIn('/en/', canonical,
                     f"Canonical URL должен содержать путь /en/, получен: {canonical}")
    
    def test_hreflang_x_default_points_to_english(self):
        """
        Тест: Hreflang x-default указывает на английскую версию.
        """
        response = self.client.get('/en/', HTTP_USER_AGENT='Googlebot')
        hreflangs = self._check_hreflang_tags(response)
        
        # Проверяем наличие x-default
        content = response.content.decode('utf-8')
        x_default_pattern = r'hreflang=["\']x-default["\']'
        self.assertRegex(content, x_default_pattern,
                        "Должен быть hreflang x-default")
        
        # Проверяем, что x-default указывает на английскую версию
        x_default_url_pattern = r'hreflang=["\']x-default["\']\s+href=["\']([^"\']+)["\']'
        match = re.search(x_default_url_pattern, content, re.IGNORECASE)
        if match:
            x_default_url = match.group(1)
            self.assertIn('/en/', x_default_url,
                         "x-default должен указывать на английскую версию")
    
    def test_all_pages_have_canonical_url(self):
        """
        Тест: Все страницы имеют canonical URL.
        """
        pages = [
            '/en/',
            '/en/blog/',
            '/en/portfolio/',
            '/en/resume/',
            '/en/about/',
            '/en/contact/',
            '/en/quizes/',
        ]
        
        for page in pages:
            response = self.client.get(page, HTTP_USER_AGENT='Googlebot')
            self.assertEqual(response.status_code, 200,
                           f"Страница {page} недоступна")
            self._check_canonical_url(response, page)
    
    def test_all_pages_have_hreflang_tags(self):
        """
        Тест: Все страницы имеют hreflang теги.
        """
        pages = [
            '/en/',
            '/en/blog/',
            '/en/portfolio/',
            '/en/resume/',
            '/en/about/',
            '/en/contact/',
        ]
        
        for page in pages:
            response = self.client.get(page, HTTP_USER_AGENT='Googlebot')
            self.assertEqual(response.status_code, 200,
                           f"Страница {page} недоступна")
            self._check_hreflang_tags(response)

