from django.urls import path
from . import views

app_name = 'topics'

urlpatterns = [
    # Simple endpoint for mini-app (тестовый)
    path('simple/', views.topics_simple, name='topics-simple'),
    
    # Simple endpoints for mini-app (без аутентификации)
    path('topics/<int:topic_id>/', views.topic_detail_simple, name='topic-detail-simple'),
    path('subtopics/<int:subtopic_id>/', views.subtopic_detail_simple, name='subtopic-detail-simple'),
    
    # Topics for mini-app (открытый доступ)
    path('mini-app/', views.TopicMiniAppListView.as_view(), name='topic-mini-app-list'),
    
    # Topics (требует аутентификации)
    path('', views.TopicListView.as_view(), name='topic-list'),
    path('<int:pk>/', views.TopicDetailView.as_view(), name='topic-detail'),
    path('create/', views.TopicCreateView.as_view(), name='topic-create'),
    path('<int:pk>/update/', views.TopicUpdateView.as_view(), name='topic-update'),
    path('<int:pk>/delete/', views.TopicDeleteView.as_view(), name='topic-delete'),
    
    # Subtopics
    path('subtopics/', views.SubtopicListView.as_view(), name='subtopic-list'),
    path('subtopics/<int:pk>/', views.SubtopicDetailView.as_view(), name='subtopic-detail'),
    path('subtopics/create/', views.SubtopicCreateView.as_view(), name='subtopic-create'),
    path('<int:topic_id>/subtopics/', views.TopicSubtopicsView.as_view(), name='topic-subtopics'),
    path('subtopics/<int:pk>/update/', views.SubtopicUpdateView.as_view(), name='subtopic-update'),
    path('subtopics/<int:pk>/delete/', views.SubtopicDeleteView.as_view(), name='subtopic-delete'),
] 