from django.urls import path
from . import views

app_name = 'platforms'

urlpatterns = [
    path('telegram-channels/', views.TelegramChannelListView.as_view(), name='telegram-channel-list'),
    path('telegram-channels/<int:pk>/', views.TelegramChannelDetailView.as_view(), name='telegram-channel-detail'),
    path('telegram/channels/stats/', views.ChannelStatsView.as_view(), name='channel-stats'),
    path('telegram/channels/health/', views.ChannelHealthCheckView.as_view(), name='channel-health'),
] 