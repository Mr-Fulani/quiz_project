/**
 * carousel.js - Модульный JavaScript для карусели тем
 * Поддерживает свайпы, кнопки управления, индикаторы и автопрокрутку
 */

class TopicCarousel {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            autoRotate: true,
            rotationSpeed: 20000, // 20 секунд на полный оборот
            swipeThreshold: 50, // минимальное расстояние для свайпа
            autoPlayDelay: 3000, // задержка автопрокрутки
            ...options
        };
        
        this.currentIndex = 0;
        this.isDragging = false;
        this.startX = 0;
        this.startY = 0;
        this.currentX = 0;
        this.currentY = 0;
        this.rotationAngle = 0;
        this.items = [];
        this.indicators = [];
        this.isPaused = false;
        this.autoPlayTimer = null;
        
        this.init();
    }
    
    init() {
        console.log('🚀 Initializing TopicCarousel...');
        
        // Получаем элементы
        this.container = document.querySelector('.carousel') || this.container;
        this.carouselContainer = this.container.querySelector('.carousel__container');
        this.items = Array.from(this.container.querySelectorAll('.carousel__item'));
        
        if (!this.container || !this.carouselContainer || this.items.length === 0) {
            console.error('❌ Carousel elements not found');
            return;
        }
        
        console.log(`✅ Found ${this.items.length} carousel items`);
        
        // Создаем элементы управления
        this.createControls();
        this.createIndicators();
        
        // Инициализируем события
        this.initEvents();
        
        // Запускаем автопрокрутку
        if (this.options.autoRotate) {
            this.startAutoPlay();
        }
        
        // Устанавливаем активный элемент
        this.setActiveItem(0);
        
        console.log('✅ TopicCarousel initialized successfully');
    }
    
    createControls() {
        // Создаем контейнер для кнопок управления
        const controlsContainer = document.createElement('div');
        controlsContainer.className = 'carousel__controls';
        
        // Кнопка "Предыдущая"
        const prevBtn = document.createElement('button');
        prevBtn.className = 'carousel__btn carousel__btn--prev';
        prevBtn.innerHTML = '<ion-icon name="chevron-back-outline"></ion-icon>';
        prevBtn.addEventListener('click', () => this.prev());
        
        // Кнопка "Следующая"
        const nextBtn = document.createElement('button');
        nextBtn.className = 'carousel__btn carousel__btn--next';
        nextBtn.innerHTML = '<ion-icon name="chevron-forward-outline"></ion-icon>';
        nextBtn.addEventListener('click', () => this.next());
        
        controlsContainer.appendChild(prevBtn);
        controlsContainer.appendChild(nextBtn);
        this.container.appendChild(controlsContainer);
        
        this.prevBtn = prevBtn;
        this.nextBtn = nextBtn;
    }
    
    createIndicators() {
        // Создаем контейнер для индикаторов
        const indicatorsContainer = document.createElement('div');
        indicatorsContainer.className = 'carousel__indicators';
        
        // Создаем индикаторы для каждой карточки
        this.items.forEach((_, index) => {
            const indicator = document.createElement('div');
            indicator.className = 'carousel__indicator';
            indicator.addEventListener('click', () => this.goTo(index));
            indicatorsContainer.appendChild(indicator);
            this.indicators.push(indicator);
        });
        
        this.container.appendChild(indicatorsContainer);
    }
    
    initEvents() {
        // События мыши
        this.carouselContainer.addEventListener('mousedown', (e) => this.startDrag(e));
        document.addEventListener('mousemove', (e) => this.drag(e));
        document.addEventListener('mouseup', () => this.endDrag());
        
        // События касания (для мобильных)
        this.carouselContainer.addEventListener('touchstart', (e) => this.startDrag(e));
        document.addEventListener('touchmove', (e) => this.drag(e));
        document.addEventListener('touchend', () => this.endDrag());
        
        // События клавиатуры
        document.addEventListener('keydown', (e) => this.handleKeydown(e));
        
        // События для паузы при наведении
        this.container.addEventListener('mouseenter', () => this.pause());
        this.container.addEventListener('mouseleave', () => this.resume());
        
        // События для карточек
        this.items.forEach((item, index) => {
            item.addEventListener('click', (e) => this.handleItemClick(e, index));
        });
    }
    
    startDrag(e) {
        e.preventDefault();
        
        this.isDragging = true;
        this.carouselContainer.classList.add('dragging');
        
        const point = e.touches ? e.touches[0] : e;
        this.startX = point.clientX;
        this.startY = point.clientY;
        this.currentX = this.startX;
        this.currentY = this.startY;
        
        // Останавливаем автопрокрутку
        this.pause();
        
        console.log('🖱️ Started dragging');
    }
    
    drag(e) {
        if (!this.isDragging) return;
        
        e.preventDefault();
        
        const point = e.touches ? e.touches[0] : e;
        this.currentX = point.clientX;
        this.currentY = point.clientY;
        
        // Вычисляем угол поворота на основе движения
        const deltaX = this.currentX - this.startX;
        const deltaY = this.currentY - this.startY;
        
        // Определяем направление свайпа
        if (Math.abs(deltaX) > Math.abs(deltaY)) {
            // Горизонтальный свайп
            const rotationDelta = (deltaX / window.innerWidth) * 360;
            this.rotationAngle = rotationDelta;
            
            // Применяем поворот
            this.carouselContainer.style.transform = `perspective(1000px) rotateY(${rotationDelta}deg)`;
        }
    }
    
    endDrag() {
        if (!this.isDragging) return;
        
        this.isDragging = false;
        this.carouselContainer.classList.remove('dragging');
        
        const deltaX = this.currentX - this.startX;
        const deltaY = this.currentY - this.startY;
        
        // Определяем, был ли это свайп
        if (Math.abs(deltaX) > this.options.swipeThreshold) {
            if (deltaX > 0) {
                this.prev();
            } else {
                this.next();
            }
        } else if (Math.abs(deltaY) > this.options.swipeThreshold) {
            // Вертикальный свайп - можно использовать для других действий
            console.log('📱 Vertical swipe detected');
        }
        
        // Возобновляем автопрокрутку
        this.resume();
        
        console.log('🖱️ Ended dragging');
    }
    
    handleKeydown(e) {
        switch (e.key) {
            case 'ArrowLeft':
                e.preventDefault();
                this.prev();
                break;
            case 'ArrowRight':
                e.preventDefault();
                this.next();
                break;
            case ' ':
                e.preventDefault();
                this.togglePlayPause();
                break;
        }
    }
    
    handleItemClick(e, index) {
        e.preventDefault();
        e.stopPropagation();
        
        console.log(`🎯 Item ${index} clicked`);
        
        // Получаем ID темы из data-атрибута
        const topicId = this.items[index].getAttribute('data-topic-id');
        if (topicId) {
            this.navigateToTopic(parseInt(topicId));
        }
    }
    
    navigateToTopic(topicId) {
        console.log(`🚀 Navigating to topic ${topicId}`);
        
        // Проверяем, запущено ли приложение в Telegram Web App
        function isTelegramWebApp() {
            return window.Telegram && window.Telegram.WebApp;
        }
        
        // Формируем URL с учетом текущего языка
        const currentLang = window.currentLanguage || 'en';
        const topicUrl = `/topic/${topicId}?lang=${currentLang}`;
        
        console.log('Navigating to:', topicUrl);
        
        // Если в Telegram Web App, используем Telegram API для навигации
        if (isTelegramWebApp()) {
            console.log('Using Telegram Web App navigation');
            window.Telegram.WebApp.navigateTo(topicUrl);
        } else {
            // Для обычного браузера используем стандартную навигацию
            console.log('Using standard browser navigation');
            window.location.href = topicUrl;
        }
    }
    
    prev() {
        this.currentIndex = (this.currentIndex - 1 + this.items.length) % this.items.length;
        this.updateCarousel();
        this.setActiveItem(this.currentIndex);
    }
    
    next() {
        this.currentIndex = (this.currentIndex + 1) % this.items.length;
        this.updateCarousel();
        this.setActiveItem(this.currentIndex);
    }
    
    goTo(index) {
        if (index >= 0 && index < this.items.length) {
            this.currentIndex = index;
            this.updateCarousel();
            this.setActiveItem(this.currentIndex);
        }
    }
    
    updateCarousel() {
        // Вычисляем угол поворота для текущего индекса
        const angle = (this.currentIndex * 360) / this.items.length;
        
        // Применяем поворот с анимацией
        this.carouselContainer.style.transition = 'transform 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
        this.carouselContainer.style.transform = `perspective(1000px) rotateY(${angle}deg)`;
        
        // Обновляем индикаторы
        this.updateIndicators();
        
        console.log(`🔄 Carousel updated to index ${this.currentIndex}`);
    }
    
    setActiveItem(index) {
        // Убираем активный класс со всех элементов
        this.items.forEach(item => item.classList.remove('active'));
        
        // Добавляем активный класс к текущему элементу
        if (this.items[index]) {
            this.items[index].classList.add('active');
        }
        
        // Обновляем индикаторы
        this.updateIndicators();
    }
    
    updateIndicators() {
        this.indicators.forEach((indicator, index) => {
            if (index === this.currentIndex) {
                indicator.classList.add('active');
            } else {
                indicator.classList.remove('active');
            }
        });
    }
    
    startAutoPlay() {
        if (this.autoPlayTimer) {
            clearInterval(this.autoPlayTimer);
        }
        
        this.autoPlayTimer = setInterval(() => {
            if (!this.isPaused && !this.isDragging) {
                this.next();
            }
        }, this.options.autoPlayDelay);
        
        console.log('▶️ Auto-play started');
    }
    
    stopAutoPlay() {
        if (this.autoPlayTimer) {
            clearInterval(this.autoPlayTimer);
            this.autoPlayTimer = null;
        }
        
        console.log('⏸️ Auto-play stopped');
    }
    
    pause() {
        this.isPaused = true;
        this.carouselContainer.classList.add('paused');
        console.log('⏸️ Carousel paused');
    }
    
    resume() {
        this.isPaused = false;
        this.carouselContainer.classList.remove('paused');
        console.log('▶️ Carousel resumed');
    }
    
    togglePlayPause() {
        if (this.isPaused) {
            this.resume();
        } else {
            this.pause();
        }
    }
    
    destroy() {
        // Очищаем все события и таймеры
        this.stopAutoPlay();
        
        // Удаляем элементы управления
        const controls = this.container.querySelector('.carousel__controls');
        const indicators = this.container.querySelector('.carousel__indicators');
        
        if (controls) controls.remove();
        if (indicators) indicators.remove();
        
        console.log('🗑️ Carousel destroyed');
    }
    
    // Публичные методы для внешнего управления
    getCurrentIndex() {
        return this.currentIndex;
    }
    
    getItemsCount() {
        return this.items.length;
    }
    
    isPlaying() {
        return !this.isPaused;
    }
}

// Глобальная функция для инициализации карусели
window.initTopicCarousel = function(container, options) {
    return new TopicCarousel(container, options);
};

// Автоматическая инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    const carouselContainer = document.querySelector('.carousel');
    if (carouselContainer) {
        console.log('🎠 Auto-initializing carousel...');
        window.topicCarousel = new TopicCarousel(carouselContainer, {
            autoRotate: true,
            rotationSpeed: 20000,
            swipeThreshold: 50,
            autoPlayDelay: 4000
        });
    }
});

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TopicCarousel;
} 