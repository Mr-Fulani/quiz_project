/**
 * Скрипт для страницы подробностей темы
 */

// Инициализация обработчиков кликов для подтем
document.addEventListener('DOMContentLoaded', function() {
    setupSubtopicHandlers();
});

function setupSubtopicHandlers() {
    const subtopicCards = document.querySelectorAll('.subtopic-card');
    
    subtopicCards.forEach(card => {
        card.addEventListener('click', function() {
            const subtopicId = this.dataset.subtopicId;
            if (subtopicId) {
                startSubtopic(parseInt(subtopicId));
            }
        });
    });
}

// Функция для запуска подтемы
function startSubtopic(subtopicId) {
    // Переходим на страницу задач подтемы
    const url = `/subtopic/${subtopicId}/tasks`;
    
    // Используем прямую навигацию для упрощения
    window.location.href = url;
}

// Функция для возврата на главную страницу
function goBackToMain() {
    const contentContainer = document.getElementById('content-container');
    
    if (contentContainer) {
        // Показываем индикатор загрузки
        contentContainer.innerHTML = '<div class="loading">Загрузка...</div>';
        
        // Загружаем главную страницу
        fetch('/')
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
                    window.history.pushState({}, '', '/');
                    
                    // Переинициализируем карточки тем
                    if (window.initTopicCards) {
                        window.initTopicCards();
                    }
                    
                    // Удаляем скрипт страницы темы
                    const topicDetailScript = document.querySelector('script[src*="topic-detail.js"]');
                    if (topicDetailScript) {
                        topicDetailScript.remove();
                    }
                } else {
                    // Если контент не найден, используем обычную навигацию
                    window.location.href = '/';
                }
            })
            .catch(error => {
                console.error('Ошибка загрузки главной страницы:', error);
                // При ошибке используем обычную навигацию
                window.location.href = '/';
            });
    } else {
        // Если контейнер не найден, используем обычную навигацию
        window.location.href = '/';
    }
}

// Экспортируем функции глобально
window.goBackToMain = goBackToMain;
window.startSubtopic = startSubtopic; 