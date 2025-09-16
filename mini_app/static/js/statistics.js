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
        
        // Анимация прогресс-баров
        this.animateProgressBars();
        
        
        
        // Обновление статистики каждые 30 секунд
        if (this.telegramId) {
            setInterval(() => this.refreshStatistics(), 30000);
        }
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
     * Анимация прогресс-баров
     */
    animateProgressBars() {
        const progressBars = document.querySelectorAll('.progress-fill');
        progressBars.forEach((bar, index) => {
            const width = bar.style.width;
            bar.style.width = '0%';
            
            setTimeout(() => {
                bar.style.transition = 'width 1.2s ease';
                bar.style.width = width;
            }, 500 + (index * 200));
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

        // Обновляем прогресс по темам
        if (data.topic_progress && data.topic_progress.length > 0) {
            this.updateTopicProgress(data.topic_progress);
        }

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

    /**
     * Обновление прогресса по темам
     */
    updateTopicProgress(topicProgress) {
        const container = document.querySelector('.topic-progress-list');
        if (!container) return;

        // Очищаем существующий контент
        container.innerHTML = '';

        topicProgress.forEach(topic => {
            const item = document.createElement('div');
            item.className = 'topic-progress-item';
            item.innerHTML = `
                <div class="topic-name">${topic.name}</div>
                <div class="topic-stats">
                    <span class="topic-completed">${topic.completed}</span>
                    <span class="topic-separator">/</span>
                    <span class="topic-total">${topic.total}</span>
                    <span class="topic-percentage">(${topic.percentage}%)</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${topic.percentage}%"></div>
                </div>
            `;
            container.appendChild(item);
        });

        // Анимируем новые прогресс-бары
        setTimeout(() => this.animateProgressBars(), 100);
    }


}



// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    console.log('StatisticsManager: DOMContentLoaded - Загрузка страницы статистики');
    
    // Проверяем, что мы на странице статистики
    if (window.location.pathname === '/statistics') {
        console.log('StatisticsManager: Создание StatisticsManager');
        const statisticsManager = new StatisticsManager();
        statisticsManager.init();
    }
});

// Глобальная функция для инициализации статистики (вызывается из base.html)
window.initStatistics = function() {
    console.log('StatisticsManager: initStatistics вызван');
    const statisticsManager = new StatisticsManager();
    statisticsManager.init();
};

// Экспорт для использования в других модулях
window.StatisticsManager = StatisticsManager;
