// topic-cards.js
// Обработка карточек тем с увеличением на месте

document.addEventListener('DOMContentLoaded', function() {
    console.log('Topic cards script loaded');
    
    // Получаем элементы галереи
    const gallery = document.querySelector('.gallery');
    const galleryContainer = document.querySelector('.gallery__container');
    const topicCards = document.querySelectorAll('.topic-card');
    
    let selectedCard = null;
    let selectedCardOverlay = null;
    
    // Создаем overlay при инициализации
    createSelectedCardOverlay();
    
    // Переменные для свайпа
    let swipeSound = document.getElementById('swipe-sound');
    let startX = 0;
    let startY = 0;
    let startTime = 0;
    
    // Добавляем touch события для свайпа на всю галерею
    gallery.addEventListener('touchstart', function(e) {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        startTime = Date.now();
    }, { passive: true });
    
    gallery.addEventListener('touchend', function(e) {
        if (selectedCard) return;
        
        const endX = e.changedTouches[0].clientX;
        const endY = e.changedTouches[0].clientY;
        
        const deltaX = endX - startX;
        const deltaY = endY - startY;
        
        // СУПЕР отзывчивый свайп - минимум 20px движения
        if (Math.abs(deltaX) > 20 && Math.abs(deltaX) > Math.abs(deltaY)) {
            rotateCarousel(deltaX > 0 ? 'right' : 'left');
        }
    }, { passive: true });
    
    // Добавляем клавиатурное управление для десктопа
    document.addEventListener('keydown', handleKeyPress);
    
    // Создаем overlay для увеличенной карточки
    function createSelectedCardOverlay() {
        if (selectedCardOverlay) return selectedCardOverlay;
        
        selectedCardOverlay = document.createElement('div');
        selectedCardOverlay.className = 'selected-card-overlay';
        selectedCardOverlay.innerHTML = `
            <div class="selected-card-container">
                <!-- Содержимое будет вставлено динамически -->
            </div>
        `;
        
        // Закрытие по клику на фон
        selectedCardOverlay.addEventListener('click', function(e) {
            if (e.target === selectedCardOverlay) {
                goBack();
            }
        });
        
        document.body.appendChild(selectedCardOverlay);
        return selectedCardOverlay;
    }
    
    // Функция поворота карусели
    function rotateCarousel(direction) {
        if (selectedCard) return;
        
        // Останавливаем автоматическое вращение МГНОВЕННО
        gallery.classList.add('manual-control');
        
        // Поворачиваем на один шаг (45 градусов) с БЫСТРОЙ анимацией
        const currentTransform = galleryContainer.style.transform || 'perspective(1000px) rotateY(0deg)';
        const currentAngle = parseFloat(currentTransform.match(/rotateY\(([^)]+)deg\)/)?.[1] || 0);
        const newAngle = direction === 'left' ? currentAngle - 45 : currentAngle + 45;
        
        // МГНОВЕННЫЙ поворот с быстрой анимацией
        galleryContainer.style.transition = 'transform 0.15s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
        galleryContainer.style.transform = `perspective(1000px) rotateY(${newAngle}deg)`;
        
        // Проигрываем звук
        playSwipeSound();
        
        // Вибрация
        if ('vibrate' in navigator) {
            navigator.vibrate(30); // Короткая вибрация
        }
        
        // Возобновляем автоматическое вращение через 5 секунд (дольше)
        setTimeout(() => {
            if (!selectedCard) {
                gallery.classList.remove('manual-control');
                galleryContainer.style.transform = '';
                galleryContainer.style.transition = '';
            }
        }, 5000);
    }
    
    // Функция обработки клавиатуры
    function handleKeyPress(e) {
        if (selectedCard) {
            if (e.key === 'Escape') {
                goBack();
            }
            return;
        }
        
        // Стрелки влево/вправо для поворота карусели
        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            rotateCarousel('left');
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            rotateCarousel('right');
        }
    }
    

    
    // Функция воспроизведения звука свайпа
    function playSwipeSound() {
        if (swipeSound) {
            swipeSound.currentTime = 0;
            swipeSound.play().catch(e => console.log('Audio play failed:', e));
        }
    }
    
    // Добавляем обработчики для каждой карточки
    topicCards.forEach(card => {
        // Обработка клика на карточку
        card.addEventListener('click', function(e) {
            // Если клик был на кнопке - игнорируем
            if (e.target.tagName === 'BUTTON') {
                return;
            }
            
            e.preventDefault();
            e.stopPropagation();
            
            const topicId = this.getAttribute('data-topic-id');
            console.log(`Clicked on topic card with ID: ${topicId}`);
            
            // Если карточка уже выбрана - ничего не делаем
            if (this.classList.contains('selected')) {
                return;
            }
            
            // Выбираем карточку
            selectCard(this);
        });
        
        // Обработка наведения мыши - останавливаем галерею
        card.addEventListener('mouseenter', function() {
            if (!selectedCard) {
                pauseGallery();
            }
        });
        
        card.addEventListener('mouseleave', function() {
            if (!selectedCard) {
                setTimeout(() => {
                    if (!selectedCard) {
                        resumeGallery();
                    }
                }, 500);
            }
        });
    });
    

    
    // Функции управления
    function selectCard(card) {
        console.log('Selecting card:', card.getAttribute('data-topic-id'));
        
        // Убираем предыдущий выбор
        if (selectedCard) {
            selectedCard.classList.remove('selected');
        }
        
        // Выбираем новую карточку
        selectedCard = card;
        
        // Останавливаем галерею
        pauseGallery();
        
        // Добавляем класс выбора к оригинальной карточке (делает её полупрозрачной)
        card.classList.add('selected');
        galleryContainer.classList.add('has-selection');
        
        // Создаем overlay и показываем увеличенную версию
        const overlay = createSelectedCardOverlay();
        const container = overlay.querySelector('.selected-card-container');
        
        // Копируем содержимое карточки
        const img = card.querySelector('img');
        const cardOverlay = card.querySelector('.card-overlay');
        
        container.innerHTML = `
            <img src="${img.src}" alt="${img.alt}" style="width: 100%; height: 100%; object-fit: cover;">
            ${cardOverlay.outerHTML}
        `;
        
        // Показываем overlay
        setTimeout(() => {
            overlay.classList.add('active');
        }, 50);
        
        // Вибрация для мобильных устройств
        if ('vibrate' in navigator) {
            navigator.vibrate(100);
        }
        
        console.log('Card selected successfully');
    }
    
    function goBack() {
        console.log('Going back from selected card');
        
        // Скрываем overlay
        if (selectedCardOverlay) {
            selectedCardOverlay.classList.remove('active');
        }
        
        // Убираем выбор с карточки
        if (selectedCard) {
            selectedCard.classList.remove('selected');
            selectedCard = null;
        }
        
        galleryContainer.classList.remove('has-selection');
        
        // Возобновляем галерею с того же места
        resumeGallery();
        
        console.log('Returned to gallery');
    }
    
    function pauseGallery() {
        console.log('Pausing gallery');
        gallery.classList.add('paused');
    }
    
    function resumeGallery() {
        console.log('Resuming gallery');
        gallery.classList.remove('paused');
    }
    
    function navigateToTopic(topicId) {
        console.log(`Navigating to topic: ${topicId}`);
        
        // Вибрация
        if ('vibrate' in navigator) {
            navigator.vibrate(200);
        }
        
        // Плавное затухание
        if (selectedCard) {
            selectedCard.style.opacity = '0.7';
        }
        
        setTimeout(() => {
            window.location.href = `/topic/${topicId}`;
        }, 300);
    }
    
    // Экспортируем функции для использования в HTML
    window.selectCard = selectCard;
    window.goBack = function(event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        goBack();
    };
    window.startTopic = function(event, topicId) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        navigateToTopic(topicId);
    };
    
    // Объект для управления галереей
    window.galleryController = {
        selectCard,
        goBack,
        pauseGallery,
        resumeGallery,
        navigateToTopic,
        // Диагностическая функция
        debug: function() {
            console.log('=== Gallery Debug Info ===');
            console.log('Selected card:', selectedCard?.getAttribute('data-topic-id') || 'none');
            console.log('Gallery classes:', gallery?.className);
            console.log('Gallery container classes:', galleryContainer?.className);
            console.log('========================');
        }
    };
    
    console.log('Gallery controller initialized');
    console.log('Используйте window.galleryController.debug() для диагностики');
});

// Функция для загрузки данных темы через API
async function loadTopicData(topicId) {
    try {
        const response = await fetch(`/api/topic/${topicId}`);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error loading topic data:', error);
        return null;
    }
} 