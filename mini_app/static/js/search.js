// Поиск тем
// Проверяем, не объявлена ли уже переменная
if (typeof window.searchTimeout === 'undefined') {
    window.searchTimeout = null;
}
const searchInput = document.getElementById('search-input');
const searchResults = document.getElementById('search-results');
const gallery = document.getElementById('gallery');

async function handleSearch(event) {
    const query = event.target.value.trim();
    
    // Очищаем предыдущий таймаут
    clearTimeout(window.searchTimeout);
    
    // Устанавливаем новый таймаут для debounce
    window.searchTimeout = setTimeout(async () => {
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
            updateGallery(data);
        } else {
            console.error('❌ Ошибка поиска:', data);
        }
    } catch (error) {
        console.error('❌ Ошибка при выполнении поиска:', error);
    }
}

async function loadTopics() {
    try {
        const response = await fetch('/api/topics');
        const data = await response.json();
        
        if (response.ok) {
            updateGallery(data);
        } else {
            console.error('❌ Ошибка загрузки тем:', data);
        }
    } catch (error) {
        console.error('❌ Ошибка при загрузке тем:', error);
    }
}

function updateGallery(topics) {
    // Сохраняем состояние поля поиска
    const currentSearchInput = document.getElementById('search-input');
    const wasFocused = currentSearchInput === document.activeElement;
    const searchValue = currentSearchInput ? currentSearchInput.value : '';
    
    const container = document.querySelector('.gallery__container');
    
    if (!container) {
        console.error('❌ Контейнер галереи не найден!');
        return;
    }
    
    if (!topics || topics.length === 0) {
        container.innerHTML = '<div class="no-results">Темы не найдены</div>';
    } else {
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
        
        // Переинициализируем обработчики событий
        initializeCardHandlers();
    }
    
    // Восстанавливаем состояние поля поиска
    if (currentSearchInput) {
        currentSearchInput.value = searchValue;
        if (wasFocused) {
            currentSearchInput.focus();
        }
    }
}

function initializeCardHandlers() {
    // Инициализация обработчиков для карточек тем
    const topicCards = document.querySelectorAll('.topic-card');
    topicCards.forEach(card => {
        card.addEventListener('click', function(e) {
            // Игнорируем клики по кнопкам
            if (e.target.tagName === 'BUTTON') {
                return;
            }
            
            const topicId = this.getAttribute('data-topic-id');
            if (topicId) {
                // Переходим на страницу темы
                window.location.href = `/topic/${topicId}`;
            }
        });
    });
}

function hideKeyboard() {
    // Скрываем клавиатуру на мобильных устройствах
    if (searchInput) {
        searchInput.blur();
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    if (searchInput) {
        searchInput.addEventListener('input', handleSearch);
        searchInput.addEventListener('focus', function() {
            // Показываем результаты поиска при фокусе
            if (this.value.trim().length > 0) {
                handleSearch({ target: this });
            }
        });
    }
    
    // Инициализируем обработчики карточек
    initializeCardHandlers();
});

// Также инициализируем, если DOM уже загружен
if (document.readyState === 'loading') {
    // DOM еще загружается, ждем события DOMContentLoaded
} else {
    if (searchInput) {
        searchInput.addEventListener('input', handleSearch);
        searchInput.addEventListener('focus', function() {
            if (this.value.trim().length > 0) {
                handleSearch({ target: this });
            }
        });
    }
    initializeCardHandlers();
} 