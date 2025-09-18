#!/bin/bash

# Скрипт для запуска локального тестирования продакшен настроек БЕЗ SSL
echo "🧪 Запуск локального тестирования продакшен настроек..."

# 1. Добавляем записи в /etc/hosts для локальных доменов
echo "📝 Проверяем записи в /etc/hosts..."

if ! grep -q "mini.quiz-code.localhost" /etc/hosts; then
    echo "Добавляем записи в /etc/hosts (потребуется sudo пароль)..."
    sudo bash -c 'cat >> /etc/hosts << EOF

# Quiz Project Local Testing
127.0.0.1 mini.quiz-code.localhost
EOF'
    echo "✅ Записи в /etc/hosts добавлены"
else
    echo "✅ Записи в /etc/hosts уже существуют"
fi

# 2. Останавливаем обычные контейнеры если они запущены
echo "🛑 Останавливаем обычные контейнеры..."
docker-compose down 2>/dev/null || true

# 3. Останавливаем тестовые контейнеры если они запущены
echo "🛑 Останавливаем предыдущие тестовые контейнеры..."
docker-compose -f docker-compose.local-test.yml down 2>/dev/null || true

# 4. Запускаем тестовую конфигурацию
echo "🚀 Запускаем тестовую конфигурацию..."
docker-compose -f docker-compose.local-test.yml up --build -d

echo ""
echo "✅ Локальная тестовая среда запущена!"
echo ""
echo "📋 Доступные URL для тестирования:"
echo "🌐 Основной сайт: http://localhost:8081"
echo "📱 Мини-приложение: http://mini.quiz-code.localhost:8081"
echo "🔧 Прямой доступ к мини-аппу: http://localhost:8081"
echo "📊 Django админка: http://localhost:8081/admin/"
echo ""
echo "📊 Мониторинг:"
echo "🔍 Логи: docker-compose -f docker-compose.local-test.yml logs -f"
echo "📈 Статус: docker-compose -f docker-compose.local-test.yml ps"
echo ""
echo "🛑 Остановка: docker-compose -f docker-compose.local-test.yml down"
echo ""
echo "⚠️  Помните: DEBUG=False, поэтому ошибки будут отображаться как в продакшене"
echo "🔧 Тестируйте аватарки на: http://mini.quiz-code.localhost:8081/top_users"
