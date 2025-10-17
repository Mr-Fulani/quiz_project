# Quick Start Guide: Импорт и публикация задач

## 🚀 Быстрый старт за 5 минут

### 1. Настройте переменные окружения

Добавьте в `.env`:

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
S3_BUCKET_NAME=your_bucket
S3_REGION=us-east-1
TELEGRAM_BOT_TOKEN=your_bot_token
```

### 2. Установите зависимости

```bash
cd quiz_backend
pip install boto3 black autopep8 requests
```

### 3. Запустите миграции (если нужно)

```bash
python manage.py migrate
```

### 4. Импортируйте задачи

#### Вариант A: Через админку (рекомендуется)

1. Откройте `/admin/tasks/task/`
2. Нажмите "Импорт из JSON"
3. Выберите файл
4. Нажмите "Загрузить и импортировать"

#### Вариант B: Через командную строку

```bash
python manage.py import_tasks --file uploads/python.json --publish
```

### 5. Готово! ✅

Задачи импортированы, изображения сгенерированы и загружены в S3.

---

## 📋 Формат JSON файла (минимальный)

```json
{
  "tasks": [
    {
      "topic": "Python",
      "difficulty": "medium",
      "translations": [
        {
          "language": "ru",
          "question": "```python\nprint('Hello')\n```",
          "answers": ["Error", "None", "0"],
          "correct_answer": "Hello",
          "explanation": "Функция print выводит текст"
        }
      ]
    }
  ]
}
```

---

## 🔧 Проверка работоспособности

### 1. Проверьте S3

```python
from tasks.services.s3_service import upload_image_to_s3
from PIL import Image

# Создаем тестовое изображение
img = Image.new('RGB', (100, 100), color='red')

# Загружаем в S3
url = upload_image_to_s3(img, 'test/test.png')
print(url)  # Должен вернуть URL
```

### 2. Проверьте генерацию изображений

```python
from tasks.services.image_generation_service import generate_image_for_task

code = "```python\nx = 5\nprint(x)\n```"
img = generate_image_for_task(code, 'Python')
print(img.size)  # Должен вернуть размеры изображения
```

### 3. Проверьте Telegram

```python
from tasks.services.telegram_service import send_message

result = send_message('-1001234567890', 'Test message')
print(result)  # Должен вернуть dict с result
```

---

## ❓ Частые проблемы

### Проблема: "AWS S3 настройки не сконфигурированы"

**Решение**:
```bash
# Проверьте переменные
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY

# Если пусто, добавьте в .env и перезапустите
```

### Проблема: "Не удалось сгенерировать изображение"

**Решение**:
```bash
# Проверьте установку Pillow и Pygments
pip install Pillow Pygments

# Проверьте наличие логотипа
ls quiz_backend/media/logos/logo.png
```

### Проблема: "Группа не найдена для топика"

**Решение**:
Создайте TelegramGroup в админке:
1. Перейдите в `/admin/platforms/telegramgroup/`
2. Нажмите "Добавить"
3. Заполните:
   - Topic: `Python` (как в JSON)
   - Language: `ru` (как в JSON)
   - Group ID: `-1001234567890` (ID вашего канала)

---

## 🎯 Следующие шаги

1. **Массовая генерация изображений**:
   ```bash
   # В админке выберите задачи без изображений
   # Используйте action "Сгенерировать изображения"
   ```

2. **Массовая публикация**:
   ```bash
   # Выберите задачи с изображениями
   # Используйте action "Опубликовать в Telegram"
   ```

3. **Умное удаление**:
   ```bash
   # При удалении задачи через админку
   # Автоматически удаляются связанные задачи и изображения из S3
   ```

---

## 📚 Дополнительная информация

Полная документация: [`README.md`](./README.md)  
Changelog: [`MIGRATION_CHANGELOG.md`](./MIGRATION_CHANGELOG.md)

---

**Время на настройку**: ~5 минут  
**Сложность**: ⭐⭐☆☆☆ (Легко)

