#!/bin/bash

# Скрипт для очистки кэша статических файлов после деплоя
echo "🧹 Очистка кэша статических файлов..."

# Очистка кэша в контейнере quiz_backend
echo "📁 Очистка staticfiles в контейнере..."
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend rm -rf staticfiles/*

# Пересборка статических файлов
echo "📦 Пересборка статических файлов..."
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend python manage.py collectstatic --noinput --clear

# Перезапуск nginx для сброса его кэша
echo "🔄 Перезапуск Nginx..."
docker compose -f docker-compose.local-prod.yml restart nginx

echo ""
echo "✅ Кэш очищен! Теперь нажмите Ctrl+Shift+R (или Cmd+Shift+R на Mac) в браузере для жесткой перезагрузки."
echo ""
echo "💡 Если стили все еще не обновились:"
echo "   1. Откройте DevTools (F12)"
echo "   2. Перейдите на вкладку Network"
echo "   3. Включите 'Disable cache'"
echo "   4. Перезагрузите страницу"

