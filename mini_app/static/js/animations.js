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
        items.forEach(item => {
            const link = item.querySelector('a');
            if (link.getAttribute('href') === currentPath) {
                // Удаляем active у всех элементов
                items.forEach(i => i.classList.remove('active'));
                // Добавляем active текущему элементу
                item.classList.add('active');
            }
        });
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