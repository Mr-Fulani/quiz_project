console.log('📄 Topic detail script loaded!');
console.log('Current page:', window.location.pathname);

// Функция для установки обработчиков кнопки "Назад"
function setupBackButtonHandlers() {
    console.log('🔧 Настройка обработчиков кнопки "Назад"...');
    
    // Добавляем обработчик для кнопки "Назад"
    const backButton = document.querySelector('.back-button');
    if (backButton) {
        // Удаляем существующие обработчики
        const newBackButton = backButton.cloneNode(true);
        backButton.parentNode.replaceChild(newBackButton, backButton);
        
        // Добавляем новый обработчик
        newBackButton.addEventListener('click', function(e) {
            e.preventDefault();
            goBackToMain();
        });
        console.log('✅ Обработчик кнопки "Назад" добавлен');
    } else {
        console.log('⚠️ Кнопка "Назад" не найдена на странице');
    }
}

// Инициализация обработчиков кликов для подтем
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔧 topic-detail: bars-only navigation; card clicks disabled');
    setupBackButtonHandlers();
});

// Также инициализируем сразу, если DOM уже загружен
if (document.readyState !== 'loading') {
    console.log('📄 DOM уже загружен');
    setupBackButtonHandlers();
}

function setupSubtopicHandlers() { /* intentionally disabled: cards are not clickable */ }

function goBackToMain() {
    console.log('🔙 goBackToMain() function called!');
    
    // Всегда возвращаемся на главную страницу
    const currentLang = window.currentLanguage || 'ru';
    const mainUrl = `/?lang=${currentLang}`;
    
    console.log('🔙 Возвращаемся на главную страницу');
    
    // Используем существующую функцию loadPage из base.html
    if (typeof window.loadPage === 'function') {
        console.log('🔙 Используем loadPage для возврата на главную');
        window.loadPage(mainUrl);
    } else {
        console.log('⚠️ loadPage не найден, используем window.location');
        window.location.href = mainUrl;
    }
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