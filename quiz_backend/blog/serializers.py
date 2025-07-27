from rest_framework import serializers
from .models import Category, Post, Project

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description']

class PostSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'content', 'excerpt',
            'category', 'category_id', 'published',
            'featured', 'created_at', 'updated_at',
            'published_at', 'views_count'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at', 'views_count']

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            'id', 'title', 'slug', 'description', 'technologies',
            'github_link', 'demo_link', 'featured',
            'created_at', 'updated_at', 'views_count'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at'] 