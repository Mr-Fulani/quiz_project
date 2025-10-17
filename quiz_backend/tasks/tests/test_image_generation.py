"""
Тесты для сервиса генерации изображений.
"""
from django.test import TestCase
from PIL import Image
from tasks.services.image_generation_service import (
    extract_code_from_markdown,
    smart_format_code,
    generate_image_for_task,
    get_lexer
)


class ImageGenerationServiceTestCase(TestCase):
    """
    Тесты для генерации изображений с кодом.
    """

    def test_extract_code_from_markdown(self):
        """
        Тест извлечения кода из markdown блока.
        """
        markdown_text = "```python\nx = 5\nprint(x)\n```"
        code, language = extract_code_from_markdown(markdown_text)
        
        self.assertEqual(language, 'python')
        self.assertIn('x = 5', code)
        self.assertIn('print(x)', code)

    def test_extract_code_from_markdown_with_language(self):
        """
        Тест извлечения кода с указанным языком.
        """
        markdown_text = "```javascript\nconsole.log('test');\n```"
        code, language = extract_code_from_markdown(markdown_text)
        
        self.assertEqual(language, 'javascript')
        self.assertIn("console.log('test')", code)

    def test_extract_code_from_plain_text(self):
        """
        Тест с текстом без markdown блоков.
        """
        plain_text = "x = 5\nprint(x)"
        code, language = extract_code_from_markdown(plain_text)
        
        self.assertEqual(language, 'python')  # Дефолтный язык
        self.assertEqual(code, plain_text)

    def test_smart_format_code_python(self):
        """
        Тест форматирования Python кода.
        """
        unformatted_code = "x=5\ny=10\nprint(x+y)"
        formatted_code = smart_format_code(unformatted_code, 'python')
        
        # Проверяем что код отформатирован (есть пробелы вокруг операторов)
        self.assertIsNotNone(formatted_code)
        self.assertGreater(len(formatted_code), 0)

    def test_smart_format_code_javascript(self):
        """
        Тест форматирования JavaScript кода.
        """
        unformatted_code = "function test(){return 5;}"
        formatted_code = smart_format_code(unformatted_code, 'javascript')
        
        self.assertIsNotNone(formatted_code)
        self.assertGreater(len(formatted_code), 0)

    def test_get_lexer_python(self):
        """
        Тест определения лексера для Python.
        """
        lexer = get_lexer('python')
        self.assertIsNotNone(lexer)
        self.assertEqual(lexer.name, 'Python')

    def test_get_lexer_javascript(self):
        """
        Тест определения лексера для JavaScript.
        """
        lexer = get_lexer('javascript')
        self.assertIsNotNone(lexer)
        self.assertEqual(lexer.name, 'JavaScript')

    def test_get_lexer_with_alias(self):
        """
        Тест определения лексера с использованием alias.
        """
        lexer = get_lexer('py')  # Alias для python
        self.assertIsNotNone(lexer)
        self.assertEqual(lexer.name, 'Python')

    def test_generate_image_for_task(self):
        """
        Тест генерации изображения для задачи.
        """
        question = "```python\nx = [1, 2, 3]\nprint(x[0])\n```"
        topic_name = "Python"
        
        image = generate_image_for_task(question, topic_name)
        
        # Проверяем что изображение сгенерировано
        self.assertIsNotNone(image)
        self.assertIsInstance(image, Image.Image)
        
        # Проверяем размеры (должны быть >= минимальных)
        self.assertGreaterEqual(image.width, 1600)
        self.assertGreaterEqual(image.height, 1000)

    def test_generate_image_with_invalid_code(self):
        """
        Тест генерации изображения с невалидным кодом.
        """
        question = "This is not code at all!"
        topic_name = "Unknown"
        
        # Даже с невалидным кодом должно сгенерироваться изображение
        image = generate_image_for_task(question, topic_name)
        
        self.assertIsNotNone(image)
        self.assertIsInstance(image, Image.Image)

