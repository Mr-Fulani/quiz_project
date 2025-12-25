#!/bin/bash
# Скрипт для первоначальной авторизации в Instagram локально

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/quiz_backend"

# Активируем виртуальное окружение если есть
if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
    echo "✅ Виртуальное окружение активировано"
fi

# Настраиваем подключение к базе данных через localhost (Docker порт 5433)
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5433}"

echo "🔐 Настройка авторизации Instagram"
echo ""
echo "Этот скрипт откроет браузер для авторизации в Instagram."
echo "После успешной авторизации сессия будет сохранена для использования в Docker."
echo ""

# Проверяем аргументы
if [ -z "$1" ]; then
    echo "Использование: $0 [credentials_id]"
    echo ""
    echo "Если credentials_id не указан, будет использован первый найденный аккаунт Instagram."
    echo ""
    python3 manage.py shell <<EOF
from tasks.services.browser_automation.setup_instagram_session import setup_session
from webhooks.models import SocialMediaCredentials

creds = SocialMediaCredentials.objects.filter(platform='instagram').first()
if not creds:
    print("❌ Не найдены учетные данные Instagram")
    print("Создайте их в Django Admin: /admin/webhooks/socialmediacredentials/")
    exit(1)

print(f"📝 Используются учетные данные: {creds.id}")
setup_session(creds.id)
EOF
else
    python3 manage.py shell <<EOF
from tasks.services.browser_automation.setup_instagram_session import setup_session
setup_session($1)
EOF
fi

