#!/bin/bash

# Диагностический скрипт для проверки состояния стилей на сервере
echo "🔍 Диагностика состояния стилей на сервере..."
echo ""

# 1. Проверяем статус контейнеров
echo "1️⃣ Статус контейнеров:"
docker compose -f docker-compose.local-prod.yml ps
echo ""

# 2. Проверяем, что статические файлы собрались
echo "2️⃣ Проверка статических файлов в quiz_backend:"
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend ls -la staticfiles/ | head -20
echo ""

# 3. Проверяем манифест версионирования
echo "3️⃣ Проверка манифеста версионирования:"
if docker compose -f docker-compose.local-prod.yml exec -T quiz_backend test -f staticfiles/staticfiles.json; then
    echo "✅ Манифест существует"
    echo "📋 Первые 10 записей в манифесте:"
    docker compose -f docker-compose.local-prod.yml exec -T quiz_backend cat staticfiles/staticfiles.json | head -30
else
    echo "❌ Манифест НЕ существует! Версионирование не работает!"
fi
echo ""

# 4. Проверяем версионированные CSS файлы
echo "4️⃣ Проверка версионированных CSS файлов:"
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend find staticfiles/ -name "*.css" | head -10
echo ""

# 5. Проверяем логи Django
echo "5️⃣ Последние логи Django:"
docker compose -f docker-compose.local-prod.yml logs --tail=20 quiz_backend | grep -E "(static|collectstatic|Manifest)" || echo "Нет логов о статике"
echo ""

# 6. Проверяем конфигурацию Nginx
echo "6️⃣ Проверка конфигурации Nginx:"
docker compose -f docker-compose.local-prod.yml exec nginx nginx -t
echo ""

# 7. Проверяем, что Nginx отдает статику
echo "7️⃣ Тест доступа к статическим файлам:"
echo "Попытка получить CSS файл через curl..."
docker compose -f docker-compose.local-prod.yml exec nginx curl -I http://localhost/static/admin/css/base.css 2>/dev/null | head -5 || echo "❌ Не удалось получить статику"
echo ""

# 8. Проверяем переменную DEBUG
echo "8️⃣ Проверка переменной DEBUG:"
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend python -c "
import os
print(f'DEBUG = {os.getenv(\"DEBUG\", \"Не установлена\")}')
print(f'STATICFILES_STORAGE = {os.getenv(\"STATICFILES_STORAGE\", \"Не установлена\")}')
"
echo ""

# 9. Проверяем права доступа к staticfiles
echo "9️⃣ Проверка прав доступа к staticfiles:"
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend ls -la staticfiles/ | head -10
echo ""

# 10. Проверяем мини-приложение
echo "🔟 Проверка статики мини-приложения:"
docker compose -f docker-compose.local-prod.yml exec -T mini_app ls -la /mini_app/static/ 2>/dev/null | head -10 || echo "❌ Не удалось получить статику мини-приложения"
echo ""

echo "════════════════════════════════════════════════════════════════════"
echo "🏁 Диагностика завершена!"
echo ""
echo "💡 Если обнаружены проблемы:"
echo "   1. Запустите: ./clear_cache.sh"
echo "   2. Или полную пересборку: ./start-prod.sh"
echo "════════════════════════════════════════════════════════════════════"
