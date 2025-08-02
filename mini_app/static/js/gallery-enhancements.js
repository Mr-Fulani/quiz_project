/**
 * gallery-enhancements.js - Улучшения для существующей галереи
 * Добавляет поддержку свайпов и улучшенную интерактивность
 */

class GalleryEnhancements {
    constructor() {
        this.gallery = null;
        this.container = null;
        this.isDragging = false;
        this.startX = 0;
        this.startY = 0;
        this.currentX = 0;
        this.currentY = 0;
        this.swipeThreshold = 50;
        this.currentRotation = 0; // Текущий угол поворота карусели
        this.rotationStep = 45; // Шаг поворота в градусах (360 / 8 карточек = 45)
        this.init();
    }
    
    init() {
        console.log('🎨 Initializing Gallery Enhancements...');
        
        // Ждем загрузки DOM
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupGallery());
        } else {
            this.setupGallery();
        }
    }
    
    setupGallery() {
        this.gallery = document.querySelector('.gallery');
        this.container = document.querySelector('.gallery__container');
        
        if (!this.gallery || !this.container) {
            console.log('❌ Gallery elements not found, skipping enhancements');
            return;
        }
        
        console.log('✅ Gallery found, adding enhancements...');
        
        // Отключаем автоматическую анимацию
        this.container.style.animation = 'none';
        
        // Добавляем поддержку свайпов
        this.addSwipeSupport();
        
        // Добавляем индикаторы
        this.addIndicators();
        
        // Добавляем кнопки управления
        this.addControls();
        
        // Добавляем эффекты при наведении
        this.addHoverEffects();
        
        // Устанавливаем начальное положение карусели
        this.rotateCarousel(this.currentRotation);
        this.updateActiveCard();
        
        console.log('✅ Gallery enhancements added successfully');
    }
    
    addSwipeSupport() {
        // События мыши
        this.container.addEventListener('mousedown', (e) => this.startDrag(e));
        document.addEventListener('mousemove', (e) => this.drag(e));
        document.addEventListener('mouseup', () => this.endDrag());
        
        // События касания (для мобильных)
        this.container.addEventListener('touchstart', (e) => this.startDrag(e));
        document.addEventListener('touchmove', (e) => this.drag(e));
        document.addEventListener('touchend', () => this.endDrag());
        
        console.log('📱 Swipe support added');
    }
    
    startDrag(e) {
        e.preventDefault();
        
        this.isDragging = true;
        this.container.style.cursor = 'grabbing';
        
        const point = e.touches ? e.touches[0] : e;
        this.startX = point.clientX;
        this.startY = point.clientY;
        this.currentX = this.startX;
        this.currentY = this.startY;
        
        // Останавливаем автопрокрутку
        this.pauseGallery();
        
        console.log('🖱️ Started dragging');
    }
    
    drag(e) {
        if (!this.isDragging) return;
        
        e.preventDefault();
        
        const point = e.touches ? e.touches[0] : e;
        this.currentX = point.clientX;
        this.currentY = point.clientY;
        
        // Показываем реальное вращение во время перетаскивания
        const deltaX = this.currentX - this.startX;
        if (Math.abs(deltaX) > 10) {
            // Временно убираем transition для плавного перетаскивания
            this.container.style.transition = 'none';
            const tempRotation = this.currentRotation + (deltaX * 0.1);
            this.container.style.transform = `perspective(1000px) rotateY(${tempRotation}deg)`;
        }
    }
    
    endDrag() {
        if (!this.isDragging) return;
        
        this.isDragging = false;
        this.container.style.cursor = 'grab';
        
        const deltaX = this.currentX - this.startX;
        const deltaY = this.currentY - this.startY;
        
        // Определяем, был ли это свайп
        if (Math.abs(deltaX) > this.swipeThreshold) {
            if (deltaX > 0) {
                this.swipeLeft();
            } else {
                this.swipeRight();
            }
        } else {
            // Если свайп был недостаточным, возвращаемся к текущему положению
            this.rotateCarousel(this.currentRotation);
        }
        
        if (Math.abs(deltaY) > this.swipeThreshold) {
            console.log('📱 Vertical swipe detected');
        }
        
        // Возобновляем автопрокрутку
        this.resumeGallery();
        
        console.log('🖱️ Ended dragging');
    }
    
    swipeLeft() {
        console.log('⬅️ Swipe left detected - rotating carousel left');
        // Поворачиваем карусель влево (по часовой стрелке)
        this.currentRotation += this.rotationStep;
        this.rotateCarousel(this.currentRotation);
        this.updateActiveCard();
        this.showSwipeFeedback('left');
    }
    
    swipeRight() {
        console.log('➡️ Swipe right detected - rotating carousel right');
        // Поворачиваем карусель вправо (против часовой стрелки)
        this.currentRotation -= this.rotationStep;
        this.rotateCarousel(this.currentRotation);
        this.updateActiveCard();
        this.showSwipeFeedback('right');
    }
    
    rotateCarousel(angle) {
        if (this.container) {
            // Применяем поворот с плавной анимацией
            this.container.style.transition = 'transform 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
            this.container.style.transform = `perspective(1000px) rotateY(${angle}deg)`;
            
            console.log(`🔄 Carousel rotated to ${angle} degrees`);
            console.log(`📍 Container transform: ${this.container.style.transform}`);
        } else {
            console.error('❌ Container not found for rotation');
        }
    }
    
    showSwipeFeedback(direction) {
        // Создаем временный элемент для обратной связи
        const feedback = document.createElement('div');
        feedback.className = `swipe-feedback swipe-${direction}`;
        feedback.innerHTML = direction === 'left' ? '⬅️' : '➡️';
        feedback.style.cssText = `
            position: fixed;
            top: 50%;
            ${direction === 'left' ? 'left' : 'right'}: 20px;
            transform: translateY(-50%);
            font-size: 48px;
            color: var(--active-color);
            z-index: 1000;
            animation: swipeFeedback 0.5s ease-out forwards;
        `;
        
        document.body.appendChild(feedback);
        
        // Удаляем через 500ms
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.parentNode.removeChild(feedback);
            }
        }, 500);
    }
    
    addIndicators() {
        const indicatorsContainer = document.createElement('div');
        indicatorsContainer.className = 'gallery__indicators';
        
        const topicCards = document.querySelectorAll('.topic-card');
        topicCards.forEach((_, index) => {
            const indicator = document.createElement('div');
            indicator.className = 'gallery__indicator';
            if (index === 0) indicator.classList.add('active');
            
            indicator.addEventListener('click', () => {
                this.goToCard(index);
            });
            
            indicatorsContainer.appendChild(indicator);
        });
        
        this.gallery.appendChild(indicatorsContainer);
        
        // Добавляем отладочную информацию
        console.log('🔘 Indicators added');
        console.log('📍 Indicators container:', indicatorsContainer);
        console.log('📍 Indicators count:', topicCards.length);
        
        // Принудительно устанавливаем стили
        indicatorsContainer.style.position = 'absolute';
        indicatorsContainer.style.bottom = '-120px';
        indicatorsContainer.style.left = '50%';
        indicatorsContainer.style.transform = 'translateX(-50%)';
        indicatorsContainer.style.zIndex = '9999';
        indicatorsContainer.style.display = 'flex';
        indicatorsContainer.style.gap = '8px';
        indicatorsContainer.style.background = 'rgba(0, 0, 0, 0.7)';
        indicatorsContainer.style.padding = '10px 15px';
        indicatorsContainer.style.borderRadius = '25px';
        indicatorsContainer.style.backdropFilter = 'blur(15px)';
        indicatorsContainer.style.border = '1px solid rgba(0, 255, 0, 0.2)';
        indicatorsContainer.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.5)';
        
        // Принудительно устанавливаем стили для индикаторов
        const indicators = indicatorsContainer.querySelectorAll('.gallery__indicator');
        indicators.forEach((indicator, index) => {
            indicator.style.width = '12px';
            indicator.style.height = '12px';
            indicator.style.borderRadius = '50%';
            indicator.style.background = index === 0 ? '#00ff00' : 'rgba(0, 255, 0, 0.6)';
            indicator.style.cursor = 'pointer';
            indicator.style.transition = 'all 0.3s ease';
            indicator.style.border = '2px solid rgba(0, 255, 0, 0.4)';
            indicator.style.boxShadow = index === 0 ? '0 0 20px rgba(0, 255, 0, 0.8)' : '0 0 10px rgba(0, 255, 0, 0.3)';
        });
        
        console.log('🔘 Indicators styles applied');
    }
    
    addControls() {
        const controlsContainer = document.createElement('div');
        controlsContainer.className = 'gallery__controls';
        
        // Кнопка "Предыдущая"
        const prevBtn = document.createElement('button');
        prevBtn.className = 'gallery__btn gallery__btn--prev';
        prevBtn.innerHTML = '←';
        prevBtn.addEventListener('click', () => this.prevCard());
        
        // Кнопка "Следующая"
        const nextBtn = document.createElement('button');
        nextBtn.className = 'gallery__btn gallery__btn--next';
        nextBtn.innerHTML = '→';
        nextBtn.addEventListener('click', () => this.nextCard());
        
        controlsContainer.appendChild(prevBtn);
        controlsContainer.appendChild(nextBtn);
        this.gallery.appendChild(controlsContainer);
        
        // Добавляем отладочную информацию
        console.log('🎛️ Controls added');
        console.log('📍 Controls container:', controlsContainer);
        console.log('📍 Controls position:', controlsContainer.style.position);
        console.log('📍 Controls z-index:', controlsContainer.style.zIndex);
        console.log('📍 Controls bottom:', controlsContainer.style.bottom);
        
        // Принудительно устанавливаем стили
        controlsContainer.style.position = 'absolute';
        controlsContainer.style.bottom = '-80px';
        controlsContainer.style.left = '50%';
        controlsContainer.style.transform = 'translateX(-50%)';
        controlsContainer.style.zIndex = '9999';
        controlsContainer.style.display = 'flex';
        controlsContainer.style.justifyContent = 'space-between';
        controlsContainer.style.width = '200px';
        controlsContainer.style.pointerEvents = 'none';
        
        // Принудительно устанавливаем стили для кнопок
        [prevBtn, nextBtn].forEach(btn => {
            btn.style.width = '50px';
            btn.style.height = '50px';
            btn.style.borderRadius = '50%';
            btn.style.background = '#000000';
            btn.style.border = '3px solid #00ff00';
            btn.style.color = '#00ff00';
            btn.style.cursor = 'pointer';
            btn.style.display = 'flex';
            btn.style.alignItems = 'center';
            btn.style.justifyContent = 'center';
            btn.style.fontSize = '20px';
            btn.style.fontWeight = 'bold';
            btn.style.boxShadow = '0 0 20px rgba(0, 255, 0, 0.8), 0 8px 24px rgba(0, 0, 0, 0.8)';
            btn.style.pointerEvents = 'auto';
            btn.style.zIndex = '9999';
        });
        
        console.log('🎛️ Controls styles applied');
    }
    
    addHoverEffects() {
        const topicCards = document.querySelectorAll('.topic-card');
        
        topicCards.forEach((card, index) => {
            // Добавляем эффект пульсации для первой карточки
            if (index === 0) {
                setTimeout(() => {
                    card.classList.add('pulse');
                    setTimeout(() => card.classList.remove('pulse'), 2000);
                }, 1000);
            }
            
            // Улучшенные эффекты при наведении
            card.addEventListener('mouseenter', () => {
                this.pauseGallery();
                card.style.transform = 'scale(1.05) translateZ(20px)';
            });
            
            card.addEventListener('mouseleave', () => {
                this.resumeGallery();
                card.style.transform = '';
            });
        });
        
        console.log('✨ Hover effects added');
    }
    
    goToCard(index) {
        const topicCards = document.querySelectorAll('.topic-card');
        
        if (index >= 0 && index < topicCards.length) {
            // Вычисляем нужный угол поворота для этой карточки
            this.currentRotation = -index * this.rotationStep;
            this.rotateCarousel(this.currentRotation);
            this.updateActiveCard();
            
            console.log(`🎯 Navigated to card ${index} with rotation ${this.currentRotation} degrees`);
        }
    }
    
    prevCard() {
        console.log('⬅️ Previous button clicked - rotating carousel left');
        this.currentRotation += this.rotationStep;
        this.rotateCarousel(this.currentRotation);
        this.updateActiveCard();
    }
    
    nextCard() {
        console.log('➡️ Next button clicked - rotating carousel right');
        this.currentRotation -= this.rotationStep;
        this.rotateCarousel(this.currentRotation);
        this.updateActiveCard();
    }
    
    updateActiveCard() {
        // Вычисляем, какая карточка должна быть активной на основе угла поворота
        const topicCards = document.querySelectorAll('.topic-card');
        const indicators = document.querySelectorAll('.gallery__indicator');
        
        // Нормализуем угол до 0-360 градусов
        const normalizedAngle = ((this.currentRotation % 360) + 360) % 360;
        
        // Вычисляем индекс активной карточки
        const cardIndex = Math.round(normalizedAngle / this.rotationStep) % topicCards.length;
        
        // Убираем активный класс со всех элементов
        topicCards.forEach(card => card.classList.remove('selected'));
        indicators.forEach(indicator => indicator.classList.remove('active'));
        
        // Добавляем активный класс к выбранному элементу
        if (topicCards[cardIndex]) {
            topicCards[cardIndex].classList.add('selected');
        }
        if (indicators[cardIndex]) {
            indicators[cardIndex].classList.add('active');
        }
        
        console.log(`🎯 Active card updated to index ${cardIndex}`);
    }
    
    pauseGallery() {
        // Анимация уже отключена, поэтому просто логируем
        console.log('⏸️ Gallery paused (animation disabled)');
    }
    
    resumeGallery() {
        // Анимация уже отключена, поэтому просто логируем
        console.log('▶️ Gallery resumed (animation disabled)');
    }
}

// Добавляем CSS для анимации обратной связи
const style = document.createElement('style');
style.textContent = `
    @keyframes swipeFeedback {
        0% {
            opacity: 0;
            transform: translateY(-50%) scale(0.5);
        }
        50% {
            opacity: 1;
            transform: translateY(-50%) scale(1.2);
        }
        100% {
            opacity: 0;
            transform: translateY(-50%) scale(1);
        }
    }
    
    .gallery__container {
        cursor: grab;
    }
    
    .gallery__container:active {
        cursor: grabbing;
    }
`;
document.head.appendChild(style);

// Инициализируем улучшения
console.log('🚀 Starting Gallery Enhancements initialization...');
window.galleryEnhancements = new GalleryEnhancements();

console.log('🎨 Gallery Enhancements script loaded');
console.log('🔍 Check browser console for detailed logs'); 