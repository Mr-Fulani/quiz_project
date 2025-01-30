from django_filters import rest_framework as filters
from .models import TelegramChannel

class TelegramChannelFilter(filters.FilterSet):
    """
    Фильтры для Telegram каналов.
    
    Поддерживает фильтрацию по:
    - Названию (полное или частичное совпадение)
    - Языку
    - Типу (группа/канал)
    """
    group_name = filters.CharFilter(lookup_expr='icontains')
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = TelegramChannel
        fields = {
            'language': ['exact'],
            'location_type': ['exact'],
            'group_id': ['exact'],
        } 