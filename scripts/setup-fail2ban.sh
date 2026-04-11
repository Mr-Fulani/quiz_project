#!/bin/bash
# ============================================================
# setup-fail2ban.sh — Настройка fail2ban для блокировки ботов
# Запускать ПОСЛЕ ./start-prod.sh
# ============================================================

set -e

LOG_PATH="$(cd "$(dirname "$0")/.." && pwd)/logs/nginx/access.log"

echo "📁 Путь к логам nginx: $LOG_PATH"

# Ждём пока лог-файл появится (nginx должен быть запущен)
for i in {1..30}; do
    if [ -f "$LOG_PATH" ]; then
        echo "✅ Лог-файл найден"
        break
    fi
    echo "⏳ Ожидание лог-файла... ($i/30)"
    sleep 2
done

if [ ! -f "$LOG_PATH" ]; then
    echo "❌ Лог-файл не найден: $LOG_PATH"
    echo "   Убедитесь что nginx запущен: docker ps | grep nginx"
    exit 1
fi

# Фильтр для SOCKS5-ботов и прокси-сканеров
sudo tee /etc/fail2ban/filter.d/nginx-bots.conf > /dev/null << 'EOF'
[Definition]
failregex = ^<HOST> -.*"(?:\\x05|POST http://(?:149|91|5)\.|CONNECT \S+:443)" \d+ \d+
ignoreregex =
EOF

echo "✅ Фильтр создан"

# Jail для nginx-ботов
sudo tee /etc/fail2ban/jail.d/nginx-bots.conf > /dev/null << EOF
[nginx-bots]
enabled  = true
filter   = nginx-bots
port     = http,https
logpath  = $LOG_PATH
maxretry = 10
findtime = 30
bantime  = 86400
EOF

echo "✅ Jail создан"

# Перезапустить fail2ban
sudo systemctl restart fail2ban
sleep 3

# Проверить статус
sudo fail2ban-client status nginx-bots

echo ""
echo "🚀 fail2ban настроен! Агрессивные боты будут баниться на 24 часа."
echo "   Статус: sudo fail2ban-client status nginx-bots"
echo "   Список забаненных: sudo fail2ban-client get nginx-bots banip"
