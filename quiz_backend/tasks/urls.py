from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Задачи
    path('', views.TaskListView.as_view(), name='task-list'),
    path('<int:pk>/', views.TaskDetailView.as_view(), name='task-detail'),
    path('create/', views.TaskCreateView.as_view(), name='task-create'),
    
    # Задачи по подтеме (для мини-приложения)
    path('subtopic/<int:subtopic_id>/', views.tasks_by_subtopic, name='tasks-by-subtopic'),
    
    # Статистика задач
    path('stats/', views.TaskStatsView.as_view(), name='task-stats'),
    path('stats/user/', views.UserTaskStatsView.as_view(), name='user-task-stats'),
    path('stats/topic/<int:topic_id>/', views.TopicTaskStatsView.as_view(), name='topic-task-stats'),
    
    # Управление задачами
    path('<int:pk>/submit/', views.TaskSubmitView.as_view(), name='task-submit'),
    path('<int:pk>/skip/', views.TaskSkipView.as_view(), name='task-skip'),
    path('next/', views.NextTaskView.as_view(), name='next-task'),
] 