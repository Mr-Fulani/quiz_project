/**
 * Динамическое управление отступами заголовков
 * Добавляет дополнительный отступ только для длинных заголовков
 */

document.addEventListener('DOMContentLoaded', function() {
    // Функция для проверки и установки отступов
    function adjustHeaderSpacing() {
        const articles = document.querySelectorAll('article');
        
        articles.forEach(article => {
            const headers = article.querySelectorAll('h1, h2, h3, .article-title');
            let hasLongHeader = false;
            
            headers.forEach(header => {
                const textLength = header.textContent.trim().length;
                
                // Если хотя бы один заголовок длиннее 20 символов, помечаем
                if (textLength > 20) {
                    hasLongHeader = true;
                }
            });

            if (hasLongHeader) {
                article.classList.add('long-header');
            } else {
                article.classList.remove('long-header');
            }
        });
    }
    
    // Запускаем при загрузке страницы с небольшой задержкой для корректного расчета отрендеренного текста
    requestAnimationFrame(() => {
        adjustHeaderSpacing();
        console.log('Header spacing adjusted on load');
    });
    
    // Также наблюдаем за изменениями в DOM (для динамически загружаемого контента)
    const observer = new MutationObserver(function(mutations) {
        adjustHeaderSpacing();
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true
    });
    
    // Запускаем при изменении размера окна (для адаптивности)
    window.addEventListener('resize', adjustHeaderSpacing);
});
