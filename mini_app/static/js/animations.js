   /* mini_app/static/js/animations.js */
   document.addEventListener('DOMContentLoaded', () => {
    const indicator = document.querySelector('.indicator');
    const lists = document.querySelectorAll('.navigation-menu .list');
    const nav = document.querySelector('.navigation-menu');

    if (!indicator || !nav) {
        console.error('Элемент индикатора или навигационного меню не найден!');
        return;
    }

    // Функция для установки позиции и ширины индикатора
    function setIndicatorPosition(element) {
        const navRect = nav.getBoundingClientRect();
        const elemRect = element.getBoundingClientRect();
        const left = elemRect.left - navRect.left;
        const width = elemRect.width;

        console.log('Установка позиции индикатора: left =', left, ', width =', width);

        indicator.style.width = `${width}px`; // Устанавливаем ширину индикатора
        indicator.style.transform = `translateX(${left}px)`; // Перемещаем индикатор
    }

    // Установка индикатора на активный пункт при загрузке страницы
    const activeList = document.querySelector('.navigation-menu .list.active');
    if (activeList) {
        setIndicatorPosition(activeList);
    }

    // Функция для активации ссылки и перемещения индикатора
    function activeLink(event) {
        // event.preventDefault(); // Удалите или закомментируйте эту строку для восстановления перехода по ссылке

        console.log('Кликнули на пункт меню:', this);
        // Удаляем класс active у всех пунктов
        lists.forEach((item) => item.classList.remove('active'));
        // Добавляем класс active к текущему пункту
        this.classList.add('active');

        // Устанавливаем позицию индикатора на текущий пункт
        setIndicatorPosition(this);
    }

    // Добавляем обработчики событий
    lists.forEach((item) => {
        item.addEventListener('click', activeLink);
    });

    // Обновление позиции индикатора при изменении размера окна
    window.addEventListener('resize', () => {
        const activeList = document.querySelector('.navigation-menu .list.active');
        if (activeList) {
            setIndicatorPosition(activeList);
        }
    });
});