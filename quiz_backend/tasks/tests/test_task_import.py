"""
Тесты для сервиса импорта задач.
"""
import json
import tempfile
import os
from django.test import TestCase
from unittest.mock import patch, MagicMock
from tasks.services.task_import_service import import_tasks_from_json
from tasks.models import Task, TaskTranslation
from topics.models import Topic


class TaskImportServiceTestCase(TestCase):
    """
    Тесты для импорта задач из JSON.
    """

    def setUp(self):
        """
        Подготовка тестовых данных.
        """
        # Создаем тестовую тему
        self.topic = Topic.objects.create(
            name='Python',
            description='Python programming'
        )

    def create_test_json_file(self, tasks_data):
        """
        Создает временный JSON файл с данными.
        """
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        json.dump({'tasks': tasks_data}, temp_file)
        temp_file.close()
        return temp_file.name

    def tearDown(self):
        """
        Очистка после тестов.
        """
        # Удаляем временные файлы если остались
        pass

    def test_import_simple_task(self):
        """
        Тест импорта простой задачи.
        """
        tasks_data = [
            {
                'topic': 'Python',
                'difficulty': 'easy',
                'translations': [
                    {
                        'language': 'ru',
                        'question': 'Test question',
                        'answers': ['A', 'B', 'C'],
                        'correct_answer': 'D',
                        'explanation': 'Test explanation'
                    }
                ]
            }
        ]

        json_file = self.create_test_json_file(tasks_data)

        try:
            with patch('tasks.services.task_import_service.generate_image_for_task'):
                with patch('tasks.services.task_import_service.upload_image_to_s3'):
                    result = import_tasks_from_json(json_file, publish=False)

            self.assertEqual(result['successfully_loaded'], 1)
            self.assertEqual(result['failed_tasks'], 0)
            self.assertEqual(len(result['successfully_loaded_ids']), 1)

            # Проверяем что задача создана
            task = Task.objects.get(id=result['successfully_loaded_ids'][0])
            self.assertEqual(task.topic.name, 'Python')
            self.assertEqual(task.difficulty, 'easy')

            # Проверяем перевод
            translation = task.translations.first()
            self.assertIsNotNone(translation)
            self.assertEqual(translation.language, 'ru')
            self.assertEqual(translation.question, 'Test question')

        finally:
            os.unlink(json_file)

    def test_import_task_with_multiple_translations(self):
        """
        Тест импорта задачи с несколькими переводами.
        """
        tasks_data = [
            {
                'topic': 'Python',
                'difficulty': 'medium',
                'translations': [
                    {
                        'language': 'ru',
                        'question': 'Вопрос',
                        'answers': ['A', 'B'],
                        'correct_answer': 'C',
                        'explanation': 'Объяснение'
                    },
                    {
                        'language': 'en',
                        'question': 'Question',
                        'answers': ['A', 'B'],
                        'correct_answer': 'C',
                        'explanation': 'Explanation'
                    }
                ]
            }
        ]

        json_file = self.create_test_json_file(tasks_data)

        try:
            with patch('tasks.services.task_import_service.generate_image_for_task'):
                with patch('tasks.services.task_import_service.upload_image_to_s3'):
                    result = import_tasks_from_json(json_file, publish=False)

            self.assertEqual(result['successfully_loaded'], 2)  # 2 перевода = 2 задачи
            
            # Проверяем что создано 2 задачи с одним translation_group_id
            tasks = Task.objects.filter(topic=self.topic)
            self.assertEqual(tasks.count(), 2)
            
            # Проверяем что у всех задач одинаковый translation_group_id
            group_ids = set(tasks.values_list('translation_group_id', flat=True))
            self.assertEqual(len(group_ids), 1)

        finally:
            os.unlink(json_file)

    def test_import_task_with_invalid_data(self):
        """
        Тест импорта с невалидными данными.
        """
        tasks_data = [
            {
                'topic': 'Python',
                'difficulty': 'easy',
                'translations': [
                    {
                        'language': 'ru',
                        'question': 'Test question',
                        # Отсутствуют answers и correct_answer
                    }
                ]
            }
        ]

        json_file = self.create_test_json_file(tasks_data)

        try:
            result = import_tasks_from_json(json_file, publish=False)

            self.assertEqual(result['successfully_loaded'], 0)
            self.assertEqual(result['failed_tasks'], 1)
            self.assertGreater(len(result['error_messages']), 0)

        finally:
            os.unlink(json_file)

    def test_import_nonexistent_file(self):
        """
        Тест импорта несуществующего файла.
        """
        result = import_tasks_from_json('/nonexistent/file.json', publish=False)

        self.assertEqual(result['successfully_loaded'], 0)
        self.assertGreater(len(result['error_messages']), 0)
        self.assertIn('не найден', result['error_messages'][0].lower())

    def test_import_invalid_json(self):
        """
        Тест импорта невалидного JSON.
        """
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_file.write('{ invalid json }')
        temp_file.close()

        try:
            result = import_tasks_from_json(temp_file.name, publish=False)

            self.assertEqual(result['successfully_loaded'], 0)
            self.assertGreater(len(result['error_messages']), 0)

        finally:
            os.unlink(temp_file.name)

