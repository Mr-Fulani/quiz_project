from django.contrib import admin
from .models import Category, Post, Project

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_portfolio', 'created_at')
    list_filter = ('is_portfolio',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_portfolio',)
    ordering = ('is_portfolio', 'name')

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('is_portfolio', 'name')

    def get_list_display(self, request):
        return ('name', 'is_portfolio', 'created_at')

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'published', 'featured', 'created_at', 'views_count')
    list_filter = ('published', 'featured', 'category')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'featured', 'created_at')
    list_filter = ('featured',)
    search_fields = ('title', 'description', 'technologies')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
