import pytest
from django.db import IntegrityError
from django.utils import timezone
from platforms.models import Group
from topics.models import Topic
from tasks.models import Task, TaskStatistics
from accounts.models import CustomUser

@pytest.mark.django_db
class TestTelegramChannelModel:
    @pytest.fixture
    def test_topic(self):
        return Topic.objects.create(
            name='Test Topic',
            description='Test Description'
        )

    def test_create_channel(self, test_topic):
        channel = Group.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )
        assert channel.group_name == 'Python Channel'
        assert channel.group_id == 123456789
        assert channel.topic_id == test_topic.id
        assert channel.language == 'ru'
        assert channel.location_type == 'group'

    def test_channel_str(self, test_topic):
        channel = Group.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )
        assert str(channel) == 'Python Channel (123456789)'

    def test_channel_topic_relationship(self, test_topic):
        channel = Group.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )
        assert channel.topic_id == test_topic.id
        assert Group.objects.filter(topic_id=test_topic.id).exists()

    def test_unique_group_id(self, test_topic):
        Group.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )
        with pytest.raises(IntegrityError):
            Group.objects.create(
                group_name='Another Channel',
                group_id=123456789,  # тот же group_id
                topic_id=test_topic.id,
                language='ru',
                location_type='group'
            )

@pytest.mark.django_db
class TestUserStatistics:
    @pytest.fixture
    def create_users_with_statistics(self):
        users_data = [
            {
                'username': 'user1',
                'correct_answers': 10,
                'total_answers': 15,
                'points': 100
            },
            {
                'username': 'user2',
                'correct_answers': 20,
                'total_answers': 25,
                'points': 200
            },
            {
                'username': 'user3',
                'correct_answers': 5,
                'total_answers': 10,
                'points': 50
            },
            {
                'username': 'user4',
                'correct_answers': 30,
                'total_answers': 35,
                'points': 300
            },
            {
                'username': 'user5',
                'correct_answers': 15,
                'total_answers': 20,
                'points': 150
            }
        ]
        
        created_users = []
        for user_data in users_data:
            user = CustomUser.objects.create(
                username=user_data['username'],
                correct_answers=user_data['correct_answers'],
                total_answers=user_data['total_answers'],
                points=user_data['points']
            )
            created_users.append(user)
        return created_users

    def test_user_statistics_creation(self, create_users_with_statistics):
        users = create_users_with_statistics
        assert len(users) == 5
        
        # Проверяем данные первого пользователя
        assert users[0].username == 'user1'
        assert users[0].correct_answers == 10
        assert users[0].total_answers == 15
        assert users[0].points == 100

        # Проверяем данные последнего пользователя
        assert users[4].username == 'user5'
        assert users[4].correct_answers == 15
        assert users[4].total_answers == 20
        assert users[4].points == 150

    def test_user_statistics_accuracy(self, create_users_with_statistics):
        users = create_users_with_statistics
        # Проверяем точность ответов для user2 (20 правильных из 25)
        assert users[1].get_accuracy() == 0.8  # 80% точность

@pytest.mark.django_db
class TestTaskStatistics:
    @pytest.fixture
    def test_task(self, test_topic):
        return Task.objects.create(
            topic=test_topic,
            difficulty='medium',
            published=True
        )

    @pytest.fixture
    def create_users_with_statistics(self, test_task):
        users_data = [
            {
                'username': 'user1',
                'attempts': 5,
                'successful': True,
            },
            {
                'username': 'user2',
                'attempts': 10,
                'successful': False,
            },
            {
                'username': 'user3',
                'attempts': 3,
                'successful': True,
            },
            {
                'username': 'user4',
                'attempts': 7,
                'successful': False,
            },
            {
                'username': 'user5',
                'attempts': 1,
                'successful': True,
            }
        ]
        
        created_statistics = []
        for user_data in users_data:
            user = CustomUser.objects.create(username=user_data['username'])
            stats = TaskStatistics.objects.create(
                user=user,
                task=test_task,
                attempts=user_data['attempts'],
                successful=user_data['successful'],
                last_attempt_date=timezone.now()
            )
            created_statistics.append(stats)
        return created_statistics

    def test_task_statistics_creation(self, create_users_with_statistics):
        statistics = create_users_with_statistics
        assert len(statistics) == 5
        
        # Проверяем данные первого пользователя
        assert statistics[0].user.username == 'user1'
        assert statistics[0].attempts == 5
        assert statistics[0].successful == True

        # Проверяем данные последнего пользователя
        assert statistics[4].user.username == 'user5'
        assert statistics[4].attempts == 1
        assert statistics[4].successful == True

    def test_task_statistics_filtering(self, create_users_with_statistics):
        # Проверяем количество успешных решений
        successful_count = TaskStatistics.objects.filter(successful=True).count()
        assert successful_count == 3

        # Проверяем количество попыток больше 5
        many_attempts_count = TaskStatistics.objects.filter(attempts__gt=5).count()
        assert many_attempts_count == 2
