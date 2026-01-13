"""
Тесты для синхронизации статистики по translation_group_id.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from tasks.models import Task, TaskTranslation, TaskStatistics
from topics.models import Topic, Subtopic
import uuid

User = get_user_model()


class TranslationGroupStatsTestCase(TestCase):
    """
    Тесты для проверки синхронизации статистики по translation_group_id.
    """

    def setUp(self):
        """
        Подготовка тестовых данных.
        """
        # Создаем пользователя
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Создаем тему и подтему
        self.topic = Topic.objects.create(
            name='Python',
            description='Python programming'
        )
        self.subtopic = Subtopic.objects.create(
            name='Basics',
            topic=self.topic
        )
        
        # Создаем translation_group_id
        self.translation_group_id = uuid.uuid4()
        
        # Создаем две задачи с одинаковым translation_group_id (разные языки)
        self.task_ru = Task.objects.create(
            topic=self.topic,
            subtopic=self.subtopic,
            difficulty='easy',
            published=True,
            translation_group_id=self.translation_group_id
        )
        
        self.task_en = Task.objects.create(
            topic=self.topic,
            subtopic=self.subtopic,
            difficulty='easy',
            published=True,
            translation_group_id=self.translation_group_id
        )
        
        # Создаем переводы
        self.translation_ru = TaskTranslation.objects.create(
            task=self.task_ru,
            language='ru',
            question='Вопрос на русском?',
            answers=['Ответ 1', 'Ответ 2', 'Правильный ответ'],
            correct_answer='Правильный ответ'
        )
        
        self.translation_en = TaskTranslation.objects.create(
            task=self.task_en,
            language='en',
            question='Question in English?',
            answers=['Answer 1', 'Answer 2', 'Correct Answer'],
            correct_answer='Correct Answer'
        )

    def test_stats_sync_on_answer_submit(self):
        """
        Тест: при прохождении задачи на одном языке статистика синхронизируется для другого языка.
        """
        from tasks.utils import get_tasks_by_translation_group
        
        # Проверяем, что связанные задачи находятся правильно
        related_tasks = get_tasks_by_translation_group(self.task_ru)
        self.assertIn(self.task_en, related_tasks)
        self.assertIn(self.task_ru, related_tasks)
        
        # Создаем статистику для русской задачи
        stats_ru = TaskStatistics.objects.create(
            user=self.user,
            task=self.task_ru,
            attempts=1,
            successful=True,
            selected_answer='Правильный ответ'
        )
        
        # Проверяем, что статистика создана только для русской задачи
        self.assertEqual(TaskStatistics.objects.filter(user=self.user).count(), 1)
        
        # Теперь симулируем синхронизацию (как в submit_task_answer)
        related_tasks = get_tasks_by_translation_group(self.task_ru).exclude(id=self.task_ru.id)
        
        for related_task in related_tasks:
            related_stats, created = TaskStatistics.objects.get_or_create(
                user=self.user,
                task=related_task,
                defaults={
                    'attempts': 1,
                    'successful': stats_ru.successful,
                    'selected_answer': 'Correct Answer'  # Соответствующий ответ на английском
                }
            )
            if not created:
                related_stats.successful = stats_ru.successful or related_stats.successful
                related_stats.save()
        
        # Проверяем, что статистика создана и для английской задачи
        self.assertEqual(TaskStatistics.objects.filter(user=self.user).count(), 2)
        
        stats_en = TaskStatistics.objects.get(user=self.user, task=self.task_en)
        self.assertTrue(stats_en.successful)
        self.assertEqual(stats_en.attempts, 1)

    def test_is_solved_check_by_translation_group(self):
        """
        Тест: проверка is_solved должна работать по translation_group_id.
        """
        # Создаем статистику только для русской задачи
        TaskStatistics.objects.create(
            user=self.user,
            task=self.task_ru,
            attempts=1,
            successful=True,
            selected_answer='Правильный ответ'
        )
        
        # Проверяем, что английская задача тоже считается решенной
        # (симулируем логику из quiz_subtopic)
        translation_group_ids = [self.translation_group_id]
        task_stats = TaskStatistics.objects.filter(
            user=self.user,
            task__translation_group_id__in=translation_group_ids
        ).values('task__translation_group_id').distinct()
        
        solved_groups = {stat['task__translation_group_id'] for stat in task_stats}
        
        # Обе задачи должны считаться решенными
        self.assertIn(self.translation_group_id, solved_groups)
        
        # Проверяем для конкретных задач
        is_solved_ru = self.task_ru.translation_group_id in solved_groups
        is_solved_en = self.task_en.translation_group_id in solved_groups
        
        self.assertTrue(is_solved_ru)
        self.assertTrue(is_solved_en)

    def test_stats_sync_for_incorrect_answer(self):
        """
        Тест: синхронизация работает и для неправильных ответов.
        """
        # Создаем статистику с неправильным ответом для русской задачи
        stats_ru = TaskStatistics.objects.create(
            user=self.user,
            task=self.task_ru,
            attempts=1,
            successful=False,
            selected_answer='Ответ 1'
        )
        
        # Синхронизируем
        from tasks.utils import get_tasks_by_translation_group
        related_tasks = get_tasks_by_translation_group(self.task_ru).exclude(id=self.task_ru.id)
        
        for related_task in related_tasks:
            TaskStatistics.objects.get_or_create(
                user=self.user,
                task=related_task,
                defaults={
                    'attempts': 1,
                    'successful': stats_ru.successful,
                    'selected_answer': 'Answer 1'
                }
            )
        
        # Проверяем, что статистика синхронизирована
        stats_en = TaskStatistics.objects.get(user=self.user, task=self.task_en)
        self.assertFalse(stats_en.successful)
        self.assertEqual(stats_en.attempts, 1)
