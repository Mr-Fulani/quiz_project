// Фильтрация топ пользователей
class TopUsersFilter {
    constructor() {
        this.filters = {
            gender: '',
            age: '',
            language: '',
            rating: ''
        };
        
        this.init();
    }

    init() {
        console.log('🚀 TopUsersFilter: Инициализация');
        this.bindEvents();
        this.loadFiltersFromURL();
        console.log('✅ TopUsersFilter: Инициализация завершена');
        // Убираем автоматический вызов applyFilters() при инициализации
    }

    bindEvents() {
        console.log('🔗 TopUsersFilter: Привязка событий...');
        
        // Обработчики для селектов фильтров
        const genderFilter = document.getElementById('gender-filter');
        const ageFilter = document.getElementById('age-filter');
        const languageFilter = document.getElementById('language-filter');
        const ratingFilter = document.getElementById('rating-filter');
        const resetButton = document.getElementById('reset-filters');
        
        console.log('🔍 Найденные элементы:', {
            genderFilter: !!genderFilter,
            ageFilter: !!ageFilter,
            languageFilter: !!languageFilter,
            ratingFilter: !!ratingFilter,
            resetButton: !!resetButton
        });
        
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

        ratingFilter?.addEventListener('change', (e) => {
            console.log('⭐ Rating filter changed:', e.target.value);
            this.filters.rating = e.target.value;
            this.applyFilters();
        });

        // Кнопка сброса фильтров
        resetButton?.addEventListener('click', () => {
            console.log('🔄 Reset filters clicked');
            this.resetFilters();
        });
        
        console.log('✅ TopUsersFilter: События привязаны');
    }

    loadFiltersFromURL() {
        const urlParams = new URLSearchParams(window.location.search);
        
        this.filters.gender = urlParams.get('gender') || '';
        this.filters.age = urlParams.get('age') || '';
        this.filters.language = urlParams.get('language') || '';
        this.filters.rating = urlParams.get('rating') || '';

        // Устанавливаем значения в селекты
        this.setSelectValue('gender-filter', this.filters.gender);
        this.setSelectValue('age-filter', this.filters.age);
        this.setSelectValue('language-filter', this.filters.language);
        this.setSelectValue('rating-filter', this.filters.rating);
    }

    setSelectValue(selectId, value) {
        const select = document.getElementById(selectId);
        if (select) {
            select.value = value;
        }
    }


    applyFilters() {
        console.log('🔍 TopUsersFilter: Применение фильтров', this.filters);
        // Перезагружаем страницу с новыми параметрами фильтрации
        this.reloadWithFilters();
    }

    reloadWithFilters() {
        console.log('🔄 TopUsersFilter: reloadWithFilters вызван');
        console.log('🔄 Текущий URL:', window.location.href);
        console.log('🔄 Текущие фильтры:', this.filters);
        
        const url = new URL(window.location);
        
        // Удаляем старые параметры фильтров
        url.searchParams.delete('gender');
        url.searchParams.delete('age');
        url.searchParams.delete('language');
        url.searchParams.delete('rating');

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
            url.searchParams.set('language', this.filters.language);
            console.log('➕ Добавлен language:', this.filters.language);
        }
        if (this.filters.rating) {
            url.searchParams.set('rating', this.filters.rating);
            console.log('➕ Добавлен rating:', this.filters.rating);
        }

        console.log('🔄 Новый URL:', url.toString());
        console.log('🔄 Перезагружаем страницу...');

        // Перезагружаем страницу
        window.location.href = url.toString();
    }


    resetFilters() {
        this.filters = {
            gender: '',
            age: '',
            language: '',
            rating: ''
        };

        // Сбрасываем селекты
        this.setSelectValue('gender-filter', '');
        this.setSelectValue('age-filter', '');
        this.setSelectValue('language-filter', '');
        this.setSelectValue('rating-filter', '');

        // Перезагружаем страницу без фильтров
        const url = new URL(window.location);
        url.searchParams.delete('gender');
        url.searchParams.delete('age');
        url.searchParams.delete('language');
        url.searchParams.delete('rating');
        window.location.href = url.toString();
    }
}

// Инициализация фильтра при загрузке страницы
// Инициализация теперь происходит из HTML шаблона
// document.addEventListener('DOMContentLoaded', () => {
//     new TopUsersFilter();
// });

// Делаем фильтр глобальным для отладки
window.TopUsersFilter = TopUsersFilter;
