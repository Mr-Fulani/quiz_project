from django.urls import path
from . import views




urlpatterns = [
    path('', views.poll_list, name='poll_list'),
    path('<int:poll_id>/', views.poll_detail, name='poll_detail'),
    path('<int:poll_id>/submit/', views.submit_answer, name='submit_answer'),
]