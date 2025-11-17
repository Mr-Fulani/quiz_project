from django.core.management import call_command
from django.test import TestCase, SimpleTestCase
from topics.models import Topic, Subtopic
from topics.utils import normalize_subtopic_name
from tasks.models import Task


class NormalizeSubtopicNameTest(SimpleTestCase):
    """
    Тесты функции normalize_subtopic_name.
    """

    def test_special_characters_and_spaces(self):
        """
        Проверяет замену спецсимволов и схлопывание пробелов.
        """
        value = '  functions   &  arguments / basics '
        self.assertEqual(
            normalize_subtopic_name(value),
            'Functions And Arguments Basics',
        )


class NormalizeSubtopicsCommandTest(TestCase):
    """
    Тесты команды normalize_subtopics.
    """

    def setUp(self):
        self.topic = Topic.objects.create(
            name='Python',
            description='Тестовая тема',
        )
        self.canonical = Subtopic.objects.create(
            topic=self.topic,
            name='Functions and Arguments',
        )
        self.duplicate = Subtopic.objects.create(
            topic=self.topic,
            name='Functions  &   Arguments',
        )
        self.task_primary = Task.objects.create(
            topic=self.topic,
            subtopic=self.canonical,
            difficulty='easy',
        )
        self.task_duplicate = Task.objects.create(
            topic=self.topic,
            subtopic=self.duplicate,
            difficulty='medium',
        )

    def test_dry_run_does_not_modify_data(self):
        """
        В режиме dry-run данные остаются неизменными.
        """
        call_command('normalize_subtopics')
        self.assertEqual(Subtopic.objects.count(), 2)
        self.task_duplicate.refresh_from_db()
        self.assertEqual(self.task_duplicate.subtopic_id, self.duplicate.id)

    def test_apply_merges_duplicates(self):
        """
        В режиме apply задачи переносятся, а дублирующая подтема удаляется.
        """
        call_command('normalize_subtopics', apply=True)
        self.assertEqual(Subtopic.objects.count(), 1)
        self.task_duplicate.refresh_from_db()
        self.assertEqual(self.task_duplicate.subtopic_id, self.canonical.id)
        self.canonical.refresh_from_db()
        self.assertEqual(self.canonical.name, 'Functions And Arguments')

