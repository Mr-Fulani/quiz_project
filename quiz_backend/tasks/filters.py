from django_filters import rest_framework as filters
from django.db.models import Count, Case, When, IntegerField
from .models import Task

class TaskFilter(filters.FilterSet):
    """
    Фильтры для задач.
    """
    min_difficulty = filters.NumberFilter(field_name='difficulty', lookup_expr='gte')
    max_difficulty = filters.NumberFilter(field_name='difficulty', lookup_expr='lte')
    success_rate = filters.NumberFilter(method='filter_by_success_rate')

    class Meta:
        model = Task
        fields = {
            'topic': ['exact'],
            'subtopic': ['exact'],
            'difficulty': ['exact'],
        }

    def filter_by_success_rate(self, queryset, name, value):
        """
        Фильтрация по проценту успешных решений.
        """
        return queryset.annotate(
            success_rate=Count(
                Case(
                    When(statistics__successful=True, then=1),
                    output_field=IntegerField(),
                )
            ) * 100.0 / Count('statistics')
        ).filter(success_rate__gte=value) 