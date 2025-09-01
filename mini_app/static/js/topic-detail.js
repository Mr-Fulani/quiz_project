console.log('📄 Topic detail script loaded!');
console.log('Current page:', window.location.pathname);

// Инициализация обработчиков кликов для подтем
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔧 topic-detail: bars-only navigation; card clicks disabled');
});

// Также инициализируем сразу, если DOM уже загружен
if (document.readyState !== 'loading') {
    console.log('📄 DOM уже загружен');
}

function setupSubtopicHandlers() { /* intentionally disabled: cards are not clickable */ }

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

// Глобальная функция для кликов по полосам сложности (используется из шаблона через inline onclick)
window.openSubtopicLevel = function(el, subtopicId, level, levelCount) {
    console.log(`🎯 openSubtopicLevel called: subtopicId=${subtopicId}, level=${level}, levelCount=${levelCount}`);
    
    try {
        if (window.event && typeof window.event.stopPropagation === 'function') {
            window.event.stopPropagation();
        }
    } catch (_) {}

    // Блокируем переход для пустых уровней
    if (level !== 'all' && (!levelCount || Number(levelCount) === 0)) {
        console.log(`❌ Блокируем переход - нет задач для уровня ${level}`);
        if (typeof window.showNotification === 'function') {
            // Передаем ключ перевода и fallback сообщение
            window.showNotification('no_tasks_for_level', 'error', el, 'Нет задач выбранного уровня');
        } else {
            alert('Нет задач выбранного уровня');
        }
        return false;
    }

    const currentLang = window.currentLanguage || 'en';
    const url = `/subtopic/${subtopicId}/tasks?lang=${currentLang}` + (level && level !== 'all' ? `&level=${level}` : '');
    
    console.log(`🔗 Constructed URL: ${url}`);
    
    // Устанавливаем cookie с уровнем для надежности
    try {
        document.cookie = `level_filter_${subtopicId}=${level}; path=/; max-age=60`;
        console.log(`🍪 Cookie установлен: level_filter_${subtopicId}=${level}`);
    } catch (e) {
        console.error('❌ Ошибка установки cookie:', e);
    }

    if (typeof window.Telegram !== 'undefined' && window.Telegram.WebApp) {
        console.log('📱 Используем Telegram WebApp навигацию');
        try { 
            window.Telegram.WebApp.navigateTo(url); 
        } catch (_) { 
            console.log('❌ Ошибка Telegram навигации, fallback на location.href');
            window.location.href = url; 
        }
    } else {
        console.log('🌐 Используем обычную навигацию');
        window.location.href = url;
    }
    return false;
}