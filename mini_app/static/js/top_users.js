// ГЛОБАЛЬНАЯ ФУНКЦИЯ ДЛЯ ОТКРЫТИЯ СВАЙПЕРА НА ОПРЕДЕЛЁННОМ СЛАЙДЕ
window.openSwiperAtIndex = function(slideIndex = 3) {
    console.log('🔧 ОТКРЫТИЕ СВАЙПЕРА НА СЛАЙДЕ:', slideIndex);
    
    const showBtn = document.getElementById('show-all-users');
    const carousel = document.getElementById('all-users-carousel');
    const backdrop = document.getElementById('carousel-backdrop');
    
    if (!carousel) {
        console.error('🔧 Карусель не найдена!');
        return;
    }
    
    // Скрываем кнопку "Показать всех" если она есть
    if (showBtn) {
        showBtn.classList.add('hidden');
    }
    
    // Блокируем скролл body — сохраняем позицию и фиксируем с top offset
    const scrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
    window.scrollPositionBeforeSwiper = scrollY;

    document.body.style.overflow = 'hidden';
    // Фиксируем тело и смещаем вверх на текущий скролл, чтобы не было прыжка на мобильных
    document.body.style.position = 'fixed';
    document.body.style.top = `-${scrollY}px`;
    document.body.style.left = '0';
    document.body.style.right = '0';
    document.body.style.width = '100%';
    
    // Показываем backdrop
    if (backdrop) {
        backdrop.classList.add('active');
    }
    
    // Показываем карусель и добавляем класс active для flex-стилей
    carousel.style.display = 'block';
    carousel.classList.add('active');
    
    // Принудительно устанавливаем размеры в зависимости от типа устройства
    const screenWidth = window.innerWidth;
    const screenHeight = window.innerHeight;
    // Проверяем именно мобильное устройство, а не просто узкий экран
    const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    const width = '330px';
    const height = isMobile ? '515px' : '445px';
    
    // Позиционирование - центрирование с учетом Safe Areas Telegram (задано в CSS)
    // Используем проценты для корректного центрирования
    const topPosition = '50%';
    const leftPosition = '50%';
    
    // ПРИНУДИТЕЛЬНОЕ ПРИМЕНЕНИЕ СТИЛЕЙ С ВЫСОКОЙ СПЕЦИФИЧНОСТЬЮ
    carousel.style.setProperty('position', 'fixed', 'important');
    carousel.style.setProperty('top', topPosition, 'important');
    carousel.style.setProperty('left', leftPosition, 'important');
    carousel.style.setProperty('right', 'auto', 'important');
    carousel.style.setProperty('bottom', 'auto', 'important');
    carousel.style.setProperty('transform', 'translate(-50%, -50%)', 'important');
    carousel.style.setProperty('width', width, 'important');
    carousel.style.setProperty('height', height, 'important');
    carousel.style.setProperty('max-width', width, 'important');
    carousel.style.setProperty('max-height', height, 'important');
    carousel.style.setProperty('min-width', width, 'important');
    carousel.style.setProperty('min-height', height, 'important');
    carousel.style.setProperty('margin', '0', 'important');
    carousel.style.setProperty('padding', '0', 'important');
    carousel.style.setProperty('z-index', '99999', 'important');
    
    console.log('🔧 Установлены размеры контейнера:', {
        screenWidth: screenWidth,
        isMobile: isMobile,
        width: width,
        height: height,
        computedWidth: window.getComputedStyle(carousel).width,
        computedHeight: window.getComputedStyle(carousel).height
    });
    
    // ДОПОЛНИТЕЛЬНАЯ ОТЛАДКА ПОЗИЦИОНИРОВАНИЯ
    console.log('🔧 ОТЛАДКА ПОЗИЦИОНИРОВАНИЯ:', {
        top: carousel.style.top,
        left: carousel.style.left,
        transform: carousel.style.transform,
        position: getComputedStyle(carousel).position,
        display: carousel.style.display,
        zIndex: getComputedStyle(carousel).zIndex,
        windowInnerWidth: window.innerWidth,
        windowInnerHeight: window.innerHeight
    });
    
    // Обработчик клика вне контейнера свайпера или на backdrop
    const handleOutsideClick = function(e) {
        // Проверяем, открыта ли карусель
        if (carousel.style.display !== 'block') return;
        
        // Проверяем, был ли клик вне контейнера карусели или на backdrop
        if (!carousel.contains(e.target) || (backdrop && e.target === backdrop)) {
            console.log('🔧 КЛИК ВНЕ КОНТЕЙНЕРА СВАЙПЕРА - ЗАКРЫВАЕМ');
            closeCarousel();
            // Удаляем обработчик после закрытия
            document.removeEventListener('click', handleOutsideClick);
            if (backdrop) {
                backdrop.removeEventListener('click', handleOutsideClick);
            }
        }
    };
    
    // Добавляем обработчик с небольшой задержкой, чтобы не сработал на клике по кнопке
    setTimeout(() => {
        document.addEventListener('click', handleOutsideClick);
        // Также добавляем обработчик на backdrop
        if (backdrop) {
            backdrop.addEventListener('click', handleOutsideClick);
        }
    }, 100);
    
    // Инициализируем Swiper с начальным слайдом
    setTimeout(() => {
        if (typeof Swiper !== 'undefined') {
            console.log('🔧 Инициализируем Swiper на слайде:', slideIndex);
            
            // Уничтожаем предыдущий экземпляр Swiper если есть
            if (window.userSwiper) {
                window.userSwiper.destroy(true, true);
            }
            
            window.userSwiper = new Swiper('#users-swiper', {
                slidesPerView: 1,
                spaceBetween: 0,
                centeredSlides: true,
                loop: false,
                effect: 'slide',
                speed: 300,
                initialSlide: slideIndex, // Начинаем с указанного слайда
                navigation: {
                    nextEl: '.swiper-button-next',
                    prevEl: '.swiper-button-prev',
                },
                on: {
                    init: function() {
                        console.log('🔧 Swiper инициализирован на слайде:', this.activeIndex);
                        
                        // Обновляем форматирование last_seen текстов
                        if (typeof updateLastSeenTexts === 'function') {
                            setTimeout(() => updateLastSeenTexts(), 100);
                        }
                        
                        // Повторно устанавливаем размеры после инициализации Swiper
                        setTimeout(() => {
                            const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                            const width = '330px';
                            const height = isMobile ? '515px' : '445px';
                            // Центрирование
                            const topPosition = '50%';
                            const leftPosition = '50%';
                            
                            carousel.style.setProperty('width', width, 'important');
                            carousel.style.setProperty('height', height, 'important');
                            carousel.style.setProperty('max-width', width, 'important');
                            carousel.style.setProperty('max-height', height, 'important');
                            carousel.style.setProperty('min-width', width, 'important');
                            carousel.style.setProperty('min-height', height, 'important');
                            carousel.style.setProperty('top', topPosition, 'important');
                            carousel.style.setProperty('left', leftPosition, 'important');
                            carousel.style.setProperty('right', 'auto', 'important');
                            carousel.style.setProperty('bottom', 'auto', 'important');
                            carousel.style.setProperty('transform', 'translate(-50%, -50%)', 'important');
                            
                            console.log('🔧 Размеры повторно установлены после Swiper init:', {
                                computedWidth: window.getComputedStyle(carousel).width,
                                computedHeight: window.getComputedStyle(carousel).height
                            });
                            
                            // Добавляем делегированный обработчик кликов на swiper-wrapper
                            console.log('🔧 Добавляем делегированный обработчик кликов');
                            const swiperWrapper = carousel.querySelector('.swiper-wrapper');
                            
                            if (swiperWrapper) {
                                // Используем делегирование событий
                                swiperWrapper.addEventListener('click', function(e) {
                                    // Ищем ближайший .user-item
                                    const userItem = e.target.closest('.user-item');
                                    
                                    if (userItem) {
                                        const telegramId = userItem.getAttribute('data-telegram-id');
                                        console.log('👤👤👤 КЛИК ПО КАРТОЧКЕ ПОЛЬЗОВАТЕЛЯ!', telegramId);
                                        console.log('👤 Event target:', e.target);
                                        console.log('👤 Closest user-item:', userItem);
                                        
                                        e.stopPropagation();
                                        e.preventDefault();
                                        
                                        if (telegramId) {
                                            console.log('✅ Переходим на страницу профиля:', `/user_profile/${telegramId}`);
                                            
                                            // Сохраняем текущий индекс слайда из родительского swiper-slide
                                            const swiperSlide = userItem.closest('.swiper-slide');
                                            if (swiperSlide && window.userSwiper) {
                                                const currentIndex = window.userSwiper.activeIndex;
                                                sessionStorage.setItem('topUsersSwiperIndex', currentIndex);
                                                sessionStorage.setItem('returnToSwiper', 'true');
                                                console.log('💾 Сохранен индекс слайда для возврата:', currentIndex);
                                            } else {
                                                console.warn('⚠️ Не удалось получить индекс Swiper, сохраняем 0');
                                                sessionStorage.setItem('topUsersSwiperIndex', '0');
                                                sessionStorage.setItem('returnToSwiper', 'true');
                                            }
                                            
                                            // Сохраняем текущие фильтры
                                            if (window.topUsersFilter && window.topUsersFilter.filters) {
                                                const filters = window.topUsersFilter.filters;
                                                sessionStorage.setItem('topUsersFilters', JSON.stringify(filters));
                                                console.log('💾 Сохранены фильтры:', filters);
                                            }
                                            
                                            window.location.href = `/user_profile/${telegramId}`;
                                        } else {
                                            console.error('❌ Не удалось получить telegram_id');
                                        }
                                    }
                                }, true); // Используем capture phase
                                
                                console.log('✅ Делегированный обработчик кликов добавлен на swiper-wrapper');
                            } else {
                                console.error('❌ swiper-wrapper не найден!');
                            }
                        }, 50);
                    }
                }
            });
        } else {
            console.error('🔧 Swiper не найден!');
        }
    }, 100);
};

// ГЛОБАЛЬНАЯ ФУНКЦИЯ ЗАКРЫТИЯ КАРУСЕЛИ
window.closeCarousel = function() {
    console.log('🔧 ЗАКРЫТИЕ КАРУСЕЛИ');
    
    const showBtn = document.getElementById('show-all-users');
    const carousel = document.getElementById('all-users-carousel');
    const backdrop = document.getElementById('carousel-backdrop');
    
    if (!carousel) {
        console.error('🔧 Карусель не найдена при закрытии');
        return;
    }
    
    // Уничтожаем Swiper
    if (window.userSwiper) {
        window.userSwiper.destroy(true, true);
        window.userSwiper = null;
    }
    
    // Скрываем backdrop
    if (backdrop) {
        backdrop.classList.remove('active');
    }
    
    // Скрываем карусель и удаляем класс active
    carousel.style.display = 'none';
    carousel.classList.remove('active');
    
    // Восстанавливаем скролл body и позицию
    const prevScroll = typeof window.scrollPositionBeforeSwiper !== 'undefined' ? window.scrollPositionBeforeSwiper : 0;

    // Убираем фиксацию тела и очищаем top, затем восстанавливаем позицию скролла
    document.body.style.overflow = '';
    document.body.style.position = '';
    document.body.style.top = '';
    document.body.style.left = '';
    document.body.style.right = '';
    document.body.style.width = '';

    if (prevScroll) {
        window.scrollTo(0, prevScroll);
        delete window.scrollPositionBeforeSwiper;
    }
    
    // Показываем кнопку "Показать всех" через удаление класса
    if (showBtn) {
        showBtn.classList.remove('hidden');
    }
    
    // Принудительно переприменяем все стили после манипуляций с document.body
    setTimeout(() => {
        // Триггерим reflow для переприменения CSS
        if (showBtn) {
            void showBtn.offsetHeight;
        }
        
        // Проверяем что стили кнопок применены корректно
        const resetBtn = document.getElementById('reset-filters');
        if (resetBtn) {
            void resetBtn.offsetHeight;
        }
        
        console.log('✅ Карусель закрыта, стили восстановлены и переприменены');
    }, 50);
};

// ГЛОБАЛЬНАЯ ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ КНОПОК КАРУСЕЛИ
window.initCarouselButtons = function() {
    console.log('🔧 ИНИЦИАЛИЗАЦИЯ КНОПОК И SWIPER');
    
    const showBtn = document.getElementById('show-all-users');
    const carousel = document.getElementById('all-users-carousel');
    
    console.log('🔧 Поиск элементов:', {
        showBtn: !!showBtn,
        carousel: !!carousel
    });
    
    if (showBtn && carousel) {
        console.log('🔧 Все элементы найдены, добавляем обработчики');
        
        // Удаляем старые обработчики (если есть)
        showBtn.onclick = null;
        
        // Обработчик для кнопки "Показать всех" - открываем с 4-го слайда (индекс 3)
        showBtn.onclick = function(e) {
            console.log('🔧 КНОПКА "ПОКАЗАТЬ ВСЕХ" НАЖАТА!');
            e.preventDefault();
            e.stopPropagation();
            
            // Открываем свайпер на 4-м слайде (индекс 3)
            openSwiperAtIndex(3);
        };
        
        // Обработчик закрытия по клавише ESC
        const handleEscKey = function(e) {
            if (e.key === 'Escape' || e.keyCode === 27) {
                if (carousel.style.display === 'block') {
                    closeCarousel();
                }
            }
        };

        // Обработчик клика внутри контейнера (на пустую область)
        carousel.addEventListener('click', function(e) {
            // Проверяем, был ли клик НЕ по user-item
            const clickedOnUserItem = e.target.closest('.user-item');
            
            if (clickedOnUserItem) {
                // Если клик по user-item - не закрываем, пусть обработается onclick
                console.log('🔧 КЛИК ПО КАРТОЧКЕ ПОЛЬЗОВАТЕЛЯ - НЕ ЗАКРЫВАЕМ');
                return;
            }
            
            // Проверяем, был ли клик по контейнеру или по swiper (не по user-item)
            const clickedOnCarousel = e.target === carousel;
            const clickedOnSwiper = e.target.classList.contains('swiper') || 
                                   e.target.classList.contains('swiper-wrapper') ||
                                   e.target.classList.contains('swiper-slide');
            
            if (clickedOnCarousel || clickedOnSwiper) {
                console.log('🔧 КЛИК ВНЕ ОБЛАСТИ КОНТЕНТА - ЗАКРЫВАЕМ');
                closeCarousel();
            }
        });
        
        // Добавляем обработчик ESC
        document.addEventListener('keydown', handleEscKey);
        
        // Сохраняем ссылку на обработчик для возможности удаления
        window.carouselEscHandler = handleEscKey;
        
        console.log('🔧 Обработчики добавлены успешно!');
        return true;
    } else {
        console.error('🔧 Не все элементы найдены!');
        return false;
    }
};

// Фильтрация топ пользователей
class TopUsersFilter {
    constructor() {
        this.filters = {
            gender: '',
            age: '',
            language: '',
            online: ''
        };
        
        this.init();
    }

    init() {
        console.log('🚀 TopUsersFilter: Инициализация');
        
        // Очищаем сохраненные фильтры из sessionStorage (если есть)
        // Они уже применены через URL при возврате
        const savedFilters = sessionStorage.getItem('topUsersFilters');
        if (savedFilters) {
            console.log('🧹 Очищаем сохраненные фильтры из sessionStorage');
            sessionStorage.removeItem('topUsersFilters');
        }
        
        // Загружаем фильтры из URL параметров (они будут там если вернулись с фильтрами)
        this.loadFiltersFromURL();
        
        this.bindEvents();
        console.log('✅ TopUsersFilter: Инициализация завершена');
        
        // Тестируем элементы
        this.testElements();
    }
    
    testElements() {
        console.log('🧪 Тестирование элементов фильтров:');
        const elements = {
            'gender-filter': document.getElementById('gender-filter'),
            'age-filter': document.getElementById('age-filter'),
            'language-filter': document.getElementById('language-filter'),
            'online-filter': document.getElementById('online-filter'),
            'reset-filters': document.getElementById('reset-filters')
        };
        
        for (const [name, element] of Object.entries(elements)) {
            if (element) {
                console.log(`✅ ${name}: найден`);
            } else {
                console.error(`❌ ${name}: НЕ НАЙДЕН!`);
            }
        }
    }

    bindEvents() {
        console.log('🔗 TopUsersFilter: Привязка событий...');
        
        // Обработчики для селектов фильтров
        const genderFilter = document.getElementById('gender-filter');
        const ageFilter = document.getElementById('age-filter');
        const languageFilter = document.getElementById('language-filter');
        const onlineFilter = document.getElementById('online-filter');
        const resetButton = document.getElementById('reset-filters');
        
        console.log('🔍 Найденные элементы:', {
            genderFilter: !!genderFilter,
            ageFilter: !!ageFilter,
            languageFilter: !!languageFilter,
            onlineFilter: !!onlineFilter,
            resetButton: !!resetButton
        });
        
        // Проверяем, что все необходимые элементы найдены
        if (!genderFilter) console.warn('⚠️ gender-filter не найден');
        if (!ageFilter) console.warn('⚠️ age-filter не найден');
        if (!languageFilter) console.warn('⚠️ language-filter не найден');
        if (!onlineFilter) console.warn('⚠️ online-filter не найден');
        if (!resetButton) console.warn('⚠️ reset-filters кнопка не найдена');
        
        genderFilter?.addEventListener('change', (e) => {
            console.log('👤 Gender filter changed:', e.target.value);
            this.filters.gender = e.target.value;
            this.applyFilters();
        });

        ageFilter?.addEventListener('change', (e) => {
            console.log('🎂 Age filter changed:', e.target.value);
            this.filters.age = e.target.value;
            this.applyFilters();
        });

        languageFilter?.addEventListener('change', (e) => {
            console.log('💻 Language filter changed:', e.target.value);
            this.filters.language = e.target.value;
            this.applyFilters();
        });

        // ratingFilter?.addEventListener('change', (e) => { // Убран, так как нет в HTML
        //     console.log('⭐ Rating filter changed:', e.target.value);
        //     this.filters.rating = e.target.value;
        //     this.applyFilters();
        // });

        // Добавляем обработчик для фильтра онлайн статуса
        if (onlineFilter) {
            console.log('✅ Online filter найден, привязываем обработчик');
            onlineFilter.addEventListener('change', (e) => {
                console.log('🟢 Online filter changed:', e.target.value);
                this.filters.online = e.target.value;
                console.log('🟢 Обновленные фильтры:', this.filters);
                this.applyFilters();
            });
        } else {
            console.error('❌ Online filter не найден!');
        }

        // Кнопка сброса фильтров
        if (resetButton) {
            console.log('🔗 Привязываем обработчик к кнопке сброса');
            resetButton.addEventListener('click', (e) => {
                console.log('🔄 Reset filters clicked - обработчик сработал!');
                e.preventDefault();
                this.resetFilters();
            });
        } else {
            console.error('❌ Кнопка сброса не найдена!');
        }
        
        console.log('✅ TopUsersFilter: События привязаны');
    }

    loadFiltersFromURL() {
        console.log('🌐🌐🌐 ЗАГРУЗКА ФИЛЬТРОВ ИЗ URL 🌐🌐🌐');
        console.log('🔍 Текущий URL:', window.location.href);
        console.log('🔍 Query string:', window.location.search);
        
        const urlParams = new URLSearchParams(window.location.search);
        console.log('🔍 URL параметры:', Object.fromEntries(urlParams));
        
        this.filters.gender = urlParams.get('gender') || '';
        this.filters.age = urlParams.get('age') || '';
        this.filters.language = urlParams.get('language_pref') || '';
        this.filters.online = urlParams.get('online_only') || '';

        console.log('📦 Загруженные фильтры:', this.filters);

        // Устанавливаем значения в селекты
        console.log('🎯 Устанавливаем значения в селекты...');
        this.setSelectValue('gender-filter', this.filters.gender);
        this.setSelectValue('age-filter', this.filters.age);
        this.setSelectValue('language-filter', this.filters.language);
        this.setSelectValue('online-filter', this.filters.online);
        
        console.log('✅ Фильтры из URL загружены и применены к селектам');
    }

    setSelectValue(selectId, value) {
        const select = document.getElementById(selectId);
        if (select) {
            select.value = value;
            console.log(`🔄 Установлено значение для ${selectId}: ${value}`);
        } else {
            console.warn(`⚠️ Элемент ${selectId} не найден для установки значения ${value}`);
        }
    }


    applyFilters() {
        console.log('🔍 TopUsersFilter: Применение фильтров', this.filters);
        console.log('🔍 Текущий URL:', window.location.href);
        console.log('🔍 Фильтры активны:', {
            gender: this.filters.gender,
            age: this.filters.age,
            language: this.filters.language,
            online: this.filters.online
        });
        // Обновляем контент через AJAX вместо перезагрузки страницы
        this.updateContentWithFilters();
    }

    updateContentWithFilters() {
        console.log('🔄 TopUsersFilter: updateContentWithFilters вызван');
        console.log('🔄 Текущие фильтры:', this.filters);
        
        const url = new URL(window.location);
        
        // Удаляем старые параметры фильтров
        url.searchParams.delete('gender');
        url.searchParams.delete('age');
        url.searchParams.delete('language_pref');
        url.searchParams.delete('online_only');

        // Добавляем новые параметры фильтров
        if (this.filters.gender) {
            url.searchParams.set('gender', this.filters.gender);
        }
        if (this.filters.age) {
            url.searchParams.set('age', this.filters.age);
        }
        if (this.filters.language) {
            url.searchParams.set('language_pref', this.filters.language);
        }
        if (this.filters.online) {
            url.searchParams.set('online_only', this.filters.online);
        }
        // if (this.filters.rating) { // Убран
        //     url.searchParams.set('rating', this.filters.rating);
        // }

        console.log('🔄 Обновляем контент через AJAX:', url.toString());
        
        // Обновляем контент через AJAX
        fetch(url.toString(), {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.text())
        .then(html => {
            // Сохраняем текущие значения фильтров
            const currentFilters = {
                gender: document.getElementById('gender-filter')?.value || '',
                age: document.getElementById('age-filter')?.value || '',
                language: document.getElementById('language-filter')?.value || '',
                online: document.getElementById('online-filter')?.value || ''
            };
            
            console.log('💾 Сохраняем фильтры:', currentFilters);
            
            // Обновляем только контент страницы
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newContent = doc.querySelector('.top-users-container');
            const currentContent = document.querySelector('.top-users-container');
            
            if (newContent && currentContent) {
                // Сохраняем только список пользователей, не трогая фильтры
                const newUserList = newContent.querySelector('.top-users-list');
                const currentUserList = currentContent.querySelector('.top-users-list');
                
                if (newUserList && currentUserList) {
                    currentUserList.innerHTML = newUserList.innerHTML;
                    console.log('✅ Список пользователей обновлен через AJAX');
                    
                    // Обновляем форматирование last_seen текстов в топ-5
                    if (typeof updateLastSeenTexts === 'function') {
                        updateLastSeenTexts();
                    }
                } else {
                    // Fallback - обновляем весь контент
                    currentContent.innerHTML = newContent.innerHTML;
                    console.log('✅ Контент обновлен через AJAX (fallback)');
                    
                    // Обновляем форматирование last_seen текстов
                    if (typeof updateLastSeenTexts === 'function') {
                        updateLastSeenTexts();
                    }
                }
                
                // ОБНОВЛЯЕМ МОДАЛЬНОЕ ОКНО СВАЙПЕРА (оно вне контейнера)
                const newCarousel = doc.querySelector('.all-users-carousel');
                const currentCarousel = document.querySelector('.all-users-carousel');
                
                if (newCarousel && currentCarousel) {
                    // Уничтожаем старый Swiper если он существует
                    if (window.userSwiper) {
                        console.log('🔄 Уничтожаем старый Swiper перед обновлением');
                        window.userSwiper.destroy(true, true);
                        window.userSwiper = null;
                    }
                    
                    // Обновляем контент карусели
                    currentCarousel.innerHTML = newCarousel.innerHTML;
                    console.log('✅ Модальное окно свайпера обновлено с учетом фильтров');
                    
                    // Обновляем форматирование last_seen текстов
                    if (typeof updateLastSeenTexts === 'function') {
                        updateLastSeenTexts();
                    }
                }
                
                // Восстанавливаем значения фильтров
                setTimeout(() => {
                    if (currentFilters.gender) {
                        const genderSelect = document.getElementById('gender-filter');
                        if (genderSelect) genderSelect.value = currentFilters.gender;
                    }
                    if (currentFilters.age) {
                        const ageSelect = document.getElementById('age-filter');
                        if (ageSelect) ageSelect.value = currentFilters.age;
                    }
                    if (currentFilters.language) {
                        const languageSelect = document.getElementById('language-filter');
                        if (languageSelect) languageSelect.value = currentFilters.language;
                    }
                    if (currentFilters.online) {
                        const onlineSelect = document.getElementById('online-filter');
                        if (onlineSelect) onlineSelect.value = currentFilters.online;
                    }
                    console.log('🔄 Фильтры восстановлены');
                    
                    // Переинициализируем обработчики событий только если обновили весь контент
                    if (!newUserList || !currentUserList) {
                        this.bindEvents();
                    }
                    
                    // Переинициализируем обработчики кнопок карусели
                    if (typeof window.initCarouselButtons === 'function') {
                        console.log('🔄 Переинициализация кнопок карусели');
                        window.initCarouselButtons();
                    }
                }, 100);
            } else {
                // Fallback - перезагружаем страницу
                window.location.href = url.toString();
            }
        })
        .catch(error => {
            console.error('❌ Ошибка AJAX запроса:', error);
            // Fallback - перезагружаем страницу
            window.location.href = url.toString();
        });
    }

    reloadWithFilters() {
        console.log('🔄 TopUsersFilter: reloadWithFilters вызван');
        console.log('🔄 Текущий URL:', window.location.href);
        console.log('🔄 Текущие фильтры:', this.filters);
        
        const url = new URL(window.location);
        
        // Удаляем старые параметры фильтров
        url.searchParams.delete('gender');
        url.searchParams.delete('age');
        url.searchParams.delete('language_pref');
        url.searchParams.delete('online_only');

        // Добавляем новые параметры фильтров
        if (this.filters.gender) {
            url.searchParams.set('gender', this.filters.gender);
            console.log('➕ Добавлен gender:', this.filters.gender);
        }
        if (this.filters.age) {
            url.searchParams.set('age', this.filters.age);
            console.log('➕ Добавлен age:', this.filters.age);
        }
        if (this.filters.language) {
            url.searchParams.set('language_pref', this.filters.language);
            console.log('➕ Добавлен language_pref:', this.filters.language);
        }
        if (this.filters.online) {
            url.searchParams.set('online_only', this.filters.online);
            console.log('➕ Добавлен online_only:', this.filters.online);
        }

        console.log('🔄 Новый URL:', url.toString());
        console.log('🔄 Перезагружаем страницу...');

        // Перезагружаем страницу
        window.location.href = url.toString();
    }


    resetFilters() {
        console.log('🔄 Reset filters clicked - сброс фильтров');
        console.log('🔄 Текущие фильтры до сброса:', this.filters);
        console.log('🔄 Кнопка сброса нажата, начинаем сброс...');
        
        this.filters = {
            gender: '',
            age: '',
            language: '',
            online: ''
        };

        // Сбрасываем селекты
        this.setSelectValue('gender-filter', '');
        this.setSelectValue('age-filter', '');
        this.setSelectValue('language-filter', '');
        this.setSelectValue('online-filter', '');
        
        console.log('🔄 Фильтры сброшены в объекте:', this.filters);

        // Обновляем контент через AJAX без фильтров
        const url = new URL(window.location);
        url.searchParams.delete('gender');
        url.searchParams.delete('age');
        url.searchParams.delete('language_pref');
        url.searchParams.delete('online_only');
        
        console.log('🔄 Reset filters - обновляем контент через AJAX:', url.toString());
        
        // Обновляем контент через AJAX
        fetch(url.toString(), {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.text())
        .then(html => {
            // Обновляем только контент страницы
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newContent = doc.querySelector('.top-users-container');
            const currentContent = document.querySelector('.top-users-container');
            
            if (newContent && currentContent) {
                // Сохраняем только список пользователей, не трогая фильтры
                const newUserList = newContent.querySelector('.top-users-list');
                const currentUserList = currentContent.querySelector('.top-users-list');
                
                if (newUserList && currentUserList) {
                    currentUserList.innerHTML = newUserList.innerHTML;
                    console.log('✅ Фильтры сброшены, список пользователей обновлен');
                    
                    // Обновляем форматирование last_seen текстов в топ-5
                    if (typeof updateLastSeenTexts === 'function') {
                        updateLastSeenTexts();
                    }
                } else {
                    // Fallback - обновляем весь контент
                    currentContent.innerHTML = newContent.innerHTML;
                    console.log('✅ Фильтры сброшены, контент обновлен (fallback)');
                    
                    // Обновляем форматирование last_seen текстов
                    if (typeof updateLastSeenTexts === 'function') {
                        updateLastSeenTexts();
                    }
                }
                
                // ОБНОВЛЯЕМ МОДАЛЬНОЕ ОКНО СВАЙПЕРА при сбросе фильтров
                const newCarousel = doc.querySelector('.all-users-carousel');
                const currentCarousel = document.querySelector('.all-users-carousel');
                
                if (newCarousel && currentCarousel) {
                    // Уничтожаем старый Swiper если он существует
                    if (window.userSwiper) {
                        console.log('🔄 Уничтожаем старый Swiper перед обновлением (сброс)');
                        window.userSwiper.destroy(true, true);
                        window.userSwiper = null;
                    }
                    
                    // Обновляем контент карусели
                    currentCarousel.innerHTML = newCarousel.innerHTML;
                    console.log('✅ Модальное окно свайпера обновлено после сброса фильтров');
                    
                    // Обновляем форматирование last_seen текстов
                    if (typeof updateLastSeenTexts === 'function') {
                        updateLastSeenTexts();
                    }
                }
                
                // Переинициализируем обработчики кнопок карусели после сброса фильтров
                setTimeout(() => {
                    if (typeof window.initCarouselButtons === 'function') {
                        console.log('🔄 Переинициализация кнопок карусели после сброса');
                        window.initCarouselButtons();
                    }
                }, 100);
            } else {
                // Fallback - перезагружаем страницу
                window.location.href = url.toString();
            }
        })
        .catch(error => {
            console.error('❌ Ошибка AJAX запроса:', error);
            // Fallback - перезагружаем страницу
            window.location.href = url.toString();
        });
    }
}

// Инициализация фильтра при загрузке страницы
// Инициализация теперь происходит из HTML шаблона
// document.addEventListener('DOMContentLoaded', () => {
//     new TopUsersFilter();
// });

// Делаем фильтр глобальным для отладки
window.TopUsersFilter = TopUsersFilter;

// Функция для переинициализации при SPA навигации
window.reinitializeTopUsersPage = function() {
    console.log('🔄 reinitializeTopUsersPage вызван для SPA навигации');
    
    // Переинициализируем фильтры
    if (window.TopUsersFilter) {
        // Удаляем старый экземпляр если он есть
        if (window.topUsersFilter) {
            console.log('🔄 Удаляем старый экземпляр TopUsersFilter');
            // Можно добавить метод destroy если нужно
        }
        
        // Создаем новый экземпляр
        window.topUsersFilter = new window.TopUsersFilter();
        console.log('✅ TopUsersFilter переинициализирован для SPA навигации');
    } else {
        console.error('❌ TopUsersFilter class не найден для переинициализации');
    }
};

// Функция для форматирования времени "был онлайн X назад"
function formatLastSeen(lastSeenDate) {
    if (!lastSeenDate) return null;
    
    const now = new Date();
    const lastSeen = new Date(lastSeenDate);
    const diffMs = now - lastSeen;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    const currentLang = window.currentLanguage || 'ru';
    
    if (diffMins < 1) {
        return currentLang === 'en' ? 'just now' : 'только что';
    } else if (diffMins < 60) {
        const unit = currentLang === 'en' ? 
            (diffMins === 1 ? 'minute' : 'minutes') :
            (diffMins === 1 ? 'минуту' : diffMins < 5 ? 'минуты' : 'минут');
        return currentLang === 'en' ? 
            `${diffMins} ${unit} ago` : 
            `${diffMins} ${unit} назад`;
    } else if (diffHours < 24) {
        const unit = currentLang === 'en' ? 
            (diffHours === 1 ? 'hour' : 'hours') :
            (diffHours === 1 ? 'час' : diffHours < 5 ? 'часа' : 'часов');
        return currentLang === 'en' ? 
            `${diffHours} ${unit} ago` : 
            `${diffHours} ${unit} назад`;
    } else if (diffDays < 7) {
        const unit = currentLang === 'en' ? 
            (diffDays === 1 ? 'day' : 'days') :
            (diffDays === 1 ? 'день' : diffDays < 5 ? 'дня' : 'дней');
        return currentLang === 'en' ? 
            `${diffDays} ${unit} ago` : 
            `${diffDays} ${unit} назад`;
    } else {
        const weeks = Math.floor(diffDays / 7);
        const unit = currentLang === 'en' ? 
            (weeks === 1 ? 'week' : 'weeks') :
            (weeks === 1 ? 'неделю' : weeks < 5 ? 'недели' : 'недель');
        return currentLang === 'en' ? 
            `${weeks} ${unit} ago` : 
            `${weeks} ${unit} назад`;
    }
}

// Функция для обновления всех last-seen текстов
function updateLastSeenTexts() {
    const lastSeenElements = document.querySelectorAll('.last-seen-text[data-last-seen]');
    const currentLang = window.currentLanguage || 'ru';
    const prefix = currentLang === 'en' ? 'Last seen' : 'Был в сети';
    
    lastSeenElements.forEach(element => {
        const lastSeenDate = element.getAttribute('data-last-seen');
        if (lastSeenDate) {
            const formattedTime = formatLastSeen(lastSeenDate);
            if (formattedTime) {
                element.textContent = `${prefix} ${formattedTime}`;
            }
        }
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    updateLastSeenTexts();
    
    // Проверяем, нужно ли восстановить модальное окно после возврата
    const shouldReturnToSwiper = sessionStorage.getItem('returnToSwiper');
    const savedSwiperIndex = sessionStorage.getItem('topUsersSwiperIndex');
    
    if (shouldReturnToSwiper === 'true' && savedSwiperIndex !== null) {
        console.log('🔄 Восстановление модального окна Swiper на слайде:', savedSwiperIndex);
        
        // Очищаем флаги
        sessionStorage.removeItem('returnToSwiper');
        sessionStorage.removeItem('topUsersSwiperIndex');
        
        // Открываем модальное окно на сохраненном слайде с минимальной задержкой
        setTimeout(() => {
            const slideIndex = parseInt(savedSwiperIndex, 10);
            if (typeof window.openSwiperAtIndex === 'function') {
                window.openSwiperAtIndex(slideIndex);
                console.log('✅ Модальное окно восстановлено на слайде:', slideIndex);
            }
        }, 100);
    }
});

// Обновление при смене языка
if (window.localizationService) {
    const originalUpdateInterface = window.localizationService.updateInterface;
    window.localizationService.updateInterface = function() {
        originalUpdateInterface.call(this);
        updateLastSeenTexts();
    };
}

// Экспортируем функции глобально
window.formatLastSeen = formatLastSeen;
window.updateLastSeenTexts = updateLastSeenTexts;
