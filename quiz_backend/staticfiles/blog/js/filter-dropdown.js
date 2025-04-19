/**
 * Управление выпадающим меню фильтров и функциональностью фильтрации.
 * Инициализирует фильтр "All"/"Все" по умолчанию, отображая все элементы.
 * Не закрывает меню на десктопе (> 580px).
 * Использует GSAP для анимации.
 */
document.addEventListener('DOMContentLoaded', () => {
    const toggleBtn = document.querySelector('[data-filter-toggle]');
    const dropdown = document.querySelector('[data-filter-dropdown]');
    const filterButtons = document.querySelectorAll('[data-filter-btn]');
    const filterItems = document.querySelectorAll('[data-filter-item]');

    if (!dropdown) {
        console.error('Filter dropdown not found');
        return;
    }

    /**
     * Применяет фильтр к элементам.
     * @param {string} filterValue - Значение фильтра (например, 'all', 'web').
     */
    function applyFilter(filterValue) {
        filterButtons.forEach(btn => btn.classList.remove('active'));
        const normalizedFilterValue = filterValue.trim().toLowerCase();
        const activeButton = Array.from(filterButtons).find(
            btn => btn.textContent.trim().toLowerCase() === normalizedFilterValue
        );

        if (activeButton) {
            activeButton.classList.add('active');
        } else {
            console.warn(`Button for filter "${filterValue}" not found. Available buttons:`,
                [...filterButtons].map(btn => `"${btn.textContent.trim()}"`));
        }

        console.log('Filter applied:', normalizedFilterValue);
        console.log('Available categories:', [...filterItems].map(item => item.dataset.category?.toLowerCase() || 'undefined'));

        filterItems.forEach(item => {
            const itemCategory = item.dataset.category?.toLowerCase() || '';
            console.log(`Item category: ${itemCategory}, Filter: ${normalizedFilterValue}`);
            if (normalizedFilterValue === 'all' || normalizedFilterValue === 'все' || normalizedFilterValue === 'всё' ||
                itemCategory === normalizedFilterValue) {
                item.classList.remove('hidden');
                item.style.display = 'block'; // Принудительно убираем display: none
                gsap.to(item, {
                    opacity: 1,
                    duration: 0.3,
                    ease: 'power2.out',
                    overwrite: 'auto' // Перезаписываем конфликтующие анимации
                });
            } else {
                gsap.to(item, {
                    opacity: 0,
                    duration: 0.3,
                    ease: 'power2.out',
                    onComplete: () => {
                        item.classList.add('hidden');
                        item.style.display = 'none';
                    }
                });
            }
        });
    }

    // Инициализация: пытаемся найти "All", "Все", "Всё" или первую кнопку
    const defaultFilter = Array.from(filterButtons).find(
        btn => ['all', 'все', 'всё'].includes(btn.textContent.trim().toLowerCase())
    )?.textContent.trim().toLowerCase() ||
    (filterButtons.length > 0 ? filterButtons[0].textContent.trim().toLowerCase() : 'all');
    console.log('Default filter:', defaultFilter);

    // Принудительно показываем все элементы при инициализации
    filterItems.forEach(item => {
        item.classList.remove('hidden');
        item.style.display = 'block';
        item.style.opacity = '0'; // Устанавливаем начальную прозрачность
    });
    applyFilter(defaultFilter);

    // Открытие/закрытие выпадающего меню (только для мобильной версии)
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            if (window.innerWidth > 580) return; // Не открываем на десктопе
            const isActive = dropdown.classList.toggle('active');
            toggleBtn.classList.toggle('active');

            gsap.to(dropdown, {
                opacity: isActive ? 1 : 0,
                y: isActive ? 0 : -10,
                duration: 0.3,
                ease: 'power2.out',
                onStart: () => {
                    if (isActive) {
                        dropdown.style.visibility = 'visible';
                        dropdown.style.display = 'block';
                    }
                },
                onComplete: () => {
                    if (!isActive) {
                        dropdown.style.visibility = 'hidden';
                        dropdown.style.display = 'none';
                    }
                }
            });

            console.log('Dropdown toggled:', isActive);
        });
    }

    // Закрытие меню при клике вне (только для мобильной версии)
    document.addEventListener('click', (e) => {
        if (window.innerWidth > 580) return; // Не закрываем на десктопе
        if (!dropdown.contains(e.target) && toggleBtn && !toggleBtn.contains(e.target)) {
            dropdown.classList.remove('active');
            if (toggleBtn) toggleBtn.classList.remove('active');

            gsap.to(dropdown, {
                opacity: 0,
                y: -10,
                duration: 0.3,
                ease: 'power2.out',
                onComplete: () => {
                    dropdown.style.visibility = 'hidden';
                    dropdown.style.display = 'none';
                }
            });

            console.log('Dropdown closed');
        }
    });

    // Логика фильтрации при клике на кнопки
    filterButtons.forEach(button => {
        button.addEventListener('click', () => {
            const filterValue = button.textContent.trim().toLowerCase();
            applyFilter(filterValue);

            // Закрываем меню только на мобильной версии
            if (window.innerWidth <= 580) {
                dropdown.classList.remove('active');
                if (toggleBtn) toggleBtn.classList.remove('active');
                gsap.to(dropdown, {
                    opacity: 0,
                    y: -10,
                    duration: 0.3,
                    ease: 'power2.out',
                    onComplete: () => {
                        dropdown.style.visibility = 'hidden';
                        dropdown.style.display = 'none';
                    }
                });
            }
        });
    });
});