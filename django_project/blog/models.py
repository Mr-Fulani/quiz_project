from django.db import models



class Post(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
        db_table = 'blog_posts'

    def __str__(self):
        return self.title