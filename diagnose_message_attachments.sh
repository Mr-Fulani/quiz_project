#!/bin/bash

echo "=========================================="
echo "Диагностика MessageAttachment в продакшене"
echo "=========================================="
echo ""

echo "1. Запуск диагностики..."
echo "------------------------------------------"
docker compose -f docker-compose.local-prod.yml exec quiz_backend python manage.py diagnose_message_attachments
echo ""

echo "2. Запуск диагностики с исправлением..."
echo "------------------------------------------"
echo "⚠️  Это удалит поврежденные вложения!"
read -p "Продолжить? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker compose -f docker-compose.local-prod.yml exec quiz_backend python manage.py diagnose_message_attachments --fix
else
    echo "Исправление отменено"
fi

echo ""
echo "=========================================="
echo "После исправления перезапустите контейнер:"
echo "docker compose -f docker-compose.local-prod.yml restart quiz_backend_local_prod"
echo "=========================================="