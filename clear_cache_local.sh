#!/bin/bash

# Скрипт для очистки кэша статических файлов в локальной разработке
echo "🧹 Очистка кэша статических файлов (локальная разработка)..."

# Очистка кэша в контейнере quiz_backend
echo "📁 Очистка staticfiles в контейнере..."
docker compose exec -T quiz_backend rm -rf staticfiles/*

# Пересборка статических файлов
echo "📦 Пересборка статических файлов..."
docker compose exec -T quiz_backend python manage.py collectstatic --noinput --clear

# Перезапуск nginx для сброса его кэша
echo "🔄 Перезапуск Nginx..."
docker compose restart nginx

echo ""
echo "✅ Кэш очищен! Теперь нажмите Ctrl+Shift+R (или Cmd+Shift+R на Mac) в браузере для жесткой перезагрузки."
echo ""
echo "💡 Примечание: В режиме DEBUG=True статика отдается напрямую Django,"
echo "   поэтому обычно не требуется очистка кэша. Но если стили не обновляются,"
echo "   используйте этот скрипт."

