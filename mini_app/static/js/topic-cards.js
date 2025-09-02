// topic-cards.js
// Обработка карточек тем с увеличением на месте

console.log('🔥 TOPIC-CARDS.JS LOADED!');
console.log('Current page URL:', window.location.href);
console.log('DOM ready state:', document.readyState);

function initTopicCards() {
    console.log('🚀 Topic cards script initialized');
    
    // Проверяем DOM
    console.log('DOM ready state:', document.readyState);
    console.log('Current URL:', window.location.pathname);
    
    // Очищаем предыдущее состояние если оно есть
    if (window.galleryController && window.galleryController.resetState) {
        console.log('Resetting previous state...');
        window.galleryController.resetState();
    }
    
    // Получаем элементы галереи
    const gallery = document.querySelector('.gallery');
    const galleryContainer = document.querySelector('.gallery__container');
    const topicCards = document.querySelectorAll('.topic-card');
    
    console.log('Gallery elements check:');
    console.log('- gallery:', gallery ? '✅' : '❌');
    console.log('- galleryContainer:', galleryContainer ? '✅' : '❌');
    console.log('- topicCards count:', topicCards.length);
    
    if (!gallery || !galleryContainer || topicCards.length === 0) {
        console.log('❌ Gallery elements not found, skipping initialization');
        console.log('Available elements:', document.querySelectorAll('*').length, 'total elements in DOM');
        return;
    }
    
    // Применяем CSS-переменную индекса если она вынесена в data-attr
    topicCards.forEach(card => {
        const i = card.getAttribute('data-i');
        if (i !== null) {
            card.style.setProperty('--i', i);
        }
    });
    console.log('Found topic cards:', topicCards.length);
    
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
            // Скрываем клавиатуру
            const searchInput = document.getElementById('search-input');
            if (searchInput) {
                searchInput.blur();
            }
            
                    if (e.target === selectedCardOverlay) {
            goBackFromCard();
        }
        });
        
        document.body.appendChild(selectedCardOverlay);
        return selectedCardOverlay;
    }
    
    // Добавляем клавиатурное управление только для Escape
    document.addEventListener('keydown', function(e) {
        if (selectedCard && e.key === 'Escape') {
            goBackFromCard();
        }
    });

        // НОВЫЙ ПОДХОД: Используем делегирование событий на родительском контейнере
    // Это работает для всех карточек, включая динамически созданные
    
    // Удаляем старый обработчик если он есть
    if (gallery.clickHandlerAdded) {
        console.log('Removing old gallery click handler...');
        gallery.removeEventListener('click', gallery.clickHandler);
    }
    
    // Создаем новый обработчик
    gallery.clickHandler = function(e) {
        console.log('🔥 GALLERY CLICKED!', e.target);
        
        // Скрываем клавиатуру при любом клике в галерее
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.blur();
        }
        
        // Находим ближайшую карточку
        const clickedCard = e.target.closest('.topic-card');
        
        if (!clickedCard) {
            console.log('Clicked outside cards');
            return;
        }
        
        console.log('🎯 CARD FOUND!', clickedCard.getAttribute('data-topic-id'));
        
        // Если клик был на кнопке - игнорируем
        if (e.target.tagName === 'BUTTON') {
            console.log('Button clicked, ignoring...');
            return;
        }
        
        e.preventDefault();
        e.stopPropagation();
        
        const topicId = clickedCard.getAttribute('data-topic-id');
        console.log(`Clicked on topic card with ID: ${topicId}`);
        
        // Если карточка уже выбрана - ничего не делаем
        if (clickedCard.classList.contains('selected')) {
            console.log('Card already selected, ignoring...');
            return;
        }
        
        // Выбираем карточку
        console.log('Calling selectCard...');
        selectCard(clickedCard);
    };
    
    // Добавляем обработчик
    gallery.addEventListener('click', gallery.clickHandler);
    gallery.clickHandlerAdded = true;
    
    console.log('✅ Gallery click handler with delegation added');

    // Добавляем hover эффекты через делегирование
    if (!gallery.hoverHandlerAdded) {
        gallery.addEventListener('mouseenter', function(e) {
            const card = e.target.closest('.topic-card');
            if (card && !selectedCard && !('ontouchstart' in window)) {
                pauseGallery();
            }
        }, true);

        gallery.addEventListener('mouseleave', function(e) {
            const card = e.target.closest('.topic-card');
            if (card && !selectedCard && !('ontouchstart' in window)) {
                setTimeout(() => {
                    if (!selectedCard) {
                        resumeGallery();
                    }
                }, 500);
            }
        }, true);
        
        gallery.hoverHandlerAdded = true;
        console.log('✅ Gallery hover handlers added');
    }
    
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
        const title = card.querySelector('.card-overlay h3').textContent;
        const topicId = card.getAttribute('data-topic-id');
        
        container.innerHTML = `
            <img src="${img.src}" alt="${img.alt}" style="width: 100%; height: 100%; object-fit: cover;">
            <div class="card-overlay always-visible">
                <h3>${title}</h3>
                <div class="card-actions">
                    <button class="btn-start" onclick="handleStartTopic(event, ${topicId})">Начать</button>
                    <button class="btn-back" onclick="goBackFromCard(event)">Назад</button>
                </div>
            </div>
        `;
        
        // Показываем overlay
        setTimeout(() => {
            overlay.classList.add('active');
        }, 50);
        
        console.log('Card selected successfully');
    }

    // Убрали прогресс из overlay карточки по требованию
    
    function goBackFromCard() {
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
        
        // Используем AJAX навигацию вместо полной перезагрузки страницы
        setTimeout(async () => {
            try {
                const url = `/topic/${topicId}`;
                console.log('Loading topic page via AJAX:', url);
                
                // Сначала сбрасываем состояние галереи
                if (window.galleryController && window.galleryController.resetState) {
                    window.galleryController.resetState();
                }
                
                const contentContainer = document.querySelector('.content');
                if (!contentContainer) {
                    console.log('Content container not found, falling back to normal navigation');
                    window.location.href = url;
                    return;
                }
                
                // Показываем индикатор загрузки
                contentContainer.style.opacity = '0.7';
                
                const response = await fetch(url, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                
                if (response.ok) {
                    const html = await response.text();
                    
                    // Парсим HTML и извлекаем контент
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const newContent = doc.querySelector('.content');
                    
                    if (newContent) {
                        // Плавно заменяем контент
                        setTimeout(() => {
                            contentContainer.innerHTML = newContent.innerHTML;
                            contentContainer.style.opacity = '1';
                            
                            // Обновляем URL в браузере
                            window.history.pushState({}, '', url);
                            
                            // Обновляем активную навигацию
                            updateActiveNavigation(url);
                            
                            // Загружаем скрипт для страницы темы
                            loadTopicDetailScript();
                            
                            console.log('Topic page loaded via AJAX successfully');
                        }, 200);
                    } else {
                        console.log('New content not found, falling back to normal navigation');
                        window.location.href = url;
                    }
                } else {
                    console.log('AJAX request failed, falling back to normal navigation');
                    window.location.href = url;
                }
            } catch (error) {
                console.error('Error during AJAX navigation:', error);
                // Fallback к обычному переходу
                window.location.href = `/topic/${topicId}`;
            }
        }, 300);
    }
    
    // Функция для обновления активной навигации
    function updateActiveNavigation(url) {
        const navItems = document.querySelectorAll('.navigation .list');
        navItems.forEach(item => {
            item.classList.remove('active');
            // Для страниц тем активируем "Главная"
            if (url.startsWith('/topic/') && item.getAttribute('data-href') === '/') {
                item.classList.add('active');
            }
        });
    }
    
    // Функция для динамической загрузки скрипта страницы темы
    function loadTopicDetailScript() {
        console.log('📜 Loading topic detail script...');
        
        // Удаляем предыдущий скрипт если он есть
        const existingScript = document.getElementById('topic-detail-script');
        if (existingScript) {
            existingScript.remove();
        }
        
        // Создаем новый скрипт
        const script = document.createElement('script');
        script.id = 'topic-detail-script';
        script.src = '/static/js/topic-detail.js';
        script.onload = function() {
            console.log('✅ Topic detail script loaded successfully');
        };
        script.onerror = function() {
            console.error('❌ Failed to load topic detail script');
        };
        
        document.head.appendChild(script);
    }
    
    // Экспортируем функции для использования в HTML
    window.selectCard = selectCard;
    window.goBackFromCard = function(event) {
        if (event) {
            event.preventDefault();
                    event.stopPropagation();
    }
    goBackFromCard();
};
    window.startTopic = function(event, topicId) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        navigateToTopic(topicId);
    };
    
    // Экспортируем функции глобально для экстренного доступа
    window.handleStartTopic = function(event, topicId) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        navigateToTopic(topicId);
    };
    
    // Объект для управления галереей
    window.galleryController = {
        selectCard,
        goBackFromCard,
        pauseGallery,
        resumeGallery,
        navigateToTopic,
        // Функция сброса состояния для AJAX навигации
        resetState: function() {
            console.log('Resetting gallery state...');
            
            try {
                // Скрываем клавиатуру
                const searchInput = document.getElementById('search-input');
                if (searchInput) {
                    searchInput.blur();
                }
                
                // Сбрасываем выбранную карточку
                if (selectedCard) {
                    selectedCard.classList.remove('selected');
                    selectedCard = null;
                }
                
                // Убираем overlay если он активен
                if (selectedCardOverlay) {
                    selectedCardOverlay.classList.remove('active');
                    // Небольшая задержка перед удалением для анимации
                    setTimeout(() => {
                        if (selectedCardOverlay && selectedCardOverlay.parentNode) {
                            selectedCardOverlay.remove();
                        }
                        selectedCardOverlay = null;
                    }, 100);
                }
                
                // Убираем все overlay-элементы на всякий случай
                const allOverlays = document.querySelectorAll('.selected-card-overlay');
                allOverlays.forEach(overlay => {
                    overlay.classList.remove('active');
                    setTimeout(() => overlay.remove(), 100);
                });
                
                // Убираем класс выбора с контейнера
                const currentGalleryContainer = document.querySelector('.gallery__container');
                if (currentGalleryContainer) {
                    currentGalleryContainer.classList.remove('has-selection');
                }
                
                // Убираем классы выбора со всех карточек
                const allCards = document.querySelectorAll('.topic-card.selected');
                allCards.forEach(card => card.classList.remove('selected'));
                
                // Возобновляем галерею
                const currentGallery = document.querySelector('.gallery');
                if (currentGallery) {
                    currentGallery.classList.remove('paused');
                }
                
                console.log('Gallery state reset complete (delegation preserved)');
            } catch (error) {
                console.error('Error during state reset:', error);
            }
        },
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
    
    // Проверяем, что карточки найдены
    console.log('Found topic cards:', topicCards.length);
    
    // Добавляем тестовую функцию для диагностики
    window.testCardClick = function(cardIndex = 0) {
        const cards = document.querySelectorAll('.topic-card');
        if (cards[cardIndex]) {
            console.log('Testing click on card:', cardIndex);
            cards[cardIndex].click();
        } else {
            console.log('Card not found:', cardIndex);
        }
    };
    
    console.log('💡 Для тестирования кликов используйте: window.testCardClick(0)');
    console.log('✅ Gallery initialization complete with event delegation');
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

// ЭКСТРЕННЫЙ ФИКС: Добавляем глобальный обработчик кликов
console.log('🚨 Adding emergency global click handler...');

document.addEventListener('click', function(e) {
    console.log('🔥 GLOBAL CLICK:', e.target);
    
    // Проверяем, находимся ли мы на странице темы
    const isTopicPage = window.location.pathname.startsWith('/topic/');
    if (isTopicPage) {
        console.log('🚫 On topic page, ignoring global click handler');
        return;
    }
    
    const card = e.target.closest('.topic-card');
    if (card) {
        console.log('🎯 CARD DETECTED GLOBALLY!', card.getAttribute('data-topic-id'));
        
        // Скрываем клавиатуру
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.blur();
        }
        
        // Если клик на кнопке - игнорируем
        if (e.target.tagName === 'BUTTON') {
            console.log('Button clicked, ignoring...');
            return;
        }
        
        e.preventDefault();
        e.stopPropagation();
        
        // Если карточка уже выбрана - ничего не делаем
        if (card.classList.contains('selected')) {
            console.log('Card already selected, ignoring...');
            return;
        }
        
        // Вызываем функцию выбора карточки
        if (window.galleryController && window.galleryController.selectCard) {
            console.log('Calling selectCard via galleryController...');
            window.galleryController.selectCard(card);
        } else {
            console.log('⚠️ galleryController not found, trying direct call...');
            // Прямой вызов функции selectCard
            if (typeof selectCard === 'function') {
                selectCard(card);
            } else {
                console.error('❌ selectCard function not available!');
            }
        }
    }
}, true); // Используем capture phase

console.log('✅ Emergency global click handler added');

// Экспортируем функцию глобально для доступа из других скриптов
window.initTopicCards = initTopicCards;
window.goBackFromCard = goBackFromCard;

// Инициализируем при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔥 DOMContentLoaded fired!');
    initTopicCards();
});

// Дополнительная инициализация для случаев когда DOM уже готов
if (document.readyState === 'loading') {
    console.log('⏳ DOM still loading, waiting for DOMContentLoaded...');
} else {
    console.log('✅ DOM already ready, initializing immediately...');
    initTopicCards();
}

console.log('🔥 TOPIC-CARDS.JS SCRIPT END REACHED!'); 