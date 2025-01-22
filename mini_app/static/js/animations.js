document.addEventListener('DOMContentLoaded', () => {
    const indicator = document.querySelector('.navigation ul .indicator');
    const items = document.querySelectorAll('.navigation ul li');

    console.log('Индикатор:', indicator);
    console.log('Пункты меню:', items);

    if (!indicator || items.length === 0) {
        console.error('Необходимые элементы не найдены!');
        return;
    }

    // Функция для получения точной позиции элемента
    function getPosition(el) {
        const rect = el.getBoundingClientRect();
        const parent = el.closest('ul').getBoundingClientRect();
        return rect.left - parent.left;
    }

    function handleIndicator(el) {
        // Форсируем перерасчет layout
        el.offsetHeight;

        // Получаем актуальную позицию
        const left = getPosition(el);
        console.log('Перемещение индикатора:', left);

        // Применяем трансформацию с небольшой задержкой
        requestAnimationFrame(() => {
            indicator.style.transform = `translateX(${left}px)`;
        });
    }

    items.forEach((item) => {
        item.addEventListener('click', (e) => {
            e.preventDefault(); // Предотвращаем переход по ссылке

            // Удаляем класс active у всех элементов
            items.forEach(item => item.classList.remove('active'));

            // Добавляем класс active к нажатому элементу
            item.classList.add('active');

            // Перемещаем индикатор
            handleIndicator(item);

            // Выполняем переход по ссылке с небольшой задержкой
            const href = item.querySelector('a').getAttribute('href');
            setTimeout(() => {
                window.location.href = href;
            }, 300);
        });
    });

    // Установка начальной позиции индикатора
    function initializeIndicator() {
        const activeItem = document.querySelector('.navigation ul li.active');
        if (activeItem) {
            handleIndicator(activeItem);
        }
    }

    // Вызываем инициализацию несколько раз для надежности
    initializeIndicator();
    setTimeout(initializeIndicator, 100);
    setTimeout(initializeIndicator, 500);

    // Обработка изменения размера окна
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            initializeIndicator();
        }, 100);
    });
});