#!/bin/bash
# Скрипт для проверки ошибки 500 при Telegram авторизации

echo "=========================================="
echo "Проверка ошибки 500 при Telegram авторизации"
echo "=========================================="
echo ""

echo "1. Последние ошибки в логах Django (последние 100 строк):"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=200 | grep -A 15 "ERROR\|Traceback\|Exception" | tail -100
echo ""

echo "2. Логи последнего POST запроса к /api/social-auth/telegram/auth/:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=500 | grep -A 50 "TELEGRAM AUTH POST REQUEST" | tail -100
echo ""

echo "3. Полные логи с ошибками 500:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=500 | grep -B 5 -A 30 "500\|Internal Server Error" | tail -150
echo ""

echo "4. Проверка обработки данных:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=300 | grep -A 5 "Обработанные данные авторизации\|Request body" | tail -50
echo ""

echo "=========================================="
echo "Для просмотра логов в реальном времени:"
echo "docker compose -f docker-compose.local-prod.yml logs -f quiz_backend"
echo "=========================================="

