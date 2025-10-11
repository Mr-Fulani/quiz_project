#!/bin/bash

# Принудительное исправление проблемы со стилями
echo "🚨 ПРИНУДИТЕЛЬНОЕ ИСПРАВЛЕНИЕ СТИЛЕЙ"
echo ""

# 1. Остановка всех контейнеров
echo "1️⃣ Остановка всех контейнеров..."
docker compose -f docker-compose.local-prod.yml down
echo ""

# 2. Очистка volumes (включая staticfiles)
echo "2️⃣ Очистка volumes..."
docker volume prune -f
echo ""

# 3. Пересборка контейнеров
echo "3️⃣ Пересборка контейнеров..."
docker compose -f docker-compose.local-prod.yml build --no-cache
echo ""

# 4. Запуск сервисов
echo "4️⃣ Запуск сервисов..."
docker compose -f docker-compose.local-prod.yml up -d
echo ""

# 5. Ожидание запуска
echo "5️⃣ Ожидание полного запуска (30 секунд)..."
sleep 30
echo ""

# 6. Принудительная очистка и пересборка статики
echo "6️⃣ Принудительная очистка статики..."
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend rm -rf staticfiles/*
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend mkdir -p staticfiles
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend chmod 755 staticfiles
echo ""

echo "7️⃣ Пересборка статики с подробным выводом..."
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend python manage.py collectstatic --noinput --clear -v 2
echo ""

# 8. Проверка результата
echo "8️⃣ Проверка результата..."
if docker compose -f docker-compose.local-prod.yml exec -T quiz_backend test -f staticfiles/staticfiles.json; then
    echo "✅ Манифест создан успешно"
    echo "📋 Количество файлов в staticfiles:"
    docker compose -f docker-compose.local-prod.yml exec -T quiz_backend find staticfiles -type f | wc -l
    echo "📋 Примеры версионированных файлов:"
    docker compose -f docker-compose.local-prod.yml exec -T quiz_backend find staticfiles -name "*.css" | head -5
else
    echo "❌ ОШИБКА: Манифест не создан!"
    echo "🔍 Проверяем логи:"
    docker compose -f docker-compose.local-prod.yml logs --tail=50 quiz_backend
    exit 1
fi
echo ""

# 9. Перезапуск Nginx
echo "9️⃣ Перезапуск Nginx..."
docker compose -f docker-compose.local-prod.yml restart nginx
echo ""

# 10. Очистка кэша мини-приложения
echo "🔟 Очистка кэша мини-приложения..."
docker compose -f docker-compose.local-prod.yml exec -T mini_app rm -rf /mini_app/static/* 2>/dev/null || true
echo ""

echo "════════════════════════════════════════════════════════════════════"
echo "✅ ПРИНУДИТЕЛЬНОЕ ИСПРАВЛЕНИЕ ЗАВЕРШЕНО!"
echo ""
echo "🌐 Теперь в браузере:"
echo "   1. Откройте DevTools (F12)"
echo "   2. Перейдите на вкладку Network"
echo "   3. Включите 'Disable cache'"
echo "   4. Перезагрузите страницу с Ctrl+Shift+R"
echo ""
echo "📋 Если стили все еще не обновляются:"
echo "   1. Попробуйте режим инкогнито"
echo "   2. Очистите кэш браузера полностью"
echo "   3. Проверьте, что файлы версионированы в DevTools"
echo "════════════════════════════════════════════════════════════════════"
