from django.test import TestCase, override_settings

from blog.models import Category, Post
from tenants.middleware import clear_tenant_cache
from tenants.models import Tenant


def _slugs(response):
    data = response.json()
    items = data.get('results', data) if isinstance(data, dict) else data
    return {item['slug'] for item in items}


@override_settings(ALLOWED_HOSTS=['*'])
class BlogApiReadOnlyTenantTests(TestCase):
    def setUp(self):
        clear_tenant_cache()
        self.tenant_a = Tenant.objects.create(slug='blog-a', name='A', domain='blog-a.example.com', site_name='A')
        self.tenant_b = Tenant.objects.create(slug='blog-b', name='B', domain='blog-b.example.com', site_name='B')
        self.category_a = Category.objects.create(tenant=self.tenant_a, name='News A', slug='news-a')
        self.category_b = Category.objects.create(tenant=self.tenant_b, name='News B', slug='news-b')
        self.post_a = Post.objects.create(
            tenant=self.tenant_a, title='Post A', slug='post-a', content='a', category=self.category_a, published=True
        )
        self.draft_a = Post.objects.create(
            tenant=self.tenant_a, title='Draft A', slug='draft-a', content='d', category=self.category_a, published=False
        )
        self.post_b = Post.objects.create(
            tenant=self.tenant_b, title='Post B', slug='post-b', content='b', category=self.category_b, published=True
        )
        self.host_a = {'HTTP_HOST': 'blog-a.example.com'}

    def test_list_contains_only_current_tenant_published_posts(self):
        response = self.client.get('/api/posts/', **self.host_a)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_slugs(response), {'post-a'})

    def test_other_tenant_post_and_drafts_are_not_retrievable(self):
        self.assertEqual(self.client.get('/api/posts/post-b/', **self.host_a).status_code, 404)
        self.assertEqual(self.client.get('/api/posts/draft-a/', **self.host_a).status_code, 404)

    def test_categories_are_filtered_by_tenant(self):
        response = self.client.get('/api/categories/', **self.host_a)
        self.assertEqual(_slugs(response), {'news-a'})

    def test_unknown_host_gets_nothing(self):
        response = self.client.get('/api/posts/', HTTP_HOST='unknown.example.com')
        self.assertEqual(_slugs(response), set())

    def test_anonymous_cannot_modify_posts(self):
        create = self.client.post(
            '/api/posts/', {'title': 'X', 'slug': 'x', 'content': 'x', 'category': self.category_a.id}, **self.host_a
        )
        delete = self.client.delete('/api/posts/post-a/', **self.host_a)
        patch = self.client.patch(
            '/api/posts/post-a/', data='{"content": "defaced"}', content_type='application/json', **self.host_a
        )
        for response in (create, delete, patch):
            self.assertIn(response.status_code, (401, 403, 405))
        self.post_a.refresh_from_db()
        self.assertEqual(self.post_a.content, 'a')
        self.assertFalse(Post.objects.filter(slug='x').exists())

    def test_authenticated_user_cannot_modify_posts_via_api(self):
        from accounts.models import CustomUser
        user = CustomUser.objects.create_user(username='reader', password='password123', tenant=self.tenant_a)
        self.client.force_login(user)
        response = self.client.delete('/api/posts/post-a/', **self.host_a)
        self.assertIn(response.status_code, (403, 405))
        self.assertTrue(Post.objects.filter(slug='post-a').exists())
