/**
 * Система аналитики для админ-панели мини-приложения
 * Загружает и отображает ключевые метрики
 */

console.log('🟢 admin_analytics.js LOADED!');

class AdminAnalytics {
    constructor() {
        this.telegramId = null;
        this.isLoading = false;
        
        console.log('🏗️ AdminAnalytics constructor called');
        console.log('🏗️ Current instance:', window.adminAnalyticsInstance);
        
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
            console.log(`📊 Loading analytics for telegram_id: ${this.telegramId}`);
            const response = await fetch(`/api/admin-analytics/overview?telegram_id=${this.telegramId}`);
            console.log(`📊 Response status: ${response.status}`);
            const data = await response.json();
            console.log(`📊 Response data:`, data);
            
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
            this.showError(window.t('analytics_load_error', 'Ошибка загрузки статистики') + ': ' + error.message);
        } finally {
            this.isLoading = false;
            this.hideLoading();  // Всегда скрываем loading в finally
        }
    }
    
    displayAnalytics(data) {
        console.log('📊 displayAnalytics called with data:', data);
        
        // Скрываем индикатор загрузки
        this.hideLoading();
        console.log('✅ Loading indicator hidden');
        
        // Показываем контент
        const contentDiv = document.getElementById('analytics-content');
        if (contentDiv) {
            contentDiv.style.display = 'block';
            console.log('✅ Analytics content displayed');
        } else {
            console.error('❌ analytics-content div not found!');
        }
        
        // Донаты
        if (data.donations) {
            console.log('📊 Processing donations data:', data.donations);
            this.updateElement('total-donations', data.donations.total_donations);
            this.updateElement('total-amount', `$${this.formatNumber(data.donations.total_amount)}`);
            this.updateElement('monthly-donations', data.donations.monthly_donations);
            this.updateElement('monthly-amount', `$${this.formatNumber(data.donations.monthly_amount)}`);
            
            // Разбивка по источникам
            if (data.donations.by_source) {
                this.displaySourceStats(data.donations.by_source);
            }
        }
        
        // Подписчики
        if (data.subscriptions) {
            console.log('👥 Processing subscriptions data:', data.subscriptions);
            this.updateElement('total-users', data.subscriptions.total_users);
            this.updateElement('monthly-users', data.subscriptions.new_users_month);
        }
        
        // Активность
        if (data.activity) {
            console.log('📈 Processing activity data:', data.activity);
            this.updateElement('active-week', data.activity.active_week);
            this.updateElement('active-month', data.activity.active_month);
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
        
        console.log('✅ displayAnalytics completed successfully');
    }
    
    displaySourceStats(bySource) {
        const container = document.getElementById('source-stats');
        if (!container) {
            console.warn('⚠️ source-stats container not found');
            return;
        }
        
        container.innerHTML = '';
        console.log('📊 Displaying source stats:', bySource);
        
        // bySource может быть либо объектом с простыми числами, либо с полными данными
        for (const [sourceKey, value] of Object.entries(bySource)) {
            const sourceCard = document.createElement('div');
            sourceCard.className = 'source-card';
            
            const sourceName = sourceKey === 'website' ? 
                window.t('source_website', 'Сайт') : 
                window.t('source_mini_app', 'Мини-апп');
            
            // Проверяем, является ли value объектом или простым числом
            const count = typeof value === 'object' ? value.count : value;
            const amount = typeof value === 'object' ? value.amount_usd : null;
            
            let infoHTML = `
                <div class="source-info">
                    <span class="label">${window.t('count', 'Количество')}:</span>
                    <span class="value">${count}</span>
                </div>
            `;
            
            // Добавляем сумму если она есть
            if (amount !== null && amount !== undefined) {
                infoHTML += `
                    <div class="source-info">
                        <span class="label">${window.t('amount', 'Сумма')}:</span>
                        <span class="value">$${this.formatNumber(amount)}</span>
                    </div>
                `;
            }
            
            sourceCard.innerHTML = `
                <div class="source-name">${sourceName}</div>
                ${infoHTML}
            `;
            
            container.appendChild(sourceCard);
        }
        
        console.log('✅ Source stats displayed');
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
        console.log('🔄 hideLoading called');
        const loadingDiv = document.getElementById('loading-indicator');
        const contentDiv = document.getElementById('analytics-content');
        
        console.log('🔍 loading-indicator element:', loadingDiv);
        console.log('🔍 analytics-content element:', contentDiv);
        
        if (loadingDiv) {
            loadingDiv.style.display = 'none';
            console.log('✅ Loading indicator hidden');
        }
        if (contentDiv) {
            contentDiv.style.display = 'block';
            console.log('✅ Analytics content shown');
        }
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

// Глобальная функция для инициализации (вызывается из base.html или при DOMContentLoaded)
function initAdminAnalytics() {
    console.log('📊 AdminAnalytics: initAdminAnalytics called');
    console.log('📊 window.adminAnalyticsInstance:', window.adminAnalyticsInstance);
    console.log('📊 document.readyState:', document.readyState);
    
    if (window.adminAnalyticsInstance) {
        console.log('⚠️ AdminAnalytics already initialized, skipping...');
        return;
    }
    
    console.log('🚀 Creating new AdminAnalytics instance...');
    window.adminAnalyticsInstance = new AdminAnalytics();
}

// Проверяем состояние документа
if (document.readyState === 'loading') {
    // DOM еще загружается - ждем DOMContentLoaded
    console.log('📊 AdminAnalytics: DOM loading, adding DOMContentLoaded listener');
    document.addEventListener('DOMContentLoaded', initAdminAnalytics);
} else {
    // DOM уже загружен (SPA-навигация) - инициализируем сразу
    console.log('📊 AdminAnalytics: DOM already loaded, initializing immediately');
    initAdminAnalytics();
}

