#!/bin/bash
# Скрипт для деплоя исправлений кнопок обратной связи на продакшен

set -e  # Останавливаем скрипт при любой ошибке

echo "🚀 Деплой исправлений кнопок обратной связи"
echo "==========================================="
echo ""

# Проверяем, что находимся в правильной директории
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Ошибка: docker-compose.yml не найден"
    echo "   Убедитесь, что вы находитесь в директории /opt/quiz_project/quiz_project"
    exit 1
fi

# 1. Проверяем переменную ADMIN_TELEGRAM_ID
echo "📋 Шаг 1: Проверка переменной ADMIN_TELEGRAM_ID"
if grep -q "ADMIN_TELEGRAM_ID=" .env; then
    ADMIN_ID=$(grep "ADMIN_TELEGRAM_ID=" .env | cut -d '=' -f2)
    echo "   ✅ ADMIN_TELEGRAM_ID = $ADMIN_ID"
else
    echo "   ⚠️  ADMIN_TELEGRAM_ID не найден в .env"
    echo "   Добавьте в .env файл: ADMIN_TELEGRAM_ID=your_username"
    exit 1
fi
echo ""

# 2. Проверяем, что файлы обновлены
echo "📋 Шаг 2: Проверка наличия исправлений в nginx-prod.conf"
if grep -q "api/get-config/" nginx/nginx-prod.conf; then
    echo "   ✅ nginx-prod.conf содержит маршрут /api/get-config/"
else
    echo "   ❌ nginx-prod.conf не содержит маршрут /api/get-config/"
    echo "   Выполните: git pull origin main"
    exit 1
fi

if grep -q "api/feedback/" nginx/nginx-prod.conf; then
    echo "   ✅ nginx-prod.conf содержит маршрут /api/feedback/"
else
    echo "   ❌ nginx-prod.conf не содержит маршрут /api/feedback/"
    echo "   Выполните: git pull origin main"
    exit 1
fi
echo ""

# 3. Останавливаем контейнеры
echo "📋 Шаг 3: Остановка контейнеров"
docker compose down
echo "   ✅ Контейнеры остановлены"
echo ""

# 4. Пересобираем nginx и mini_app
echo "📋 Шаг 4: Пересборка nginx и mini_app"
docker compose build nginx mini_app
echo "   ✅ Контейнеры пересобраны"
echo ""

# 5. Запускаем контейнеры
echo "📋 Шаг 5: Запуск контейнеров"
docker compose up -d
echo "   ✅ Контейнеры запущены"
echo ""

# 6. Ожидание запуска
echo "📋 Шаг 6: Ожидание запуска контейнеров (10 секунд)"
sleep 10
echo ""

# 7. Проверка логов mini_app
echo "📋 Шаг 7: Проверка загрузки ADMIN_TELEGRAM_ID в mini_app"
if docker compose logs mini_app 2>/dev/null | grep -q "ADMIN_TELEGRAM_ID"; then
    docker compose logs mini_app | grep "ADMIN_TELEGRAM_ID" | tail -1
    echo "   ✅ ADMIN_TELEGRAM_ID загружен в mini_app"
else
    echo "   ⚠️  Лог ADMIN_TELEGRAM_ID не найден (возможно, контейнер еще загружается)"
fi
echo ""

# 8. Проверка статуса контейнеров
echo "📋 Шаг 8: Статус контейнеров"
docker compose ps
echo ""

# 9. Тест API
echo "📋 Шаг 9: Тест API /api/get-config/"
echo "   Выполняем: curl http://localhost/api/get-config/"
CONFIG_RESPONSE=$(curl -s http://localhost/api/get-config/ 2>/dev/null || echo "ERROR")
if [ "$CONFIG_RESPONSE" != "ERROR" ]; then
    echo "   Ответ: $CONFIG_RESPONSE"
    if echo "$CONFIG_RESPONSE" | grep -q "admin_telegram_id"; then
        echo "   ✅ API возвращает admin_telegram_id"
    else
        echo "   ⚠️  API не содержит admin_telegram_id в ответе"
    fi
else
    echo "   ⚠️  Не удалось подключиться к API (возможно, контейнеры еще запускаются)"
fi
echo ""

echo "==========================================="
echo "✅ Деплой завершен!"
echo ""
echo "Проверьте работу в браузере:"
echo "1. Откройте мини-апп → Settings"
echo "2. Нажмите кнопку 'Написать админу'"
echo "3. Должен открыться чат в Telegram"
echo ""
echo "Для просмотра логов используйте:"
echo "  docker compose logs -f mini_app"
echo "  docker compose logs -f nginx"
echo ""

