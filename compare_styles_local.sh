#!/bin/bash

echo "════════════════════════════════════════════════════════════════════"
echo "🔍 ДИАГНОСТИКА ЛОКАЛЬНОГО ОКРУЖЕНИЯ"
echo "════════════════════════════════════════════════════════════════════"

echo ""
echo "📋 1. ПРОВЕРКА НАСТРОЕК DJANGO В ЛОКАЛЬНОМ ОКРУЖЕНИИ:"
echo "───────────────────────────────────────────────────────────────────"

# Проверяем настройки Django
docker compose exec -T quiz_backend python -c "
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
echo "📋 2. ПРОВЕРКА CSS ФАЙЛОВ В ЛОКАЛЬНОМ ОКРУЖЕНИИ:"
echo "───────────────────────────────────────────────────────────────────"

echo "🔍 Поиск основных CSS файлов:"
docker compose exec -T quiz_backend find staticfiles -name "*.css" | grep -E "(global|main|style|base)" | head -10

echo ""
echo "🔍 Поиск версионированных CSS файлов (с хешами):"
docker compose exec -T quiz_backend find staticfiles -name "*.css" | grep -E "\.[a-f0-9]{8,}\.css$" | head -10

echo ""
echo "📋 3. ПРОВЕРКА СОДЕРЖИМОГО CSS ФАЙЛОВ:"
echo "───────────────────────────────────────────────────────────────────"

# Найдем основной CSS файл
MAIN_CSS=$(docker compose exec -T quiz_backend find staticfiles -name "*.css" | grep -E "(global|main)" | head -1)
if [ -n "$MAIN_CSS" ]; then
    echo "📄 Основной CSS файл: $MAIN_CSS"
    echo "📊 Размер файла:"
    docker compose exec -T quiz_backend ls -lh "$MAIN_CSS"
    echo "📝 Первые 20 строк:"
    docker compose exec -T quiz_backend head -20 "$MAIN_CSS"
else
    echo "❌ Основной CSS файл не найден!"
fi

echo ""
echo "📋 4. ПРОВЕРКА СТАТИЧЕСКИХ ФАЙЛОВ В ИСХОДНОМ КОДЕ:"
echo "───────────────────────────────────────────────────────────────────"

echo "🔍 Поиск CSS файлов в исходном коде:"
find quiz_backend -name "*.css" | head -10

echo ""
echo "🔍 Поиск в директории static:"
find quiz_backend -path "*/static/*" -name "*.css" | head -10

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "💡 СРАВНЕНИЕ С ПРОДАКШЕНОМ:"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "1. Сравните DEBUG настройки (должны быть разные: True vs False)"
echo "2. Сравните STORAGES настройки"
echo "3. Сравните содержимое CSS файлов"
echo "4. Проверьте, что файлы одинаковые в исходном коде"
echo ""
echo "════════════════════════════════════════════════════════════════════"
