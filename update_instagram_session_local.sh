#!/bin/bash
# Скрипт для обновления сессии Instagram локально с видимым браузером

echo "🔄 Обновление сессии Instagram локально (видимый браузер)..."
echo "📋 Инструкции:"
echo "   1. В браузере авторизуйтесь в Instagram"
echo "   2. После авторизации закройте браузер"
echo "   3. Сессия будет сохранена в базу данных"
echo ""

# Устанавливаем переменные окружения для локального запуска
export DB_HOST=localhost
export DB_PORT=5433
export DJANGO_SETTINGS_MODULE=config.settings
export BROWSER_DEBUG=true
export UPDATE_INSTAGRAM_SESSION=true

# Проверяем наличие виртуального окружения
if [ -d "quiz_backend/venv" ]; then
    echo "🐍 Активируем виртуальное окружение..."
    source quiz_backend/venv/bin/activate
elif [ -d "venv" ]; then
    echo "🐍 Активируем виртуальное окружение..."
    source venv/bin/activate
fi

# Переходим в директорию backend
cd quiz_backend

# Запускаем Django shell для обновления сессии
python3 manage.py shell -c "
from tasks.services.social_media_service import publish_to_platform
from tasks.models import Task, TaskTranslation

print('🔄 Запуск режима обновления сессии Instagram...')
print('📋 Авторизуйтесь в открывшемся браузере и закройте его после авторизации')

# Находим задачу для тестирования
task = Task.objects.get(id=239)

# Получаем первый перевод задачи
translation = task.translations.first()
if not translation:
    print('Ошибка: у задачи нет переводов')
    exit(1)

# Запускаем в режиме обновления сессии
result = publish_to_platform(task, translation, 'instagram_reels')
print(f'Результат: {result}')
"
