/**
 * JavaScript для страницы статистики мини-приложения
 * Обеспечивает динамическое обновление статистики и анимации
 */

class StatisticsManager {
    constructor() {
        this.telegramId = this.getTelegramId();
        this.init();
    }

    /**
     * Получает telegram_id из cookie или других источников
     */
    getTelegramId() {
        // Пытаемся получить из cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'telegram_id') {
                return parseInt(value);
            }
        }
        return null;
    }

    /**
     * Инициализация статистики
     */
    init() {
        console.log('StatisticsManager: Инициализация статистики');
        
        // Анимация появления карточек
        this.animateCards();
        
        // Перевод названий достижений
        this.translateAchievements();
        
        // Обновление статистики каждые 30 секунд
        if (this.telegramId) {
            setInterval(() => this.refreshStatistics(), 30000);
        }
        
        // Слушаем изменения языка
        this.setupLanguageListener();
    }

    /**
     * Перевод названий достижений
     */
    translateAchievements() {
        const achievementElements = document.querySelectorAll('[data-achievement-id]');
        achievementElements.forEach(element => {
            const achievementId = element.getAttribute('data-achievement-id');
            const translationKey = `achievement_${achievementId}`;
            
            // Используем глобальную функцию t() для получения перевода
            if (window.t) {
                const translatedName = window.t(translationKey, element.textContent);
                element.textContent = translatedName;
            }
        });
    }

    /**
     * Настройка слушателя изменений языка
     */
    setupLanguageListener() {
        // Слушаем события изменения языка от системы локализации
        document.addEventListener('languageChanged', () => {
            this.translateAchievements();
        });
    }

    /**
     * Анимация появления карточек статистики
     */
    animateCards() {
        const cards = document.querySelectorAll('.stat-card');
        cards.forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                card.style.transition = 'all 0.6s ease';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, index * 100);
        });
    }


    /**
     * Обновление статистики через API
     */
    async refreshStatistics() {
        if (!this.telegramId) {
            console.log('StatisticsManager: telegram_id не найден, пропускаем обновление');
            return;
        }

        try {
            console.log('StatisticsManager: Обновление статистики...');
            
            const response = await fetch(`/api/accounts/miniapp-users/statistics/?telegram_id=${this.telegramId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('StatisticsManager: Получены новые данные статистики:', data);
            
            // Обновляем отображение статистики
            this.updateStatisticsDisplay(data);
            
        } catch (error) {
            console.error('StatisticsManager: Ошибка при обновлении статистики:', error);
        }
    }

    /**
     * Обновление отображения статистики
     */
    updateStatisticsDisplay(data) {
        if (!data || !data.stats) {
            console.log('StatisticsManager: Нет данных для обновления');
            return;
        }

        // Обновляем основные показатели
        this.updateStatCard('.stat-card:nth-child(1) .stat-number', data.stats.total_quizzes || 0);
        this.updateStatCard('.stat-card:nth-child(2) .stat-number', data.stats.completed_quizzes || 0);
        this.updateStatCard('.stat-card:nth-child(3) .stat-number', `${data.stats.success_rate || 0}%`);
        this.updateStatCard('.stat-card:nth-child(4) .stat-number', data.stats.current_streak || 0);
        this.updateStatCard('.stat-card:nth-child(5) .stat-number', data.stats.best_streak || 0);


    }

    /**
     * Обновление отдельной карточки статистики
     */
    updateStatCard(selector, value) {
        const element = document.querySelector(selector);
        if (element) {
            // Анимация изменения числа
            this.animateNumberChange(element, value);
        }
    }

    /**
     * Анимация изменения числа
     */
    animateNumberChange(element, newValue) {
        const currentValue = parseInt(element.textContent) || 0;
        const targetValue = parseInt(newValue) || 0;
        
        if (currentValue === targetValue) return;

        const duration = 1000;
        const startTime = performance.now();

        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Используем easing функцию для плавной анимации
            const easeOutCubic = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(currentValue + (targetValue - currentValue) * easeOutCubic);
            
            element.textContent = current;
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };

        requestAnimationFrame(animate);
    }



}



// Глобальная функция для инициализации статистики
window.initStatistics = function() {
    console.log('📊 StatisticsManager: initStatistics called');
    console.log('📊 window.statisticsManagerInstance:', window.statisticsManagerInstance);
    console.log('📊 document.readyState:', document.readyState);
    
    // Проверяем, что мы на странице статистики
    const isStatisticsPage = window.location.pathname === '/statistics' || 
                             window.location.pathname.startsWith('/statistics');
    
    if (!isStatisticsPage) {
        console.log('⚠️ Not on statistics page, skipping initialization');
        return;
    }
    
    // Предотвращаем повторную инициализацию
    if (window.statisticsManagerInstance) {
        console.log('⚠️ StatisticsManager already initialized, skipping...');
        return;
    }
    
    console.log('🚀 Creating new StatisticsManager instance...');
    window.statisticsManagerInstance = new StatisticsManager();
};

// Проверяем состояние документа для автоинициализации
if (document.readyState === 'loading') {
    console.log('📊 StatisticsManager: DOM loading, adding DOMContentLoaded listener');
    document.addEventListener('DOMContentLoaded', window.initStatistics);
} else {
    console.log('📊 StatisticsManager: DOM already loaded, initializing immediately');
    window.initStatistics();
}

// Экспорт для использования в других модулях
window.StatisticsManager = StatisticsManager;
