from django.urls import path
from rest_framework.authtoken import views as token_views

app_name = 'accounts_api'

urlpatterns = [
    path('token/', token_views.obtain_auth_token, name='token'),
    # Другие API endpoints...
] 