// Поиск тем
// Проверяем, не объявлена ли уже переменная
if (typeof window.searchTimeout === 'undefined') {
    window.searchTimeout = null;
}
// Используем window для предотвращения повторного объявления при SPA-навигации
if (typeof window.searchInput === 'undefined') {
    window.searchInput = null;
}
if (typeof window.searchResults === 'undefined') {
    window.searchResults = null;
}
if (typeof window.searchGallery === 'undefined') {
    window.searchGallery = null;
}
// Получаем элементы, если они есть (используем let для возможности переопределения)
let searchInput = document.getElementById('search-input');
let searchResults = document.getElementById('search-results');
let gallery = document.getElementById('gallery');
// Сохраняем в window для повторного использования
if (searchInput) window.searchInput = searchInput;
if (searchResults) window.searchResults = searchResults;
if (gallery) window.searchGallery = gallery;

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
        const language = window.currentLanguage || document.documentElement.lang || 'en';
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
        const language = window.currentLanguage || document.documentElement.lang || 'en';
        const response = await fetch(`/api/topics?language=${encodeURIComponent(language)}`);
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
    const language = window.currentLanguage || document.documentElement.lang || 'en';
    const translations = window.translations || {};
    const noResultsText = translations.no_results || (language === 'ru' ? 'Темы не найдены' : 'No topics found');
    const questionsText = translations.questions_count || (language === 'ru' ? 'вопросов' : 'questions');
    const startText = translations.start_button || (language === 'ru' ? 'Начать' : 'Start');
    const backText = translations.back_button || (language === 'ru' ? 'Назад' : 'Back');
    
    // Сохраняем состояние поля поиска
    // Используем window.searchInput или получаем элемент заново
    const searchInput = window.searchInput || document.getElementById('search-input');
    const wasFocused = searchInput === document.activeElement;
    const searchValue = searchInput ? searchInput.value : '';
    
    const container = document.querySelector('.gallery__container');
    
    if (!container) {
        console.error('❌ Контейнер галереи не найден!');
        return;
    }
    
    if (!topics || topics.length === 0) {
        console.log('📭 Нет тем для отображения, показываем сообщение');
        container.innerHTML = `<div class="no-results">${noResultsText}</div>`;
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
                    mediaElement = `<video src="${topic.image_url}" alt="${topic.name}" controls playsinline preload="metadata"></video>`;
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
                        <p class="questions">${topic.questions_count} ${questionsText}</p>
                        <div class="card-actions">
                            <button class="btn-start" onclick="startTopic(event, ${topic.id})">${startText}</button>
                            <button class="btn-back" onclick="goBack(event)">${backText}</button>
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
    const searchInput = window.searchInput || document.getElementById('search-input');
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
const searchInputForEnter = window.searchInput || document.getElementById('search-input');
if (searchInputForEnter) {
    searchInputForEnter.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            hideKeyboard();
        }
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    initializeCardHandlers();
}); 