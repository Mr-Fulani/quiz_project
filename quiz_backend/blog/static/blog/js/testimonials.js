document.addEventListener('DOMContentLoaded', function() {
    console.log("Testimonials script loaded!");

    // Получаем шаблон URL из глобального объекта window, если он есть
    const userProfileUrlTemplate = window.userProfileUrlTemplate || '/accounts/user/__USERNAME__/';

    // Находим родительский элемент для карточек отзывов/пользователей
    const testimonialsContainer = document.querySelector('.testimonials');

    // Если контейнер найден, добавляем обработчик кликов именно на него
    if (testimonialsContainer) {
        testimonialsContainer.addEventListener('click', function(e) {
            // Ищем ближайший родительский элемент с классом .testimonials-item
            const item = e.target.closest('.testimonials-item');
            
            if (item) {
                // Предотвращаем стандартное действие, если это была ссылка
                e.preventDefault(); 
                e.stopPropagation(); // Останавливаем всплытие, чтобы избежать конфликтов

                const username = item.dataset.username;
                if (username) {
                    // Создаем корректный URL и переходим по нему
                    const profileUrl = userProfileUrlTemplate.replace('__USERNAME__', username);
                    window.location.href = profileUrl;
                } else {
                    console.error('Username not found on clicked testimonials item.');
                }
            }
        });
    }
}); 