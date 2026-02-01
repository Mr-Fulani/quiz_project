from django import template
from tasks.models import TaskStatistics
register = template.Library()


@register.simple_tag
def get_popular_topics():
    """
    Simple template tag to get popular topics based on global statistics
    """
    # Get global topic statistics
    topic_stats = TaskStatistics.get_global_topic_stats(limit=4)
    
    # Format data for the template
    popular_topics = []
    for i, topic in enumerate(topic_stats):
        popularity_percentage = topic['popularity_percentage']
        name = topic['name']
        
        # Map topic names to display names (programming languages)
        display_name = name.capitalize()
        
        popular_topics.append({
            'id': i + 1,
            'name': display_name,
            'popularity_percentage': popularity_percentage
        })
    
    return popular_topics