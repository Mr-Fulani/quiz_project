from django.urls import path
from . import views

app_name = 'donation'

urlpatterns = [
    path('', views.donation_page, name='donation_page'),
    path('process/', views.process_payment, name='process_payment'),
] 