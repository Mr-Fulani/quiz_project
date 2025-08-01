document.addEventListener('DOMContentLoaded', () => {
    const indicator = document.querySelector('.indicator');
    const items = document.querySelectorAll('.navigation ul li');

    if (!indicator || items.length === 0) {
        console.error('Необходимые элементы не найдены!');
        return;
    }

    // Функция для определения активного пункта меню на основе текущего URL
    const setActiveItemFromURL = () => {
        const currentPath = window.location.pathname;
        let activeItem = null;
        
        // Специальная логика для страниц задач
        if (currentPath.includes('/subtopic/') && currentPath.includes('/tasks')) {
            // Для страниц задач считаем активной главную страницу
            activeItem = items[0]; // Первый элемент (главная)
        } else {
            // Обычная логика для других страниц
            items.forEach(item => {
                const link = item.querySelector('a');
                const href = link.getAttribute('href');
                // Убираем параметры из href для сравнения
                const hrefPath = href.split('?')[0];
                if (hrefPath === currentPath || 
                    (currentPath.startsWith('/topic/') && hrefPath === '/')) {
                    activeItem = item;
                }
            });
        }
        
        if (activeItem) {
            // Удаляем active у всех элементов
            items.forEach(i => i.classList.remove('active'));
            // Добавляем active текущему элементу
            activeItem.classList.add('active');
        }
    };

    // Устанавливаем активный пункт при загрузке страницы
    setActiveItemFromURL();

    items.forEach((item) => {
        item.addEventListener('click', (e) => {
            e.preventDefault();

            // Удаляем класс active у всех элементов
            items.forEach(item => item.classList.remove('active'));

            // Добавляем класс active к нажатому элементу
            item.classList.add('active');

            // Получаем ссылку для перехода
            const link = item.querySelector('a');
            const href = link.getAttribute('href');

            // Переходим по ссылке после анимации
            setTimeout(() => {
                window.location.href = href;
            }, 500);
        });
    });
});