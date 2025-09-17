#!/bin/bash

# Скрипт для настройки локального тестирования продакшен конфигурации

echo "🚀 Настройка локального тестирования продакшен конфигурации..."

# 1. Добавляем записи в /etc/hosts для локальных доменов
echo "📝 Добавляем записи в /etc/hosts..."

# Проверяем, есть ли уже записи
if ! grep -q "quiz-code.localhost" /etc/hosts; then
    echo "Добавляем записи в /etc/hosts (потребуется sudo пароль)..."
    sudo bash -c 'cat >> /etc/hosts << EOF

# Quiz Project Local Testing
127.0.0.1 quiz-code.localhost
127.0.0.1 mini.quiz-code.localhost
127.0.0.1 quiz-format.localhost
127.0.0.1 mini.quiz-format.localhost
127.0.0.1 quiz-game.localhost
127.0.0.1 mini.quiz-game.localhost
EOF'
    echo "✅ Записи в /etc/hosts добавлены"
else
    echo "✅ Записи в /etc/hosts уже существуют"
fi

# 2. Останавливаем обычные контейнеры если они запущены
echo "🛑 Останавливаем обычные контейнеры..."
docker-compose down 2>/dev/null || true

# 3. Запускаем тестовую конфигурацию
echo "🚀 Запускаем тестовую конфигурацию..."
docker compose -f docker-compose.local-prod.yml -f docker-compose.local-prod.override.yml up --build -d --remove-orphans

echo ""
echo "✅ Локальная тестовая среда запущена!"
echo ""
echo "📋 Доступные URL для тестирования:"
echo "🌐 Основной сайт: http://quiz-code.localhost"
echo "📱 Мини-приложение: http://mini.quiz-code.localhost:8081"
echo "🔧 Прямой доступ к мини-аппу: http://localhost:8080"
echo ""
echo "📊 Мониторинг:"
echo "🔍 Логи: docker-compose -f docker-compose.local-prod.yml -f docker-compose.local-prod.override.yml logs -f"
echo "📈 Статус: docker-compose -f docker-compose.local-prod.yml -f docker-compose.local-prod.override.yml ps"
echo ""
echo "🛑 Остановка: docker-compose -f docker-compose.local-prod.yml -f docker-compose.local-prod.override.yml down"
echo ""
echo "⚠️  Помните: DEBUG=False, поэтому ошибки будут отображаться как в продакшене"
