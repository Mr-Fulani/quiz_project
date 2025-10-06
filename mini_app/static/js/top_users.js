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
        this.bindEvents();
        this.loadFiltersFromURL();
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
        const urlParams = new URLSearchParams(window.location.search);
        
        this.filters.gender = urlParams.get('gender') || '';
        this.filters.age = urlParams.get('age') || '';
        this.filters.language = urlParams.get('language_pref') || '';
        this.filters.online = urlParams.get('online_only') || '';

        // Устанавливаем значения в селекты
        this.setSelectValue('gender-filter', this.filters.gender);
        this.setSelectValue('age-filter', this.filters.age);
        this.setSelectValue('language-filter', this.filters.language);
        this.setSelectValue('online-filter', this.filters.online);
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
                } else {
                    // Fallback - обновляем весь контент
                    currentContent.innerHTML = newContent.innerHTML;
                    console.log('✅ Контент обновлен через AJAX (fallback)');
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
                } else {
                    // Fallback - обновляем весь контент
                    currentContent.innerHTML = newContent.innerHTML;
                    console.log('✅ Фильтры сброшены, контент обновлен (fallback)');
                }
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
