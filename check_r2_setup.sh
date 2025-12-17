#!/bin/bash
# Скрипт для проверки настройки R2

echo "🔍 Проверка настроек R2..."
echo ""

# Проверяем наличие переменных в .env
if grep -q "USE_R2_STORAGE=True" .env 2>/dev/null; then
    echo "✅ USE_R2_STORAGE=True найден"
else
    echo "❌ USE_R2_STORAGE не найден или не установлен в True"
fi

if grep -q "R2_ACCOUNT_ID=" .env 2>/dev/null; then
    echo "✅ R2_ACCOUNT_ID найден"
    R2_ACCOUNT_ID=$(grep "R2_ACCOUNT_ID=" .env | cut -d'=' -f2)
    echo "   Значение: ${R2_ACCOUNT_ID:0:10}..."
else
    echo "❌ R2_ACCOUNT_ID не найден"
fi

if grep -q "R2_ACCESS_KEY_ID=" .env 2>/dev/null; then
    echo "✅ R2_ACCESS_KEY_ID найден"
    R2_ACCESS_KEY_ID=$(grep "R2_ACCESS_KEY_ID=" .env | cut -d'=' -f2)
    echo "   Значение: ${R2_ACCESS_KEY_ID:0:10}..."
else
    echo "❌ R2_ACCESS_KEY_ID не найден"
fi

if grep -q "R2_SECRET_ACCESS_KEY=" .env 2>/dev/null; then
    echo "✅ R2_SECRET_ACCESS_KEY найден"
    R2_SECRET_ACCESS_KEY=$(grep "R2_SECRET_ACCESS_KEY=" .env | cut -d'=' -f2)
    echo "   Значение: ${R2_SECRET_ACCESS_KEY:0:10}..."
else
    echo "❌ R2_SECRET_ACCESS_KEY не найден"
fi

if grep -q "R2_BUCKET_NAME=" .env 2>/dev/null; then
    echo "✅ R2_BUCKET_NAME найден"
    R2_BUCKET_NAME=$(grep "R2_BUCKET_NAME=" .env | cut -d'=' -f2)
    echo "   Значение: $R2_BUCKET_NAME"
else
    echo "⚠️  R2_BUCKET_NAME не найден (будет использовано значение по умолчанию: quiz-hub-prod)"
fi

echo ""
echo "📋 Следующие шаги:"
echo "1. Убедитесь, что все переменные добавлены в .env"
echo "2. Перезапустите контейнеры: docker compose restart quiz_backend telegram_bot"
echo "3. Проверьте логи: docker compose logs quiz_backend | grep 'R2 хранилище'"

