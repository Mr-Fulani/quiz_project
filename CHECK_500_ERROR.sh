#!/bin/bash
# Скрипт для проверки ошибки 500 при Telegram авторизации

echo "=========================================="
echo "Проверка ошибки 500 при Telegram авторизации"
echo "=========================================="
echo ""

echo "1. Последние 150 строк логов quiz_backend (БЕЗ фильтрации):"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=150 2>&1 | tail -100
echo ""

echo "2. Поиск TELEGRAM AUTH POST REQUEST:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=500 2>&1 | grep -A 100 "TELEGRAM AUTH POST REQUEST" | tail -150
echo ""

echo "3. Поиск ошибок и исключений:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=500 2>&1 | grep -i "error\|exception\|traceback" | tail -80
echo ""

echo "4. Проверка обработки данных:"
echo "---------------------------------------------------"
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=500 2>&1 | grep -A 3 "Обработанные данные\|Request body\|Данные получены" | tail -60
echo ""

echo "=========================================="
echo "Для просмотра ВСЕХ логов в реальном времени:"
echo "docker compose -f docker-compose.local-prod.yml logs -f quiz_backend 2>&1"
echo ""
echo "Для просмотра только ошибок:"
echo "docker compose -f docker-compose.local-prod.yml logs -f quiz_backend 2>&1 | grep -i error"
echo "=========================================="

