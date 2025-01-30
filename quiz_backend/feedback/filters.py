from django_filters import rest_framework as filters
from .models import FeedbackMessage

class FeedbackFilter(filters.FilterSet):
    """
    Фильтры для сообщений обратной связи.
    
    Поддерживает фильтрацию по:
    - Дате создания
    - Статусу обработки
    - ID пользователя
    - Имени пользователя
    """
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    username = filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = FeedbackMessage
        fields = {
            'user_id': ['exact'],
            'is_processed': ['exact'],
        } 