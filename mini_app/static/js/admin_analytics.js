/**
 * Система аналитики для админ-панели мини-приложения
 * Загружает и отображает ключевые метрики
 */

class AdminAnalytics {
    constructor() {
        this.telegramId = null;
        this.isLoading = false;
        
        this.init();
    }
    
    async init() {
        console.log('📊 AdminAnalytics: Initializing...');
        
        // Проверяем наличие Telegram WebApp
        if (!window.Telegram || !window.Telegram.WebApp) {
            this.showError('Telegram WebApp не доступен');
            return;
        }
        
        const tg = window.Telegram.WebApp;
        const user = tg.initDataUnsafe.user;
        
        if (!user || !user.id) {
            this.showError('Не удалось получить данные пользователя');
            return;
        }
        
        this.telegramId = user.id;
        console.log(`📊 User telegram_id: ${this.telegramId}`);
        
        // Загружаем данные
        await this.loadAnalytics();
    }
    
    async loadAnalytics() {
        if (this.isLoading) {
            console.log('⏳ Already loading...');
            return;
        }
        
        this.isLoading = true;
        this.showLoading();
        
        try {
            const response = await fetch(`/api/admin-analytics/overview?telegram_id=${this.telegramId}`);
            const data = await response.json();
            
            if (response.status === 403) {
                // Доступ запрещен
                console.warn('⚠️ Access denied');
                this.showAccessDenied();
                return;
            }
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to load analytics');
            }
            
            if (data.success) {
                console.log('✅ Analytics data loaded:', data);
                this.displayAnalytics(data);
            } else {
                throw new Error(data.error || 'Unknown error');
            }
        } catch (error) {
            console.error('❌ Error loading analytics:', error);
            this.showError(window.t('analytics_load_error', 'Ошибка загрузки статистики'));
        } finally {
            this.isLoading = false;
        }
    }
    
    displayAnalytics(data) {
        // Скрываем индикатор загрузки
        this.hideLoading();
        
        // Показываем контент
        const contentDiv = document.getElementById('analytics-content');
        if (contentDiv) {
            contentDiv.style.display = 'block';
        }
        
        // Донаты
        if (data.donations) {
            this.updateElement('total-donations', data.donations.total_donations);
            this.updateElement('total-amount', `$${this.formatNumber(data.donations.total_amount_usd)}`);
            this.updateElement('monthly-donations', data.donations.monthly_donations);
            this.updateElement('monthly-amount', `$${this.formatNumber(data.donations.monthly_amount_usd)}`);
            
            // Разбивка по источникам
            if (data.donations.by_source) {
                this.displaySourceStats(data.donations.by_source);
            }
        }
        
        // Подписчики
        if (data.subscriptions) {
            this.updateElement('total-users', data.subscriptions.total_users);
            this.updateElement('monthly-users', data.subscriptions.monthly_new_users);
            this.updateElement('weekly-users', data.subscriptions.weekly_new_users);
        }
        
        // Активность
        if (data.activity) {
            this.updateElement('active-7-days', data.activity.active_7_days);
            this.updateElement('active-30-days', data.activity.active_30_days);
            this.updateElement('online-now', data.activity.online_now);
        }
        
        // Время обновления
        if (data.timestamp) {
            const date = new Date(data.timestamp);
            const timeStr = date.toLocaleTimeString('ru-RU', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
            this.updateElement('last-updated-time', timeStr);
        }
    }
    
    displaySourceStats(bySource) {
        const container = document.getElementById('source-stats');
        if (!container) return;
        
        container.innerHTML = '';
        
        for (const [sourceKey, sourceData] of Object.entries(bySource)) {
            const sourceCard = document.createElement('div');
            sourceCard.className = 'source-card';
            
            const sourceName = sourceKey === 'website' ? 
                window.t('source_website', 'Сайт') : 
                window.t('source_mini_app', 'Мини-апп');
            
            sourceCard.innerHTML = `
                <div class="source-name">${sourceName}</div>
                <div class="source-info">
                    <span class="label">${window.t('count', 'Количество')}:</span>
                    <span class="value">${sourceData.count}</span>
                </div>
                <div class="source-info">
                    <span class="label">${window.t('amount', 'Сумма')}:</span>
                    <span class="value">$${this.formatNumber(sourceData.amount_usd)}</span>
                </div>
            `;
            
            container.appendChild(sourceCard);
        }
    }
    
    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
            element.classList.add('updated');
            setTimeout(() => element.classList.remove('updated'), 500);
        }
    }
    
    formatNumber(num) {
        if (typeof num !== 'number') {
            num = parseFloat(num) || 0;
        }
        return num.toFixed(2);
    }
    
    showLoading() {
        const loadingDiv = document.getElementById('loading-indicator');
        const contentDiv = document.getElementById('analytics-content');
        const accessDeniedDiv = document.getElementById('access-denied');
        
        if (loadingDiv) loadingDiv.style.display = 'block';
        if (contentDiv) contentDiv.style.display = 'none';
        if (accessDeniedDiv) accessDeniedDiv.style.display = 'none';
    }
    
    hideLoading() {
        const loadingDiv = document.getElementById('loading-indicator');
        if (loadingDiv) loadingDiv.style.display = 'none';
    }
    
    showAccessDenied() {
        const loadingDiv = document.getElementById('loading-indicator');
        const contentDiv = document.getElementById('analytics-content');
        const accessDeniedDiv = document.getElementById('access-denied');
        
        if (loadingDiv) loadingDiv.style.display = 'none';
        if (contentDiv) contentDiv.style.display = 'none';
        if (accessDeniedDiv) accessDeniedDiv.style.display = 'block';
    }
    
    showError(message) {
        const loadingDiv = document.getElementById('loading-indicator');
        if (loadingDiv) {
            loadingDiv.innerHTML = `
                <div style="color: #ff6666; font-size: 18px; font-weight: 600;">
                    ❌ ${message}
                </div>
            `;
        }
    }
}

// Глобальная переменная
let adminAnalytics;

// Инициализация при загрузке DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        console.log('📊 AdminAnalytics: DOM loaded, initializing...');
        adminAnalytics = new AdminAnalytics();
    });
} else {
    console.log('📊 AdminAnalytics: DOM already loaded, initializing...');
    adminAnalytics = new AdminAnalytics();
}

