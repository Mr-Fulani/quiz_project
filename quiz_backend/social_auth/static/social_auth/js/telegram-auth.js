/**
 * Telegram Login Widget для авторизации через Telegram.
 * 
 * Этот скрипт добавляет кнопку "Войти через Telegram" на сайт
 * и обрабатывает авторизацию через Telegram Login Widget.
 */

class TelegramAuth {
    constructor(options = {}) {
        this.options = {
            botName: options.botName || 'QuizHubBot',
            requestAccess: options.requestAccess || true,
            lang: options.lang || 'ru',
            usePic: options.usePic || true,
            cornerRadius: options.cornerRadius || 8,
            ...options
        };
        
        this.init();
    }
    
    init() {
        // Добавляем скрипт Telegram Login Widget если его нет
        if (!window.TelegramLoginWidget) {
            this.loadTelegramScript();
        }
        
        // Инициализируем после загрузки скрипта
        if (window.TelegramLoginWidget) {
            this.createWidget();
        } else {
            // Ждем загрузки скрипта
            window.addEventListener('telegram-widget-loaded', () => {
                this.createWidget();
            });
        }
    }
    
    loadTelegramScript() {
        const script = document.createElement('script');
        script.src = 'https://telegram.org/js/telegram-widget.js';
        script.async = true;
        script.onload = () => {
            // Создаем событие загрузки
            window.dispatchEvent(new Event('telegram-widget-loaded'));
        };
        document.head.appendChild(script);
    }
    
    createWidget() {
        // Создаем контейнер для виджета
        const container = document.getElementById('telegram-login-widget');
        if (!container) {
            console.warn('Контейнер #telegram-login-widget не найден');
            return;
        }
        
        // Очищаем контейнер
        container.innerHTML = '';
        
        // Создаем виджет (новый API)
        if (window.Telegram && window.Telegram.LoginWidget) {
            window.Telegram.LoginWidget.dataOnauth = (user) => {
                this.handleAuth(user);
            };
        } else if (window.TelegramLoginWidget) {
            // Старый API (для совместимости)
            window.TelegramLoginWidget.dataOnauth = (user) => {
                this.handleAuth(user);
            };
        }
        
        // Добавляем виджет в контейнер
        const widget = document.createElement('div');
        widget.className = 'telegram-login-widget';
        widget.setAttribute('data-telegram-login', this.options.botName);
        widget.setAttribute('data-size', 'large');
        widget.setAttribute('data-onauth', 'TelegramLoginWidget.dataOnauth');
        widget.setAttribute('data-request-access', this.options.requestAccess);
        widget.setAttribute('data-lang', this.options.lang);
        widget.setAttribute('data-use-pic', this.options.usePic);
        widget.setAttribute('data-corner-radius', this.options.cornerRadius);
        
        container.appendChild(widget);
        
        // Перезагружаем виджет (новый API)
        if (window.Telegram && window.Telegram.LoginWidget && window.Telegram.LoginWidget.reload) {
            window.Telegram.LoginWidget.reload();
        } else if (window.TelegramLoginWidget && window.TelegramLoginWidget.reload) {
            // Старый API (для совместимости)
            window.TelegramLoginWidget.reload();
        }
    }
    
    async handleAuth(user) {
        try {
            console.log('Telegram авторизация:', user);
            
            // Показываем индикатор загрузки
            this.showLoading();
            
            // Отправляем данные на сервер
            const response = await fetch('/api/social-auth/telegram/auth/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken(),
                },
                body: JSON.stringify(user)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Успешная авторизация
                this.handleSuccess(data);
            } else {
                // Ошибка авторизации
                this.handleError(data.error || 'Ошибка авторизации');
            }
            
        } catch (error) {
            console.error('Ошибка при авторизации через Telegram:', error);
            this.handleError('Ошибка сети');
        } finally {
            this.hideLoading();
        }
    }
    
    handleSuccess(data) {
        console.log('Успешная авторизация:', data);
        
        // Показываем уведомление об успехе
        this.showNotification(data.message || 'Успешная авторизация через Telegram!', 'success');
        
        // Если есть redirect_url, перенаправляем
        if (data.redirect_url) {
            setTimeout(() => {
                window.location.href = data.redirect_url;
            }, 1500);
        } else {
            // Перезагружаем страницу для обновления состояния
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        }
    }
    
    handleError(error) {
        console.error('Ошибка авторизации:', error);
        this.showNotification(error, 'error');
    }
    
    showLoading() {
        const container = document.getElementById('telegram-login-widget');
        if (container) {
            container.innerHTML = '<div class="telegram-loading">Авторизация...</div>';
        }
    }
    
    hideLoading() {
        // Восстанавливаем виджет
        this.createWidget();
    }
    
    showNotification(message, type = 'info') {
        // Создаем уведомление
        const notification = document.createElement('div');
        notification.className = `telegram-notification telegram-notification-${type}`;
        notification.textContent = message;
        
        // Добавляем стили
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            max-width: 300px;
            word-wrap: break-word;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideIn 0.3s ease-out;
        `;
        
        // Цвета для разных типов
        if (type === 'success') {
            notification.style.backgroundColor = '#4CAF50';
        } else if (type === 'error') {
            notification.style.backgroundColor = '#f44336';
        } else {
            notification.style.backgroundColor = '#2196F3';
        }
        
        // Добавляем в DOM
        document.body.appendChild(notification);
        
        // Удаляем через 5 секунд
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOut 0.3s ease-in';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }
        }, 5000);
    }
    
    getCSRFToken() {
        // Получаем CSRF токен из cookie или meta тега
        const csrfCookie = document.cookie
            .split(';')
            .find(c => c.trim().startsWith('csrftoken='));
        
        if (csrfCookie) {
            return csrfCookie.split('=')[1];
        }
        
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (csrfMeta) {
            return csrfMeta.getAttribute('content');
        }
        
        return '';
    }
}

// Добавляем CSS стили для анимаций
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    .telegram-loading {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 12px;
        background: #f5f5f5;
        border-radius: 8px;
        color: #666;
        font-size: 14px;
    }
    
    .telegram-login-widget {
        margin: 10px 0;
    }
    
    .telegram-login-widget iframe {
        border-radius: 8px;
    }
`;
document.head.appendChild(style);

// Инициализируем при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    // Инициализируем Telegram Auth если есть контейнер
    const container = document.getElementById('telegram-login-widget');
    if (container) {
        window.telegramAuth = new TelegramAuth({
            botName: 'mr_proger_bot', // Имя вашего бота
            lang: document.documentElement.lang || 'ru'
        });
    }
});

// Экспортируем для использования в других скриптах
window.TelegramAuth = TelegramAuth; 