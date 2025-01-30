from django.contrib import admin
from django.urls import path, re_path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.authtoken.views import obtain_auth_token
from django.views.decorators.csrf import csrf_exempt
from accounts.views import CustomObtainAuthToken

schema_view = get_schema_view(
   openapi.Info(
      title="Quiz API",
      default_version='v1',
      description="API для системы тестирования",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@quiz.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
   authentication_classes=(),  # Отключаем аутентификацию для Swagger
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API URLs
    path('api/accounts/', include('accounts.urls')),
    path('api/tasks/', include('tasks.urls')),
    path('api/topics/', include('topics.urls')),
    path('api/platforms/', include('platforms.urls')),
    path('api/feedback/', include('feedback.urls')),
    path('api/webhooks/', include('webhooks.urls')),
    
    # Auth URLs
    path('api-token-auth/', CustomObtainAuthToken.as_view(), name='api_token_auth'),
    path('api-auth/', include('rest_framework.urls')),
    
    # Documentation URLs
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
