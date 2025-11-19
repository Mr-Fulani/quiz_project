"""
Тесты для S3 сервиса.
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock
from PIL import Image
from tasks.services.s3_service import (
    extract_s3_key_from_url,
    upload_image_to_s3,
    delete_image_from_s3
)


class S3ServiceTestCase(TestCase):
    """
    Тесты для работы с AWS S3.
    """

    def test_extract_s3_key_from_url(self):
        """
        Тест извлечения ключа S3 из URL.
        """
        url = 'https://bucket.s3.us-east-1.amazonaws.com/path/to/image.png'
        key = extract_s3_key_from_url(url)
        self.assertEqual(key, 'path/to/image.png')

    def test_extract_s3_key_from_url_with_leading_slash(self):
        """
        Тест извлечения ключа с ведущим слэшем.
        """
        url = 'https://bucket.s3.us-east-1.amazonaws.com//path/to/image.png'
        key = extract_s3_key_from_url(url)
        self.assertEqual(key, 'path/to/image.png')

    def test_extract_s3_key_from_empty_url(self):
        """
        Тест с пустым URL.
        """
        key = extract_s3_key_from_url('')
        self.assertIsNone(key)

    @patch('tasks.services.s3_service.boto3.client')
    @patch('tasks.services.s3_service.settings')
    def test_upload_image_to_s3_success(self, mock_settings, mock_boto_client):
        """
        Тест успешной загрузки изображения в S3.
        """
        # Настраиваем mock
        mock_settings.AWS_ACCESS_KEY_ID = 'test_key'
        mock_settings.AWS_SECRET_ACCESS_KEY = 'test_secret'
        mock_settings.AWS_STORAGE_BUCKET_NAME = 'test_bucket'
        mock_settings.AWS_S3_REGION_NAME = 'us-east-1'
        mock_settings.AWS_S3_CUSTOM_DOMAIN = 'test_bucket.s3.us-east-1.amazonaws.com'
        mock_settings.AWS_PUBLIC_MEDIA_DOMAIN = 'cdn.test-bucket.com'

        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        # Создаем тестовое изображение
        image = Image.new('RGB', (100, 100), color='red')

        # Загружаем
        result = upload_image_to_s3(image, 'test/image.png')

        # Проверяем
        self.assertIsNotNone(result)
        self.assertIn('cdn.test-bucket.com', result)
        mock_s3.put_object.assert_called_once()

    @patch('tasks.services.s3_service.settings')
    def test_upload_image_with_invalid_type(self, mock_settings):
        """
        Тест загрузки с неправильным типом объекта.
        """
        mock_settings.AWS_ACCESS_KEY_ID = 'test_key'
        mock_settings.AWS_SECRET_ACCESS_KEY = 'test_secret'
        mock_settings.AWS_STORAGE_BUCKET_NAME = 'test_bucket'

        result = upload_image_to_s3("not an image", 'test.png')
        self.assertIsNone(result)

    @patch('tasks.services.s3_service.boto3.client')
    @patch('tasks.services.s3_service.settings')
    def test_delete_image_from_s3_success(self, mock_settings, mock_boto_client):
        """
        Тест успешного удаления изображения из S3.
        """
        mock_settings.AWS_ACCESS_KEY_ID = 'test_key'
        mock_settings.AWS_SECRET_ACCESS_KEY = 'test_secret'
        mock_settings.AWS_STORAGE_BUCKET_NAME = 'test_bucket'
        mock_settings.AWS_S3_REGION_NAME = 'us-east-1'

        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        url = 'https://bucket.s3.us-east-1.amazonaws.com/path/to/image.png'
        result = delete_image_from_s3(url)

        self.assertTrue(result)
        mock_s3.delete_object.assert_called_once()

    def test_delete_empty_url(self):
        """
        Тест удаления с пустым URL.
        """
        result = delete_image_from_s3('')
        self.assertTrue(result)  # Пустой URL не считается ошибкой

