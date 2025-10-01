// Фильтрация топ пользователей
class TopUsersFilter {
    constructor() {
        this.filters = {
            gender: '',
            age: '',
            language: '',
            grade: ''
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
            'grade-filter': document.getElementById('grade-filter'),
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
        // const ratingFilter = document.getElementById('rating-filter'); // Убран, так как нет в HTML
        const resetButton = document.getElementById('reset-filters');
        
        console.log('🔍 Найденные элементы:', {
            genderFilter: !!genderFilter,
            ageFilter: !!ageFilter,
            languageFilter: !!languageFilter,
            resetButton: !!resetButton
        });
        
        // Проверяем, что все необходимые элементы найдены
        if (!genderFilter) console.warn('⚠️ gender-filter не найден');
        if (!ageFilter) console.warn('⚠️ age-filter не найден');
        if (!languageFilter) console.warn('⚠️ language-filter не найден');
        // if (!ratingFilter) console.warn('⚠️ rating-filter не найден'); // Убран
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

        // Добавляем обработчик для фильтра грейда
        const gradeFilter = document.getElementById('grade-filter');
        if (gradeFilter) {
            console.log('✅ Grade filter найден, привязываем обработчик');
            gradeFilter.addEventListener('change', (e) => {
                console.log('🎯 Grade filter changed:', e.target.value);
                this.filters.grade = e.target.value;
                console.log('🎯 Обновленные фильтры:', this.filters);
                this.applyFilters();
            });
        } else {
            console.error('❌ Grade filter не найден!');
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
        this.filters.grade = urlParams.get('grade') || '';
        // this.filters.rating = urlParams.get('rating') || ''; // Убран

        // Устанавливаем значения в селекты
        this.setSelectValue('gender-filter', this.filters.gender);
        this.setSelectValue('age-filter', this.filters.age);
        this.setSelectValue('language-filter', this.filters.language);
        this.setSelectValue('grade-filter', this.filters.grade);
        // this.setSelectValue('rating-filter', this.filters.rating); // Убран
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
            grade: this.filters.grade
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
        url.searchParams.delete('grade');

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
        if (this.filters.grade) {
            url.searchParams.set('grade', this.filters.grade);
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
                grade: document.getElementById('grade-filter')?.value || '',
                // rating: document.getElementById('rating-filter')?.value || '' // Убран
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
                    if (currentFilters.grade) {
                        const gradeSelect = document.getElementById('grade-filter');
                        if (gradeSelect) gradeSelect.value = currentFilters.grade;
                    }
                    // if (currentFilters.rating) { // Убран
                    //     const ratingSelect = document.getElementById('rating-filter');
                    //     if (ratingSelect) ratingSelect.value = currentFilters.rating;
                    // }
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
        url.searchParams.delete('grade');
        // url.searchParams.delete('rating'); // Убран

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
        if (this.filters.grade) {
            url.searchParams.set('grade', this.filters.grade);
            console.log('➕ Добавлен grade:', this.filters.grade);
        }
        // if (this.filters.rating) { // Убран
        //     url.searchParams.set('rating', this.filters.rating);
        //     console.log('➕ Добавлен rating:', this.filters.rating);
        // }

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
            grade: ''
        };

        // Сбрасываем селекты
        this.setSelectValue('gender-filter', '');
        this.setSelectValue('age-filter', '');
        this.setSelectValue('language-filter', '');
        this.setSelectValue('grade-filter', '');
        // this.setSelectValue('rating-filter', ''); // Убран
        
        console.log('🔄 Фильтры сброшены в объекте:', this.filters);

        // Обновляем контент через AJAX без фильтров
        const url = new URL(window.location);
        url.searchParams.delete('gender');
        url.searchParams.delete('age');
        url.searchParams.delete('language_pref');
        url.searchParams.delete('grade');
        // url.searchParams.delete('rating'); // Убран
        
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
