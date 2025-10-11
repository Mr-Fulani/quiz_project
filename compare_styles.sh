#!/bin/bash

echo "════════════════════════════════════════════════════════════════════"
echo "🔍 ДЕТАЛЬНАЯ ДИАГНОСТИКА РАЗЛИЧИЙ В СТИЛЯХ"
echo "════════════════════════════════════════════════════════════════════"

echo ""
echo "📋 1. ПРОВЕРКА НАСТРОЕК DJANGO В ПРОДАКШЕНЕ:"
echo "───────────────────────────────────────────────────────────────────"

# Проверяем настройки Django
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
print(f'DEBUG: {settings.DEBUG}')
print(f'STATIC_URL: {settings.STATIC_URL}')
print(f'STATIC_ROOT: {settings.STATIC_ROOT}')
print(f'STATICFILES_DIRS: {settings.STATICFILES_DIRS}')
print(f'STORAGES: {settings.STORAGES}')
"

echo ""
echo "📋 2. ПРОВЕРКА МАНИФЕСТА ВЕРСИОНИРОВАНИЯ:"
echo "───────────────────────────────────────────────────────────────────"

# Проверяем манифест
if docker compose -f docker-compose.local-prod.yml exec -T quiz_backend test -f staticfiles/staticfiles.json; then
    echo "✅ Манифест существует"
    echo "📄 Первые 10 записей из манифеста:"
    docker compose -f docker-compose.local-prod.yml exec -T quiz_backend head -10 staticfiles/staticfiles.json
else
    echo "❌ Манифест НЕ существует!"
fi

echo ""
echo "📋 3. ПРОВЕРКА CSS ФАЙЛОВ (ОСНОВНЫЕ):"
echo "───────────────────────────────────────────────────────────────────"

echo "🔍 Поиск основных CSS файлов:"
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend find staticfiles -name "*.css" | grep -E "(global|main|style|base)" | head -10

echo ""
echo "🔍 Поиск версионированных CSS файлов (с хешами):"
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend find staticfiles -name "*.css" | grep -E "\.[a-f0-9]{8,}\.css$" | head -10

echo ""
echo "📋 4. ПРОВЕРКА СОДЕРЖИМОГО CSS ФАЙЛОВ:"
echo "───────────────────────────────────────────────────────────────────"

# Найдем основной CSS файл
MAIN_CSS=$(docker compose -f docker-compose.local-prod.yml exec -T quiz_backend find staticfiles -name "*.css" | grep -E "(global|main)" | head -1)
if [ -n "$MAIN_CSS" ]; then
    echo "📄 Основной CSS файл: $MAIN_CSS"
    echo "📊 Размер файла:"
    docker compose -f docker-compose.local-prod.yml exec -T quiz_backend ls -lh "$MAIN_CSS"
    echo "📝 Первые 20 строк:"
    docker compose -f docker-compose.local-prod.yml exec -T quiz_backend head -20 "$MAIN_CSS"
else
    echo "❌ Основной CSS файл не найден!"
fi

echo ""
echo "📋 5. ПРОВЕРКА NGINX КОНФИГУРАЦИИ:"
echo "───────────────────────────────────────────────────────────────────"

echo "🔍 Проверка активной конфигурации Nginx:"
docker compose -f docker-compose.local-prod.yml exec -T nginx nginx -T 2>/dev/null | grep -A 10 -B 2 "location /static/"

echo ""
echo "📋 6. ПРОВЕРКА ДОСТУПНОСТИ СТАТИЧЕСКИХ ФАЙЛОВ:"
echo "───────────────────────────────────────────────────────────────────"

# Проверяем доступность через Nginx
echo "🌐 Проверка доступности статических файлов через Nginx:"
STATIC_URL=$(docker compose -f docker-compose.local-prod.yml exec -T quiz_backend python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
print(settings.STATIC_URL)
" 2>/dev/null)

if [ -n "$STATIC_URL" ]; then
    echo "📡 Static URL: $STATIC_URL"
    echo "🔍 Тест доступности через curl:"
    docker compose -f docker-compose.local-prod.yml exec -T nginx curl -I "http://localhost$STATIC_URL" 2>/dev/null || echo "❌ Не удалось получить доступ к статике"
fi

echo ""
echo "📋 7. СРАВНЕНИЕ С ЛОКАЛЬНЫМ ОКРУЖЕНИЕМ:"
echo "───────────────────────────────────────────────────────────────────"

echo "💡 Для сравнения с локальным окружением выполните:"
echo ""
echo "# На локальной машине:"
echo "docker compose exec quiz_backend python -c \""
echo "import os"
echo "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')"
echo "import django"
echo "django.setup()"
echo "from django.conf import settings"
echo "print(f'DEBUG: {settings.DEBUG}')"
echo "print(f'STORAGES: {settings.STORAGES}')"
echo "\""
echo ""
echo "# Проверьте CSS файлы локально:"
echo "docker compose exec quiz_backend find staticfiles -name '*.css' | head -5"

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "🎯 СЛЕДУЮЩИЕ ШАГИ:"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "1. Сравните результаты с локальным окружением"
echo "2. Проверьте, что CSS файлы имеют одинаковое содержимое"
echo "3. Убедитесь, что версионирование работает в обоих окружениях"
echo "4. Проверьте, что Nginx правильно раздает статические файлы"
echo ""
echo "════════════════════════════════════════════════════════════════════"
