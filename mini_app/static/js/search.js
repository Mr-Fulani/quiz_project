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
    // Добавляем обработчики кликов для новых карточек
    document.querySelectorAll('.topic-card').forEach(card => {
        card.addEventListener('click', function(e) {
            if (e.target.closest('.card-actions')) {
                return; // Не обрабатываем клики по кнопкам
            }
            
            // Переключаем увеличенное состояние
            if (this.classList.contains('enlarged')) {
                this.classList.remove('enlarged');
            } else {
                // Убираем увеличение с других карточек
                document.querySelectorAll('.topic-card.enlarged').forEach(otherCard => {
                    otherCard.classList.remove('enlarged');
                });
                this.classList.add('enlarged');
            }
        });
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    initializeCardHandlers();
}); 