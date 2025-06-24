// Поиск тем
let searchTimeout;
const searchInput = document.getElementById('search-input');
const searchResults = document.getElementById('search-results');
const gallery = document.getElementById('gallery');

async function handleSearch(event) {
    const query = event.target.value.trim();
    
    // Очищаем предыдущий таймаут
    clearTimeout(searchTimeout);
    
    // Устанавливаем новый таймаут для debounce
    searchTimeout = setTimeout(async () => {
        if (query.length === 0) {
            // Если поиск пустой, загружаем все темы
            await loadTopics();
            return;
        }
        
        if (query.length >= 2) {
            // Поиск только если введено 2 или больше символов
            await searchTopics(query);
        }
    }, 300); // Задержка 300ms
}

async function searchTopics(query) {
    try {
        const response = await fetch(`/api/topics?search=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (response.ok) {
            updateGallery(data.topics);
        } else {
            console.error('Ошибка поиска:', data);
        }
    } catch (error) {
        console.error('Ошибка при выполнении поиска:', error);
    }
}

async function loadTopics() {
    try {
        const response = await fetch('/api/topics');
        const data = await response.json();
        
        if (response.ok) {
            updateGallery(data.topics);
        } else {
            console.error('Ошибка загрузки тем:', data);
        }
    } catch (error) {
        console.error('Ошибка при загрузке тем:', error);
    }
}

function updateGallery(topics) {
    const container = document.querySelector('.gallery__container');
    
    if (!topics || topics.length === 0) {
        container.innerHTML = '<div class="no-results">Темы не найдены</div>';
        return;
    }
    
    container.innerHTML = topics.map((topic, index) => `
        <span style="--i:${index};" class="topic-card" data-topic-id="${topic.id}">
            <img src="${topic.image_url}" alt="${topic.name}">
            <div class="card-overlay always-visible">
                <h3>${topic.name}</h3>
                <p class="difficulty">${topic.difficulty}</p>
                <p class="questions">${topic.questions_count} вопросов</p>
                <div class="card-actions">
                    <button class="btn-start" onclick="startTopic(event, ${topic.id})">Начать</button>
                    <button class="btn-back" onclick="goBack(event)">Назад</button>
                </div>
            </div>
        </span>
    `).join('');
    
    // Переинициализируем обработчики событий для новых карточек
    initializeCardHandlers();
}

function initializeCardHandlers() {
    // Переинициализируем галерею после обновления карточек
    if (window.initTopicCards) {
        window.initTopicCards();
    }
}

// Обработчик для скрытия клавиатуры
function hideKeyboard() {
    if (searchInput) {
        searchInput.blur();
    }
}

// Скрываем клавиатуру при клике вне поля поиска
document.addEventListener('click', function(event) {
    if (!event.target.closest('.search-container') && 
        !event.target.closest('.topic-card') &&
        !event.target.closest('.selected-card-overlay')) {
        hideKeyboard();
    }
}, true); // Используем capture phase

// Скрываем клавиатуру при скролле
document.addEventListener('scroll', hideKeyboard);

// Скрываем клавиатуру при нажатии Enter
if (searchInput) {
    searchInput.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            hideKeyboard();
        }
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    initializeCardHandlers();
}); 