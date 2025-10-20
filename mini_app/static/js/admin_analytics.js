/**
 * Система аналитики для админ-панели мини-приложения
 * Загружает и отображает ключевые метрики
 */

console.log('🟢 admin_analytics.js LOADED!');

// Предотвращаем повторное объявление класса при SPA-навигации
if (typeof AdminAnalytics === 'undefined') {
    window.AdminAnalytics = class AdminAnalytics {
        constructor() {
            this.telegramId = null;
            this.isLoading = false;
            this.dataLoaded = false;  // Флаг успешной загрузки данных
            
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
        
        // Загружаем данные только если еще не загружены
        if (!this.dataLoaded) {
            await this.loadAnalytics();
        } else {
            console.log('📊 Data already loaded, skipping...');
        }
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
                this.dataLoaded = true;  // Отмечаем что данные загружены
                this.displayAnalytics(data);
            } else {
                throw new Error(data.error || 'Unknown error');
            }
        } catch (error) {
            console.error('❌ Error loading analytics:', error);
            this.hideLoading();
            this.showError(window.t('analytics_load_error', 'Ошибка загрузки статистики') + ': ' + error.message);
        } finally {
            this.isLoading = false;
        }
    }
    
    displayAnalytics(data) {
        console.log('📊 displayAnalytics called with data:', data);
        
        // Показываем контент
        const contentDiv = document.getElementById('analytics-content');
        if (contentDiv) {
            contentDiv.style.display = 'block';
            console.log('✅ Analytics content displayed');
        } else {
            console.error('❌ analytics-content div not found!');
        }
        
        // Скрываем индикатор загрузки ПОСЛЕ показа контента
        this.hideLoading();
        console.log('✅ Loading indicator hidden');
        
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
        console.log('🔄 showLoading called');
        const loadingDiv = document.getElementById('loading-indicator');
        const contentDiv = document.getElementById('analytics-content');
        const accessDeniedDiv = document.getElementById('access-denied');
        
        console.log('🔍 Elements in showLoading:', {loadingDiv, contentDiv, accessDeniedDiv});
        
        if (loadingDiv) {
            loadingDiv.style.display = 'block';
            console.log('✅ Loading indicator shown');
        }
        if (contentDiv) {
            contentDiv.style.display = 'none';
            console.log('✅ Content hidden');
        }
        if (accessDeniedDiv) {
            accessDeniedDiv.style.display = 'none';
            console.log('✅ Access denied hidden');
        }
    }
    
    hideLoading() {
        console.log('🔄 hideLoading called');
        console.log('🔄 Call stack:', new Error().stack);
        const loadingDiv = document.getElementById('loading-indicator');
        const contentDiv = document.getElementById('analytics-content');
        
        console.log('🔍 loading-indicator element:', loadingDiv);
        console.log('🔍 analytics-content element:', contentDiv);
        
        if (loadingDiv) {
            console.log('🔍 loading-indicator current display:', loadingDiv.style.display);
            loadingDiv.style.display = 'none';
            console.log('✅ Loading indicator hidden, new display:', loadingDiv.style.display);
        }
        if (contentDiv) {
            console.log('🔍 analytics-content current display:', contentDiv.style.display);
            contentDiv.style.display = 'block';
            console.log('✅ Analytics content shown, new display:', contentDiv.style.display);
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
    };
} else {
    console.log('⚠️ [ADMIN_ANALYTICS] AdminAnalytics class already defined, skipping redefinition');
}

// Глобальная функция для инициализации (вызывается из base.html или при DOMContentLoaded)
function initAdminAnalytics() {
    console.log('═══════════════════════════════════════════════════');
    console.log('📊 [ADMIN_ANALYTICS] initAdminAnalytics called');
    console.log('📊 [ADMIN_ANALYTICS] Current pathname:', window.location.pathname);
    console.log('📊 [ADMIN_ANALYTICS] Current URL:', window.location.href);
    console.log('📊 [ADMIN_ANALYTICS] window.adminAnalyticsInstance:', window.adminAnalyticsInstance);
    console.log('📊 [ADMIN_ANALYTICS] document.readyState:', document.readyState);
    
    // Проверяем, что мы на странице админ-аналитики
    const isAdminAnalyticsPage = window.location.pathname === '/admin-analytics' || 
                                  window.location.pathname.startsWith('/admin-analytics');
    
    console.log('📊 [ADMIN_ANALYTICS] isAdminAnalyticsPage:', isAdminAnalyticsPage);
    
    if (!isAdminAnalyticsPage) {
        console.log('⚠️ [ADMIN_ANALYTICS] Not on admin-analytics page, skipping initialization');
        console.log('═══════════════════════════════════════════════════');
        return;
    }
    
    // Проверяем есть ли уже экземпляр и загружены ли данные
    if (window.adminAnalyticsInstance) {
        console.log('🔍 [ADMIN_ANALYTICS] Instance exists, checking dataLoaded...');
        console.log('🔍 [ADMIN_ANALYTICS] dataLoaded:', window.adminAnalyticsInstance.dataLoaded);
        
        if (window.adminAnalyticsInstance.dataLoaded) {
            console.log('✅ [ADMIN_ANALYTICS] AdminAnalytics already loaded with data, keeping existing instance');
            // Просто показываем контент, не перезагружаем данные
            const contentDiv = document.getElementById('analytics-content');
            const loadingDiv = document.getElementById('loading-indicator');
            console.log('🔍 [ADMIN_ANALYTICS] Elements:', {contentDiv: !!contentDiv, loadingDiv: !!loadingDiv});
            
            if (contentDiv && loadingDiv) {
                loadingDiv.style.display = 'none';
                contentDiv.style.display = 'block';
                console.log('✅ [ADMIN_ANALYTICS] Restored content visibility without reloading');
            }
            console.log('═══════════════════════════════════════════════════');
            return;
        } else {
            console.log('⚠️ [ADMIN_ANALYTICS] AdminAnalytics exists but no data, will recreate...');
        }
    }
    
    console.log('🚀 [ADMIN_ANALYTICS] Creating new AdminAnalytics instance...');
    window.adminAnalyticsInstance = new window.AdminAnalytics();
    console.log('═══════════════════════════════════════════════════');
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

