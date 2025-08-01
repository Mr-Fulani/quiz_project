console.log('📄 Topic detail script loaded!');
console.log('Current page:', window.location.pathname);

// Инициализация обработчиков кликов для подтем
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔧 Setting up subtopic click handlers (DOMContentLoaded)...');
    setupSubtopicHandlers();
});

// Также инициализируем сразу, если DOM уже загружен
if (document.readyState === 'loading') {
    console.log('📄 DOM еще загружается, ждем DOMContentLoaded...');
} else {
    console.log('📄 DOM уже загружен, инициализируем обработчики сразу...');
    setupSubtopicHandlers();
}

function setupSubtopicHandlers() {
    const subtopicCards = document.querySelectorAll('.subtopic-card');
    console.log(`🔧 Found ${subtopicCards.length} subtopic cards`);
    
    subtopicCards.forEach(card => {
        card.addEventListener('click', function() {
            const subtopicId = this.dataset.subtopicId;
            console.log('🖱️ Subtopic card clicked, ID:', subtopicId);
            if (subtopicId) {
                startSubtopic(parseInt(subtopicId));
            }
        });
    });
}

function goBackToMain() {
    console.log('🔙 goBackToMain() function called!');
    console.log('Current URL:', window.location.href);
    
    // Используем AJAX навигацию для возврата на главную
    const loadMainPage = async () => {
        try {
            console.log('🔍 Looking for content container...');
            const contentContainer = document.querySelector('.content');
            console.log('Content container found:', !!contentContainer);
            
            if (!contentContainer) {
                console.log('❌ Content container not found, using browser back');
                window.history.back();
                return;
            }
            
            // Показываем индикатор загрузки
            console.log('💫 Setting loading state...');
            contentContainer.style.opacity = '0.7';
            
            console.log('📡 Fetching main page...');
            const response = await fetch('/', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            console.log('📡 Response status:', response.status);
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
                        window.history.pushState({}, '', '/');
                        
                        // Обновляем активную навигацию
                        const navItems = document.querySelectorAll('.navigation .list');
                        navItems.forEach(item => {
                            item.classList.remove('active');
                            if (item.getAttribute('data-href') === '/') {
                                item.classList.add('active');
                            }
                        });
                        
                        // Перезапускаем скрипты карточек
                        if (window.initTopicCards) {
                            console.log('Reinitializing topic cards after back navigation...');
                            window.initTopicCards();
                        }
                        
                        // Удаляем скрипт страницы темы
                        const topicScript = document.getElementById('topic-detail-script');
                        if (topicScript) {
                            topicScript.remove();
                            console.log('🗑️ Topic detail script removed');
                        }
                        
                        console.log('Returned to main page via AJAX successfully');
                    }, 200);
                } else {
                    console.log('New content not found, using browser back');
                    window.history.back();
                }
            } else {
                console.log('AJAX request failed, using browser back');
                window.history.back();
            }
        } catch (error) {
            console.error('Error during AJAX back navigation:', error);
            window.history.back();
        }
    };
    
    loadMainPage();
}

// Функция для запуска подтемы
function startSubtopic(subtopicId) {
    console.log('🚀 startSubtopic() called with ID:', subtopicId);
    
    // Переходим на страницу задач подтемы
    const url = `/subtopic/${subtopicId}/tasks`;
    console.log('📡 Navigating to:', url);
    
    // Используем прямую навигацию для упрощения
    window.location.href = url;
}

// Экспортируем функции глобально
window.goBackToMain = goBackToMain;
window.startSubtopic = startSubtopic;

console.log('✅ Topic detail script ready!'); 