from django.urls import path
from . import views

app_name = 'feedback'

urlpatterns = [
    path('', views.FeedbackListView.as_view(), name='feedback-list'),
    path('<int:pk>/', views.FeedbackDetailView.as_view(), name='feedback-detail'),
    path('create/', views.FeedbackCreateView.as_view(), name='feedback-create'),
] 