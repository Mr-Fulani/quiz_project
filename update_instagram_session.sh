#!/bin/bash
# Скрипт для обновления сессии Instagram

# Проверяем аргументы командной строки
USE_LOCAL=""
case $1 in
    --local)
        USE_LOCAL="true"
        shift
        ;;
    --help)
        echo "Скрипт для обновления сессии Instagram"
        echo ""
        echo "Использование:"
        echo "  $0              # Docker режим (автоматический)"
        echo "  $0 --local      # Локальный режим (видимый браузер)"
        echo "  $0 --help       # Показать эту справку"
        echo ""
        echo "Docker режим: браузер запускается в контейнере автоматически"
        echo "Локальный режим: браузер открывается на вашем компьютере (нужны зависимости)"
        exit 0
        ;;
esac

if [ "$USE_LOCAL" = "true" ]; then
    echo "🔄 Локальный режим обновления сессии Instagram..."
    echo "📋 Инструкции:"
    echo "   1. Браузер откроется на вашем компьютере"
    echo "   2. Авторизуйтесь в Instagram"
    echo "   3. Закройте браузер после авторизации"
    echo "   4. Сессия будет сохранена"
    echo ""

    # Запускаем локальный скрипт
    exec ./update_instagram_session_local.sh
else
    echo "🔄 Docker режим обновления сессии Instagram..."
    echo "📋 Инструкции:"
    echo "   1. Браузер запустится автоматически в фоне"
    echo "   2. Авторизация произойдет автоматически (если сессия не истекла)"
    echo "   3. Или следуйте инструкциям для ручной авторизации"
    echo ""

    # Создаем временный Python скрипт
    cat > /tmp/instagram_session_update.py << 'EOF'
from tasks.services.social_media_service import publish_to_platform
from tasks.models import Task, TaskTranslation

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
EOF

    # Запускаем через docker compose с xvfb для видимого браузера
    cd "$(dirname "$0")" && docker compose run --rm \
      -e BROWSER_DEBUG=true \
      -e UPDATE_INSTAGRAM_SESSION=true \
      -v /tmp/instagram_session_update.py:/tmp/instagram_session_update.py \
      --entrypoint sh \
      quiz_backend \
      -c "
# Устанавливаем xvfb для виртуального дисплея
apt-get update && apt-get install -y xvfb

# Запускаем xvfb
Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
export DISPLAY=:99

# Запускаем Django
python3 manage.py shell -c \"
import sys
sys.path.insert(0, '/tmp')
exec(open('/tmp/instagram_session_update.py').read())
\"
"

    # Удаляем временный файл
    rm -f /tmp/instagram_session_update.py
fi
