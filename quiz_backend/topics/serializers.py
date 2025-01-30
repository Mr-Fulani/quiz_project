from rest_framework import serializers
from .models import Topic, Subtopic

class SubtopicSerializer(serializers.ModelSerializer):
    """
    Сериализатор для подтем.
    """
    class Meta:
        model = Subtopic
        fields = [
            'id', 
            'name',
            'topic'
        ]

class TopicSerializer(serializers.ModelSerializer):
    """
    Сериализатор для тем с вложенными подтемами.
    """
    subtopics = SubtopicSerializer(many=True, read_only=True)
    subtopics_count = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = [
            'id',
            'name',
            'description',
            'subtopics',
            'subtopics_count'
        ]
        read_only_fields = ['id']

    def get_subtopics_count(self, obj):
        return obj.subtopics.count() 