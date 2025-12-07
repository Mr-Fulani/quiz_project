// Глобальная функция для восстановления состояния body
window.restoreBodyState = function() {
    document.body.style.overflow = '';
    document.body.style.position = '';
    document.body.style.top = '';
    document.body.style.left = '';
    document.body.style.right = '';
    document.body.style.width = '';
    console.log('✅ [BODY RESTORE] Состояние body восстановлено');
};

document.addEventListener('DOMContentLoaded', () => {
    // Восстанавливаем состояние body при загрузке страницы
    // На случай если модальное окно осталось открытым после переключения вкладок
    window.restoreBodyState();
    
    // Закрываем модальное окно карусели, если оно случайно осталось открытым
    const carousel = document.getElementById('all-users-carousel');
    if (carousel && carousel.style.display === 'block') {
        console.log('🔧 Восстанавливаем состояние: закрываем модальное окно карусели');
        if (typeof window.closeCarousel === 'function') {
            window.closeCarousel();
        } else {
            // Если функция не доступна, просто скрываем и восстанавливаем body
            carousel.style.display = 'none';
            carousel.classList.remove('active');
            const backdrop = document.getElementById('carousel-backdrop');
            if (backdrop) {
                backdrop.classList.remove('active');
            }
            window.restoreBodyState();
        }
    }
    
    // Закрываем модальное окно редактирования профиля, если оно открыто
    const editModal = document.getElementById('edit-modal');
    if (editModal && editModal.style.display === 'flex') {
        console.log('🔧 Восстанавливаем состояние: закрываем модальное окно редактирования профиля');
        editModal.style.display = 'none';
        editModal.classList.remove('show');
        window.restoreBodyState();
    }
    
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

            // Закрываем все открытые модальные окна при переключении вкладки
            console.log('🔧 Закрываем все модальные окна при переключении вкладки');
            
            // КРИТИЧЕСКИ ВАЖНО: Восстанавливаем состояние body ПЕРВЫМ ДЕЛОМ
            // Это должно произойти до закрытия модальных окон
            if (typeof window.restoreBodyState === 'function') {
                window.restoreBodyState();
            } else {
                document.body.style.overflow = '';
                document.body.style.position = '';
                document.body.style.top = '';
                document.body.style.left = '';
                document.body.style.right = '';
                document.body.style.width = '';
            }
            
            // Закрываем модальное окно карусели пользователей
            const carousel = document.getElementById('all-users-carousel');
            if (carousel && carousel.style.display === 'block') {
                // Сначала скрываем визуально
                carousel.style.display = 'none';
                carousel.classList.remove('active');
                const backdrop = document.getElementById('carousel-backdrop');
                if (backdrop) {
                    backdrop.classList.remove('active');
                }
                // Затем вызываем функцию закрытия для очистки Swiper
                if (typeof window.closeCarousel === 'function') {
                    // Вызываем асинхронно, чтобы не блокировать переход
                    setTimeout(() => {
                        try {
                            window.closeCarousel();
                        } catch (e) {
                            console.warn('Ошибка при закрытии карусели:', e);
                        }
                    }, 0);
                }
            }
            
            // Закрываем модальное окно редактирования профиля
            const editModal = document.getElementById('edit-modal');
            if (editModal && editModal.style.display === 'flex') {
                editModal.style.display = 'none';
                editModal.classList.remove('show');
            }
            
            // Закрываем модальное окно шаринга
            if (window.shareApp && window.shareApp.modal && window.shareApp.modal.style.display === 'flex') {
                window.shareApp.closeModal();
            }
            
            // Повторно восстанавливаем состояние body после закрытия модальных окон
            if (typeof window.restoreBodyState === 'function') {
                window.restoreBodyState();
            } else {
                document.body.style.overflow = '';
                document.body.style.position = '';
                document.body.style.top = '';
                document.body.style.left = '';
                document.body.style.right = '';
                document.body.style.width = '';
            }
            
            // Принудительно триггерим reflow для применения изменений
            void document.body.offsetHeight;

            // Удаляем класс active у всех элементов
            items.forEach(item => item.classList.remove('active'));

            // Добавляем класс active (как на десктопе - просто добавляем класс)
            item.classList.add('active');

            // Получаем ссылку для перехода
            const link = item.querySelector('a');
            const href = link.getAttribute('href');

            // Переходим по ссылке после анимации
            // ВАЖНО: Состояние body уже восстановлено, переход произойдет с чистым состоянием
            setTimeout(() => {
                // Финальная проверка и восстановление состояния перед переходом
                if (typeof window.restoreBodyState === 'function') {
                    window.restoreBodyState();
                }
                // Принудительно применяем изменения
                void document.body.offsetHeight;
                // Переходим на новую страницу
                window.location.href = href;
            }, 500);
        });
    });
});