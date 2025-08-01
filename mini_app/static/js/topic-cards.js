/**
 * Управление карточками тем на главной странице
 */

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    initTopicCards();
});

// Также инициализируем, если DOM уже загружен
if (document.readyState === 'loading') {
    // DOM еще загружается, ждем события DOMContentLoaded
} else {
    initTopicCards();
}

function initTopicCards() {
    // Сбрасываем предыдущее состояние
    resetGalleryState();
    
    // Проверяем наличие необходимых элементов
    const gallery = document.querySelector('.gallery');
    const galleryContainer = document.querySelector('.gallery-container');
    const topicCards = document.querySelectorAll('.topic-card');
    
    if (!gallery || !galleryContainer || topicCards.length === 0) {
        return;
    }
    
    // Настраиваем обработчики событий
    setupGalleryHandlers(gallery, topicCards);
    setupHoverHandlers(gallery);
}

function resetGalleryState() {
    // Убираем выделение с карточек
    const selectedCards = document.querySelectorAll('.topic-card.selected');
    selectedCards.forEach(card => {
        card.classList.remove('selected');
    });
    
    // Убираем overlay
    const overlays = document.querySelectorAll('.selected-card-overlay');
    overlays.forEach(overlay => overlay.remove());
}

function setupGalleryHandlers(gallery, topicCards) {
    // Удаляем старый обработчик, если есть
    gallery.removeEventListener('click', handleGalleryClick);
    
    // Добавляем новый обработчик с делегированием
    gallery.addEventListener('click', handleGalleryClick);
}

function handleGalleryClick(e) {
    // Проверяем, что клик был по карточке
    const clickedCard = e.target.closest('.topic-card');
    if (!clickedCard) {
        return;
    }
    
    // Игнорируем клики по кнопкам
    if (e.target.closest('.card-button')) {
        return;
    }
    
    const topicId = clickedCard.getAttribute('data-topic-id');
    if (!topicId) {
        return;
    }
    
    // Проверяем, не выбрана ли уже карточка
    if (clickedCard.classList.contains('selected')) {
        return;
    }
    
    // Выбираем карточку
    selectCard(clickedCard, topicId);
}

function setupHoverHandlers(gallery) {
    // Добавляем обработчики наведения для карточек
    const cards = gallery.querySelectorAll('.topic-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', () => pauseGallery());
        card.addEventListener('mouseleave', () => resumeGallery());
    });
}

function selectCard(card, topicId) {
    // Убираем выделение с других карточек
    const otherCards = document.querySelectorAll('.topic-card.selected');
    otherCards.forEach(otherCard => {
        if (otherCard !== card) {
            otherCard.classList.remove('selected');
        }
    });
    
    // Выбираем текущую карточку
    card.classList.add('selected');
    
    // Создаем overlay с кнопками
    createCardOverlay(card, topicId);
}

function createCardOverlay(card, topicId) {
    // Удаляем существующий overlay
    const existingOverlay = document.querySelector('.selected-card-overlay');
    if (existingOverlay) {
        existingOverlay.remove();
    }
    
    // Создаем новый overlay
    const overlay = document.createElement('div');
    overlay.className = 'selected-card-overlay';
    overlay.innerHTML = `
        <div class="selected-card-container">
            <div class="selected-card-content">
                <h3>${card.querySelector('.card-title').textContent}</h3>
                <p>${card.querySelector('.card-description').textContent}</p>
                <div class="selected-card-buttons">
                    <button class="card-button start-button" onclick="handleStartTopic(${topicId})">
                        Начать
                    </button>
                    <button class="card-button back-button" onclick="goBackFromCard()">
                        Назад
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(overlay);
}

function goBackFromCard() {
    // Убираем выделение с карточек
    const selectedCards = document.querySelectorAll('.topic-card.selected');
    selectedCards.forEach(card => {
        card.classList.remove('selected');
    });
    
    // Удаляем overlay
    const overlay = document.querySelector('.selected-card-overlay');
    if (overlay) {
        overlay.remove();
    }
}

function handleStartTopic(topicId) {
    // Переходим на страницу темы
    const url = `/topic/${topicId}`;
    
    // Пытаемся загрузить страницу через AJAX
    loadTopicPage(url);
}

function loadTopicPage(url) {
    const contentContainer = document.getElementById('content-container');
    if (!contentContainer) {
        // Если контейнер не найден, используем обычную навигацию
        window.location.href = url;
        return;
    }
    
    // Показываем индикатор загрузки
    contentContainer.innerHTML = '<div class="loading">Загрузка...</div>';
    
    // Загружаем страницу
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.text();
        })
        .then(html => {
            // Парсим HTML и извлекаем контент
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newContent = doc.getElementById('content-container');
            
            if (newContent) {
                contentContainer.innerHTML = newContent.innerHTML;
                
                // Обновляем URL без перезагрузки страницы
                window.history.pushState({}, '', url);
                
                // Загружаем скрипт для страницы темы
                loadTopicDetailScript();
                
                // Переинициализируем карточки тем
                resetGalleryState();
            } else {
                // Если контент не найден, используем обычную навигацию
                window.location.href = url;
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки страницы:', error);
            // При ошибке используем обычную навигацию
            window.location.href = url;
        });
}

function loadTopicDetailScript() {
    // Проверяем, не загружен ли уже скрипт
    if (document.querySelector('script[src*="topic-detail.js"]')) {
        return;
    }
    
    // Загружаем скрипт для страницы темы
    const script = document.createElement('script');
    script.src = '/static/js/topic-detail.js?v=1.5';
    script.onload = function() {
        // Скрипт загружен успешно
    };
    script.onerror = function() {
        console.error('Ошибка загрузки topic-detail.js');
    };
    document.head.appendChild(script);
}

function pauseGallery() {
    // Приостанавливаем анимацию галереи
    const gallery = document.querySelector('.gallery');
    if (gallery) {
        gallery.style.animationPlayState = 'paused';
    }
}

function resumeGallery() {
    // Возобновляем анимацию галереи
    const gallery = document.querySelector('.gallery');
    if (gallery) {
        gallery.style.animationPlayState = 'running';
    }
}

// Глобальные функции для использования в HTML
window.handleStartTopic = handleStartTopic;
window.goBackFromCard = goBackFromCard;
window.selectCard = selectCard; 