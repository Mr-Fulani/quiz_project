# Система управления задачами Quiz Backend

## Обзор

Полная миграция функциональности бота для работы с задачами в Django backend. Система поддерживает:
- Импорт задач из JSON файлов
- Автоматическую генерацию изображений с кодом
- Загрузку изображений в AWS S3
- Публикацию задач в Telegram каналы
- Умное удаление с автоматической очисткой S3

## Установка зависимостей

Все необходимые зависимости уже добавлены в `requirements.txt`:

```bash
pip install -r requirements.txt
```

Ключевые зависимости:
- `boto3` - для работы с AWS S3
- `Pillow` - для генерации изображений
- `Pygments` - для подсветки синтаксиса кода
- `black`, `autopep8` - для форматирования кода
- `requests` - для Telegram Bot API

## Конфигурация

### Переменные окружения

Добавьте в `.env`:

```env
# AWS S3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_NAME=your_bucket_name
S3_REGION=us-east-1

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
```

### Логотип

Логотип для генерации изображений находится в:
```
quiz_backend/media/logos/logo.png
```

## Использование

### 1. Через Django Admin

#### Импорт задач

1. Перейдите в админку: `/admin/tasks/task/`
2. Нажмите кнопку "Импорт из JSON"
3. Выберите JSON файл
4. Опционально: отметьте "Опубликовать в Telegram"
5. Нажмите "Загрузить и импортировать"

#### Массовые действия

Выберите задачи в списке и используйте действия:
- **Опубликовать в Telegram** - публикует выбранные задачи
- **Сгенерировать изображения** - создает изображения для задач без них
- **Удалить с очисткой S3** - удаляет задачи и изображения из S3

#### Умное удаление

При удалении задачи через админку:
- Автоматически удаляются все связанные задачи по `translation_group_id`
- Удаляются все изображения задач из S3
- Каскадно удаляются все переводы

### 2. Через Management команду

```bash
# Импорт без публикации
python manage.py import_tasks --file path/to/tasks.json

# Импорт с публикацией в Telegram
python manage.py import_tasks --file path/to/tasks.json --publish
```

### 3. Программное использование

```python
from tasks.services.task_import_service import import_tasks_from_json

# Импорт задач
result = import_tasks_from_json('path/to/tasks.json', publish=True)

print(f"Загружено: {result['successfully_loaded']}")
print(f"Опубликовано: {result['published_count']}")
print(f"Ошибок: {result['failed_tasks']}")
```

```python
from tasks.models import Task

# Публикация отдельной задачи
task = Task.objects.get(id=123)
result = task.publish_to_telegram()

# Умное удаление
task.delete_with_related()
```

## Формат JSON файла

```json
{
  "tasks": [
    {
      "topic": "Python",
      "subtopic": "Lists",
      "difficulty": "medium",
      "image_url": "https://example.com/image.png",  // опционально
      "external_link": "https://example.com/learn",  // опционально
      "translation_group_id": "uuid",  // опционально, генерируется автоматически
      "translations": [
        {
          "language": "ru",
          "question": "```python\nx = [1, 2, 3]\nprint(x[0])\n```",
          "answers": ["0", "2", "3"],
          "correct_answer": "1",
          "explanation": "Индексация в Python начинается с 0",
          "external_link": "https://docs.python.org"  // опционально
        }
      ]
    }
  ]
}
```

### Особенности:

1. **Автоматическая генерация изображений**: Если `image_url` не указан, система:
   - Извлекает код из markdown блоков в `question`
   - Форматирует код с помощью black/autopep8
   - Генерирует изображение с подсветкой синтаксиса
   - Загружает в S3

2. **Связанные задачи**: Все задачи с одинаковым `translation_group_id` считаются переводами друг друга и удаляются вместе.

3. **Telegram группы**: Для публикации в Telegram должна существовать группа с соответствующими `topic` и `language`.

## Архитектура

### Сервисы (`tasks/services/`)

#### `s3_service.py`
- `upload_image_to_s3()` - загрузка изображений
- `delete_image_from_s3()` - удаление изображений
- `extract_s3_key_from_url()` - извлечение ключа из URL

#### `image_generation_service.py`
- `generate_image_for_task()` - генерация изображения для задачи
- `generate_console_image()` - создание изображения в стиле консоли
- `smart_format_code()` - умное форматирование кода
- `extract_code_from_markdown()` - извлечение кода из markdown

#### `telegram_service.py`
- `publish_task_to_telegram()` - публикация задачи
- `send_photo()` - отправка фото
- `send_poll()` - отправка опроса
- `send_message_with_button()` - отправка сообщения с кнопкой

#### `task_import_service.py`
- `import_tasks_from_json()` - полный импорт задач из JSON

### Сигналы (`tasks/signals.py`)

- `delete_related_tasks_and_images` - автоматическое удаление связанных задач и изображений при удалении Task

### Django Admin (`tasks/admin.py`)

Расширенная админка с:
- Кастомным URL для импорта JSON
- Переопределенными методами удаления
- Массовыми действиями

## Логирование

Все сервисы используют стандартное Django логирование:

```python
import logging
logger = logging.getLogger(__name__)
```

Логи можно найти в:
- `quiz_backend/logs/debug.log`
- Консоль (в режиме разработки)

## Примеры использования

### Пример 1: Импорт задач из JSON

```bash
python manage.py import_tasks --file uploads/python.json --publish
```

### Пример 2: Генерация изображений для существующих задач

```python
from tasks.models import Task
from tasks.services.image_generation_service import generate_image_for_task
from tasks.services.s3_service import upload_image_to_s3
import uuid

for task in Task.objects.filter(image_url__isnull=True):
    translation = task.translations.first()
    if translation:
        image = generate_image_for_task(
            translation.question, 
            task.topic.name
        )
        if image:
            image_name = f"tasks/{task.id}_{uuid.uuid4().hex[:8]}.png"
            image_url = upload_image_to_s3(image, image_name)
            if image_url:
                task.image_url = image_url
                task.save()
```

### Пример 3: Массовая публикация задач

```python
from tasks.models import Task

unpublished_tasks = Task.objects.filter(
    published=False,
    image_url__isnull=False
)

for task in unpublished_tasks:
    result = task.publish_to_telegram()
    if result['success']:
        print(f"✅ Задача {task.id} опубликована")
    else:
        print(f"❌ Ошибка: {result['errors']}")
```

## Troubleshooting

### Ошибка: "AWS S3 настройки не сконфигурированы"

Проверьте наличие переменных окружения:
```bash
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY
echo $S3_BUCKET_NAME
```

### Ошибка: "Не удалось сгенерировать изображение"

1. Проверьте установку зависимостей: `pip install Pillow Pygments`
2. Убедитесь, что логотип существует: `quiz_backend/media/logos/logo.png`

### Ошибка: "Группа не найдена для топика"

Создайте TelegramGroup в админке с соответствующими:
- `topic` - должен совпадать с topic задачи
- `language` - должен совпадать с language перевода
- `group_id` - ID Telegram канала (например, `-1001234567890`)

## Тестирование

```bash
# Запуск всех тестов
python manage.py test tasks

# Тестирование импорта
python manage.py test tasks.tests.test_task_import

# Тестирование S3
python manage.py test tasks.tests.test_s3_service
```

## Миграция данных

Если вы переносите данные из бота:

1. Экспортируйте задачи из бота в JSON
2. Импортируйте через админку или CLI
3. Система автоматически:
   - Создаст темы и подтемы
   - Сгенерирует изображения
   - Загрузит в S3
   - Опубликует в Telegram (если указано)

## Производительность

### Оптимизация импорта

При импорте больших JSON файлов используйте:

```python
from django.db import transaction

with transaction.atomic():
    result = import_tasks_from_json('large_file.json')
```

### Кэширование

Для часто используемых задач рекомендуется использовать Django cache:

```python
from django.core.cache import cache

task = cache.get(f'task_{task_id}')
if not task:
    task = Task.objects.select_related('topic', 'subtopic').get(id=task_id)
    cache.set(f'task_{task_id}', task, 3600)
```

## Безопасность

1. **AWS credentials** - храните в переменных окружения, никогда в коде
2. **Telegram Bot Token** - также в переменных окружения
3. **Валидация JSON** - система автоматически валидирует входные данные
4. **Санитизация URL** - все URL проверяются перед использованием

## Мониторинг

Рекомендуется отслеживать:
- Количество успешных/неуспешных импортов
- Размер хранилища S3
- Количество публикаций в Telegram
- Ошибки генерации изображений

Для этого можно использовать Django Admin logs или внешние сервисы мониторинга.

