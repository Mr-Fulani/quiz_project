/**
 * Динамическое управление отступами заголовков
 * Добавляет дополнительный отступ только для длинных заголовков
 */

document.addEventListener('DOMContentLoaded', function() {
    // Функция для проверки и установки отступов
    function adjustHeaderSpacing() {
        const articles = document.querySelectorAll('article');
        
        articles.forEach(article => {
            const headers = article.querySelectorAll('h1, h2');
            
            headers.forEach(header => {
                const textLength = header.textContent.trim().length;
                
                // Если заголовок длиннее 7 символов, добавляем класс
                if (textLength > 7) {
                    article.classList.add('long-header');
                } else {
                    article.classList.remove('long-header');
                }
            });
        });
    }
    
    // Запускаем при загрузке страницы
    adjustHeaderSpacing();
    
    // Запускаем при изменении размера окна (для адаптивности)
    window.addEventListener('resize', adjustHeaderSpacing);
});
