#!/bin/bash
# Скрипт для проверки логов Gunicorn и диагностики ошибки 500

echo "=========================================="
echo "Проверка логов Gunicorn и ошибки 500"
echo "=========================================="
echo ""

echo "1. Проверка что логи Gunicorn существуют в контейнере:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml exec quiz_backend ls -la /app/logs/ 2>/dev/null || echo "Папка /app/logs не найдена или недоступна"
echo ""

echo "2. Последние 150 строк из gunicorn-error.log:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml exec quiz_backend tail -150 /app/logs/gunicorn-error.log 2>/dev/null || echo "Файл gunicorn-error.log не найден или пуст"
echo ""

echo "3. Поиск TELEGRAM в gunicorn-error.log:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml exec quiz_backend grep -i "telegram\|TELEGRAM AUTH POST" /app/logs/gunicorn-error.log 2>/dev/null | tail -100 || echo "Нет записей о Telegram в error.log"
echo ""

echo "4. Последние строки из gunicorn-access.log с Telegram:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml exec quiz_backend grep -i "telegram\|/api/social-auth" /app/logs/gunicorn-access.log 2>/dev/null | tail -50 || echo "Нет записей о Telegram в access.log"
echo ""

echo "5. Все последние логи quiz_backend (stdout/stderr) с print():"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=500 2>&1 | grep -A 5 "TELEGRAM AUTH POST\|POST Request\|Обработанные данные\|Вызываем\|Пользователь\|ERROR\|Traceback" | tail -200
echo ""

echo "6. Полные последние 200 строк логов quiz_backend:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=200 2>&1
echo ""

echo "=========================================="
echo "Для просмотра логов в реальном времени:"
echo "docker compose -f docker-compose.local-prod.yml logs -f quiz_backend 2>&1"
echo ""
echo "Для просмотра только ошибок Gunicorn:"
echo "docker compose -f docker-compose.local-prod.yml exec quiz_backend tail -f /app/logs/gunicorn-error.log"
echo "=========================================="

