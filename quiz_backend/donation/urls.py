from django.urls import path
from . import views

app_name = 'donation'

urlpatterns = [
    path('', views.donation_page, name='donation_page'),
    path('test/', views.test_stripe, name='test_stripe'),
] 