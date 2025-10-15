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
        console.log('🔍 Поиск тем с запросом:', query);
        const language = window.currentLanguage || 'ru';
        const response = await fetch(`/api/topics?search=${encodeURIComponent(query)}&language=${language}`);
        const data = await response.json();
        
        console.log('📡 Ответ от API поиска:', data);
        
        if (response.ok) {
            console.log('✅ Поиск успешен, обновляем галерею с', data.length, 'темами');
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
        console.log('📡 Загружаем все темы...');
        const response = await fetch('/api/topics');
        const data = await response.json();
        
        console.log('📡 Ответ от API загрузки тем:', data);
        
        if (response.ok) {
            console.log('✅ Загрузка успешна, обновляем галерею с', data.length, 'темами');
            updateGallery(data);
        } else {
            console.error('❌ Ошибка загрузки тем:', data);
        }
    } catch (error) {
        console.error('❌ Ошибка при загрузке тем:', error);
    }
}

function updateGallery(topics) {
    console.log('🎨 Обновляем галерею с темами:', topics);
    
    // Сохраняем состояние поля поиска
    const searchInput = document.getElementById('search-input');
    const wasFocused = searchInput === document.activeElement;
    const searchValue = searchInput ? searchInput.value : '';
    
    const container = document.querySelector('.gallery__container');
    
    if (!container) {
        console.error('❌ Контейнер галереи не найден!');
        return;
    }
    
    if (!topics || topics.length === 0) {
        console.log('📭 Нет тем для отображения, показываем сообщение');
        container.innerHTML = '<div class="no-results">Темы не найдены</div>';
    } else {
        console.log('🎨 Создаем HTML для', topics.length, 'тем');
        container.innerHTML = topics.map((topic, index) => {
            const mediaType = topic.media_type || 'default';
            let mediaElement;
            if (mediaType === 'video') {
                if (topic.video_poster_url) {
                    // Если есть постер, показываем его как изображение
                    mediaElement = `<img src="${topic.video_poster_url}" alt="${topic.name}" class="video-poster">`;
                } else {
                    // Иначе показываем первый кадр видео
                    mediaElement = `<video src="${topic.image_url}" alt="${topic.name}" muted playsinline preload="metadata"></video>`;
                }
            } else {
                mediaElement = `<img src="${topic.image_url}" alt="${topic.name}">`;
            }
            
            const dataVideoUrl = mediaType === 'video' ? `data-video-url="${topic.image_url}"` : '';
            
            return `
                <span style="--i:${index};" class="topic-card" data-topic-id="${topic.id}" data-media-type="${mediaType}" ${dataVideoUrl}>
                    ${mediaElement}
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
            `;
        }).join('');
    }
    
    console.log('🔄 Переинициализируем обработчики событий');
    // Переинициализируем обработчики событий для новых карточек
    initializeCardHandlers();
    
    // Восстанавливаем состояние поля поиска
    if (searchInput) {
        searchInput.value = searchValue;
        if (wasFocused) {
            // Небольшая задержка для восстановления фокуса
            setTimeout(() => {
                searchInput.focus();
                // Устанавливаем курсор в конец текста
                searchInput.setSelectionRange(searchValue.length, searchValue.length);
            }, 10);
        }
    }
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