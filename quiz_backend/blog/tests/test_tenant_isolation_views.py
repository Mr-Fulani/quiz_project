from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.models import CustomUser
from blog.context_processors import telegram_settings
from blog.models import Category, Message, Post
from tenants.middleware import clear_tenant_cache
from tenants.models import Tenant


@override_settings(ALLOWED_HOSTS=['*'])
class BlogTenantIsolationViewTests(TestCase):
    def setUp(self):
        clear_tenant_cache()
        self.tenant_a = Tenant.objects.create(slug='iso-a', name='A', domain='iso-a.example.com', site_name='A')
        self.tenant_b = Tenant.objects.create(slug='iso-b', name='B', domain='iso-b.example.com', site_name='B')
        category_a = Category.objects.create(tenant=self.tenant_a, name='Cat A', slug='cat-a')
        category_b = Category.objects.create(tenant=self.tenant_b, name='Cat B', slug='cat-b')
        Post.objects.create(tenant=self.tenant_a, title='A', slug='iso-post-a', content='a',
                            category=category_a, published=True)
        Post.objects.create(tenant=self.tenant_a, title='Draft', slug='iso-draft-a', content='d',
                            category=category_a, published=False)
        Post.objects.create(tenant=self.tenant_b, title='B', slug='iso-post-b', content='b',
                            category=category_b, published=True)
        self.host_a = {'HTTP_HOST': 'iso-a.example.com'}

    def post_url(self, slug):
        return reverse('blog:post_detail', kwargs={'slug': slug})

    def test_own_published_post_is_shown(self):
        self.assertEqual(self.client.get(self.post_url('iso-post-a'), **self.host_a).status_code, 200)

    def test_other_tenant_post_is_not_shown(self):
        self.assertEqual(self.client.get(self.post_url('iso-post-b'), **self.host_a).status_code, 404)

    def test_draft_is_hidden_from_visitors(self):
        self.assertEqual(self.client.get(self.post_url('iso-draft-a'), **self.host_a).status_code, 404)

    def test_cannot_message_user_of_other_tenant(self):
        sender = CustomUser.objects.create_user(username='sender_a', password='password123', tenant=self.tenant_a)
        CustomUser.objects.create_user(username='user_b', password='password123', tenant=self.tenant_b)
        self.client.force_login(sender)
        response = self.client.post(
            reverse('blog:send_message'), {'recipient_username': 'user_b', 'content': 'hi'}, **self.host_a
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Message.objects.exists())

    def test_message_is_saved_with_tenant(self):
        sender = CustomUser.objects.create_user(username='sender_a2', password='password123', tenant=self.tenant_a)
        CustomUser.objects.create_user(username='recipient_a', password='password123', tenant=self.tenant_a)
        self.client.force_login(sender)
        response = self.client.post(
            reverse('blog:send_message'), {'recipient_username': 'recipient_a', 'content': 'hi'}, **self.host_a
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.get().tenant, self.tenant_a)

    def test_anonymous_cannot_create_subtopic_via_api(self):
        from topics.models import Subtopic, Topic
        topic = Topic.objects.create(tenant=self.tenant_a, name='Python')
        response = self.client.post(f'/api/{topic.id}/subtopics/', {'name': 'Injected'}, **self.host_a)
        self.assertIn(response.status_code, (401, 403, 405))
        self.assertFalse(Subtopic.objects.filter(topic=topic, name='Injected').exists())


@override_settings(ALLOWED_HOSTS=['*'], DEBUG=False)
class DebugEndpointsTests(TestCase):
    def test_debug_tenant_is_hidden_from_anonymous(self):
        self.assertEqual(self.client.get('/api/debug-tenant/').status_code, 404)

    def test_telegram_auth_debug_endpoint_removed(self):
        self.assertEqual(self.client.get('/api/social-auth/telegram/auth/debug/').status_code, 404)

    def test_bot_token_not_in_template_context(self):
        request = RequestFactory().get('/')
        self.assertNotIn('TELEGRAM_BOT_TOKEN', telegram_settings(request))
