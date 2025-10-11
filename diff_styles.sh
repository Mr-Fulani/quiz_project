#!/bin/bash

echo "════════════════════════════════════════════════════════════════════"
echo "🔍 СРАВНЕНИЕ CSS ФАЙЛОВ МЕЖДУ ЛОКАЛЬНЫМ И ПРОДАКШЕН ОКРУЖЕНИЯМИ"
echo "════════════════════════════════════════════════════════════════════"

echo ""
echo "📋 1. ПОЛУЧЕНИЕ CSS ФАЙЛОВ ИЗ ПРОДАКШЕНА:"
echo "───────────────────────────────────────────────────────────────────"

# Создаем временную директорию для продакшен файлов
mkdir -p /tmp/prod_styles

# Получаем CSS файлы из продакшен контейнера
echo "📥 Копируем CSS файлы из продакшен контейнера..."
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend find staticfiles -name "*.css" | head -10 | while read css_file; do
    if [ -n "$css_file" ]; then
        echo "📄 Копируем: $css_file"
        docker compose -f docker-compose.local-prod.yml exec -T quiz_backend cat "$css_file" > "/tmp/prod_styles/$(basename "$css_file")"
    fi
done

echo ""
echo "📋 2. ПОЛУЧЕНИЕ CSS ФАЙЛОВ ИЗ ЛОКАЛЬНОГО ОКРУЖЕНИЯ:"
echo "───────────────────────────────────────────────────────────────────"

# Создаем временную директорию для локальных файлов
mkdir -p /tmp/local_styles

# Получаем CSS файлы из локального контейнера
echo "📥 Копируем CSS файлы из локального контейнера..."
docker compose exec -T quiz_backend find staticfiles -name "*.css" | head -10 | while read css_file; do
    if [ -n "$css_file" ]; then
        echo "📄 Копируем: $css_file"
        docker compose exec -T quiz_backend cat "$css_file" > "/tmp/local_styles/$(basename "$css_file")"
    fi
done

echo ""
echo "📋 3. СРАВНЕНИЕ ФАЙЛОВ:"
echo "───────────────────────────────────────────────────────────────────"

# Сравниваем файлы
echo "🔍 Список файлов в продакшене:"
ls -la /tmp/prod_styles/ 2>/dev/null || echo "❌ Нет файлов в продакшене"

echo ""
echo "🔍 Список файлов в локальном окружении:"
ls -la /tmp/local_styles/ 2>/dev/null || echo "❌ Нет файлов в локальном окружении"

echo ""
echo "📋 4. ДЕТАЛЬНОЕ СРАВНЕНИЕ:"
echo "───────────────────────────────────────────────────────────────────"

# Находим общие файлы для сравнения
for file in /tmp/prod_styles/*; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        local_file="/tmp/local_styles/$filename"
        
        if [ -f "$local_file" ]; then
            echo "🔍 Сравниваем: $filename"
            if diff "$file" "$local_file" > /dev/null 2>&1; then
                echo "✅ Файлы идентичны: $filename"
            else
                echo "❌ Файлы РАЗЛИЧАЮТСЯ: $filename"
                echo "📊 Размеры:"
                echo "   Продакшен: $(wc -c < "$file") байт"
                echo "   Локальный:  $(wc -c < "$local_file") байт"
                echo "📝 Первые различия:"
                diff "$file" "$local_file" | head -10
                echo ""
            fi
        else
            echo "⚠️  Файл отсутствует в локальном окружении: $filename"
        fi
    fi
done

echo ""
echo "📋 5. ПРОВЕРКА ИСХОДНЫХ CSS ФАЙЛОВ:"
echo "───────────────────────────────────────────────────────────────────"

echo "🔍 Ищем исходные CSS файлы в проекте:"
find quiz_backend -name "*.css" -type f | head -10

echo ""
echo "🔍 Проверяем содержимое исходных файлов:"
for css_file in $(find quiz_backend -name "*.css" -type f | head -5); do
    if [ -f "$css_file" ]; then
        echo "📄 Файл: $css_file"
        echo "📊 Размер: $(wc -c < "$css_file") байт"
        echo "📝 Первые 5 строк:"
        head -5 "$css_file"
        echo ""
    fi
done

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "🧹 ОЧИСТКА ВРЕМЕННЫХ ФАЙЛОВ:"
echo "════════════════════════════════════════════════════════════════════"

rm -rf /tmp/prod_styles /tmp/local_styles
echo "✅ Временные файлы удалены"

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "🎯 ВЫВОДЫ:"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "1. Если файлы идентичны - проблема в кэшировании браузера"
echo "2. Если файлы различаются - проблема в процессе сборки"
echo "3. Если файлы отсутствуют - проблема в collectstatic"
echo "4. Проверьте исходные CSS файлы в quiz_backend/"
echo ""
echo "════════════════════════════════════════════════════════════════════"
