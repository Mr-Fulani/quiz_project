#!/bin/bash

# Скрипт для настройки автоматического обновления SSL сертификатов
# Использование: ./setup-ssl-auto-renewal.sh

# Определяем директорию проекта автоматически
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
RENEW_SCRIPT="$PROJECT_DIR/renew-ssl-auto.sh"
CRON_LOG="/var/log/ssl-renewal.log"

echo "🔧 Настройка автоматического обновления SSL сертификатов..."
echo "📁 Директория проекта: $PROJECT_DIR"

# Проверяем, что скрипт существует
if [ ! -f "$RENEW_SCRIPT" ]; then
    echo "❌ Ошибка: скрипт $RENEW_SCRIPT не найден"
    exit 1
fi

# Делаем скрипт исполняемым
chmod +x "$RENEW_SCRIPT"
echo "✅ Скрипт обновления сделан исполняемым"

# Создаем директорию для логов, если её нет
sudo mkdir -p "$(dirname "$CRON_LOG")"
sudo touch "$CRON_LOG"
sudo chmod 666 "$CRON_LOG" 2>/dev/null || sudo chmod 644 "$CRON_LOG"
echo "✅ Лог файл создан: $CRON_LOG"

# Проверяем наличие cron
CRON_CMD="0 3 * * * $RENEW_SCRIPT >> $CRON_LOG 2>&1"

# Проверяем, установлен ли cron
if ! command -v crontab &> /dev/null; then
    echo "⚠️  Команда crontab не найдена. Пробуем установить cron..."
    
    # Определяем дистрибутив и устанавливаем cron
    if command -v apt-get &> /dev/null; then
        echo "📦 Установка cron через apt-get..."
        sudo apt-get update && sudo apt-get install -y cron
    elif command -v yum &> /dev/null; then
        echo "📦 Установка cron через yum..."
        sudo yum install -y cronie
        sudo systemctl enable crond
        sudo systemctl start crond
    elif command -v dnf &> /dev/null; then
        echo "📦 Установка cron через dnf..."
        sudo dnf install -y cronie
        sudo systemctl enable crond
        sudo systemctl start crond
    else
        echo "❌ Не удалось определить пакетный менеджер"
        echo "💡 Установите cron вручную и запустите скрипт снова"
        echo ""
        echo "Альтернативный способ: добавьте задачу вручную в /etc/cron.d/ssl-renewal:"
        echo "   sudo bash -c 'echo \"0 3 * * * root $RENEW_SCRIPT >> $CRON_LOG 2>&1\" > /etc/cron.d/ssl-renewal'"
        exit 1
    fi
    
    # Проверяем еще раз
    if ! command -v crontab &> /dev/null; then
        echo "❌ Не удалось установить cron. Используем альтернативный способ..."
        # Используем /etc/cron.d/ вместо crontab
        echo "📝 Добавление задачи в /etc/cron.d/ssl-renewal..."
        sudo bash -c "echo '0 3 * * * root $RENEW_SCRIPT >> $CRON_LOG 2>&1' > /etc/cron.d/ssl-renewal"
        sudo chmod 644 /etc/cron.d/ssl-renewal
        echo "✅ Задача добавлена в /etc/cron.d/ssl-renewal"
        echo "✅ Автоматическое обновление SSL сертификатов настроено!"
        exit 0
    fi
fi

# Если cron установлен, используем crontab
CRON_TMP=$(mktemp)

# Получаем текущие cron задачи (кроме пустых строк и комментариев)
crontab -l 2>/dev/null | grep -v "renew-ssl-auto.sh" | grep -v "^#" | grep -v "^$" > "$CRON_TMP" 2>/dev/null || true

# Добавляем новую задачу
echo "$CRON_CMD" >> "$CRON_TMP"

# Устанавливаем обновленный crontab
crontab "$CRON_TMP"
rm "$CRON_TMP"

echo "✅ Cron задача добавлена:"
echo "   Время выполнения: каждый день в 03:00"
echo "   Команда: $CRON_CMD"
echo ""
echo "📋 Текущие cron задачи:"
if command -v crontab &> /dev/null; then
    crontab -l 2>/dev/null | grep -A 1 -B 1 "renew-ssl-auto" || echo "   (задача добавлена)"
else
    echo "   Задача добавлена в /etc/cron.d/ssl-renewal"
    if [ -f "/etc/cron.d/ssl-renewal" ]; then
        cat /etc/cron.d/ssl-renewal
    fi
fi
echo ""
echo "📝 Логи будут сохраняться в: $CRON_LOG"
echo ""
echo "💡 Для проверки логов используйте:"
echo "   tail -f $CRON_LOG"
echo ""
echo "💡 Для ручного запуска обновления:"
echo "   $RENEW_SCRIPT"
echo ""
echo "✅ Автоматическое обновление SSL сертификатов настроено!"

