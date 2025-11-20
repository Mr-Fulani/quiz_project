#!/bin/bash
# Скрипт для проверки логов Telegram авторизации на сервере

echo "=========================================="
echo "Проверка логов Telegram авторизации"
echo "=========================================="
echo ""

echo "1. Проверка что исправления применились в контейнере:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml exec quiz_backend grep -c "Raw data (обработанные)" /app/social_auth/views.py 2>/dev/null && echo "✅ Исправления применены" || echo "❌ Исправления НЕ применены"
echo ""

echo "2. Проверка services.py:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml exec quiz_backend grep -c "Проверка подписи Telegram для данных" /app/social_auth/services.py 2>/dev/null && echo "✅ Исправления применены" || echo "❌ Исправления НЕ применены"
echo ""

echo "3. Последние логи с упоминанием Telegram (последние 50 строк):"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=500 | grep -i "telegram\|TELEGRAM AUTH" | tail -50
echo ""

echo "4. Проверка последнего запроса к /api/social-auth/telegram/auth:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=500 | grep -A 30 "TELEGRAM AUTH GET REQUEST\|TELEGRAM AUTH POST REQUEST" | tail -80
echo ""

echo "5. Проверка ошибок 'НЕТ ДАННЫХ ОТ TELEGRAM':"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=500 | grep -A 15 "НЕТ ДАННЫХ ОТ TELEGRAM" | tail -50
echo ""

echo "6. Проверка настройки бота:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml exec quiz_backend env | grep TELEGRAM || echo "Переменные TELEGRAM не найдены"
echo ""

echo "=========================================="
echo "Для просмотра логов в реальном времени:"
echo "docker compose -f docker-compose.local-prod.yml logs -f quiz_backend | grep -i telegram"
echo "=========================================="

