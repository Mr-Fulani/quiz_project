// topic-cards.js
// Обработка карточек тем с увеличением на месте

function initTopicCards() {
    console.log('Topic cards script initialized');
    
    // Получаем элементы галереи
    const gallery = document.querySelector('.gallery');
    const galleryContainer = document.querySelector('.gallery__container');
    const topicCards = document.querySelectorAll('.topic-card');
    
    if (!gallery || !galleryContainer || topicCards.length === 0) {
        console.log('Gallery elements not found, skipping initialization');
        return;
    }
    
    let selectedCard = null;
    let selectedCardOverlay = null;
    
    // Создаем overlay при инициализации
    createSelectedCardOverlay();
    
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
    
    // Добавляем клавиатурное управление только для Escape
    document.addEventListener('keydown', function(e) {
        if (selectedCard && e.key === 'Escape') {
            goBack();
        }
    });

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
        
        // Обработка наведения мыши - останавливаем галерею только на десктопе
        card.addEventListener('mouseenter', function() {
            if (!selectedCard && !('ontouchstart' in window)) {
                pauseGallery();
            }
        });
        
        card.addEventListener('mouseleave', function() {
            if (!selectedCard && !('ontouchstart' in window)) {
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
}

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

// Экспортируем функцию глобально для доступа из других скриптов
window.initTopicCards = initTopicCards;

// Инициализируем при загрузке страницы
document.addEventListener('DOMContentLoaded', initTopicCards); 