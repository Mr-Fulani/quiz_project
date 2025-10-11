/**
 * JavaScript модуль для управления профилем пользователя в Telegram Mini App.
 * Обеспечивает загрузку и отображение данных профиля, а также
 * предоставляет глобальную функцию для инициализации при SPA-навигации.
 */

// Обертка для инкапсуляции логики и предотвращения засорения глобальной области
(function(window) {
    console.log('🚀 Profile.js загружен!');
    
    // Переменные состояния модуля
    let isLoading = false;
    
    // Функция для получения актуального состояния Telegram WebApp
    function getTelegramWebApp() {
        return window.Telegram?.WebApp;
    }

    // Функция для получения telegram_id из URL параметров
    function getTelegramIdFromURL() {
        const urlParams = new URLSearchParams(window.location.search);
        const telegramId = urlParams.get('telegram_id');
        console.log('🔍 Telegram ID из URL:', telegramId);
        return telegramId ? parseInt(telegramId) : null;
    }

    // Простая функция для показа уведомлений
    function showNotification(key, type, element, message) {
        console.log(`📢 Notification [${type}]: ${message}`);
        // Показываем уведомление через Telegram WebApp, если доступно
        const tg = getTelegramWebApp();
        if (tg && tg.showAlert) {
            try {
                tg.showAlert(message);
            } catch (e) {
                console.warn('Telegram showAlert failed:', e);
                alert(message);
            }
        } else {
            // Fallback к обычному alert
            alert(message);
        }
    }

    // Простая заглушка для translations.get
    function getTranslation(key, fallback) {
        return fallback || key;
    }

    // --- DOM Элементы ---
    function getDOMElements() {
        return {
            loader: document.getElementById('loader'),
            profileContainer: document.getElementById('profile-container'),
            name: document.getElementById('profile-name'),
            username: document.getElementById('profile-username'),
            avatar: document.getElementById('profile-avatar'),
            socials: document.getElementById('social-links-container'),
            editProfileBtn: document.getElementById('edit-profile-btn'),
            editModal: document.getElementById('edit-modal'),
            closeModalBtn: document.querySelector('#edit-modal .close'),
            cancelEditBtn: document.querySelector('#edit-modal .btn-cancel'),
            editProfileForm: document.getElementById('edit-profile-form'),
            avatarInput: document.getElementById('avatar-input'),
            avatarPreview: document.getElementById('avatar-preview'),
            firstNameInput: document.getElementById('first-name-input'),
            lastNameInput: document.getElementById('last-name-input'),
            websiteInput: document.getElementById('website-input'),
            telegramInput: document.getElementById('telegram-input'),
            githubInput: document.getElementById('github-input'),
            linkedinInput: document.getElementById('linkedin-input'),
            instagramInput: document.getElementById('instagram-input'),
            facebookInput: document.getElementById('facebook-input'),
            youtubeInput: document.getElementById('youtube-input'),
            refreshBtn: document.getElementById('refresh-btn'),
        };
    }

    // --- Функции обновления UI ---

    function updateAvatar(avatarUrl) {
        console.log('🖼️ updateAvatar вызван с URL:', avatarUrl);
        const { avatar } = getDOMElements();
        if (avatar) {
            let finalUrl = '/static/images/default_avatar.png';
            
            if (avatarUrl) {
                // Если URL содержит полный путь с доменом, используем его как есть
                if (avatarUrl.startsWith('http')) {
                    finalUrl = avatarUrl;
                } else {
                    // Для относительных URL добавляем правильный базовый URL
                    finalUrl = avatarUrl;
                }
                
                // Добавляем cache-busting параметр для предотвращения кэширования
                const separator = finalUrl.includes('?') ? '&' : '?';
                finalUrl += `${separator}t=${Date.now()}`;
            }
            
            console.log('🖼️ Устанавливаем аватарку:', finalUrl);
            avatar.src = finalUrl;
            avatar.style.display = 'block';
            
            // Принудительно обновляем аватарку
            avatar.onload = function() {
                console.log('✅ Аватарка успешно загружена');
            };
            avatar.onerror = function() {
                console.log('❌ Ошибка загрузки аватарки, используем дефолтную');
                avatar.src = '/static/images/default_avatar.png';
                avatar.onerror = null;
            };
        }
    }

    // Функция для обновления переводов в профессиональной информации
    function updateProfessionalInfoTranslations() {
        console.log('🌐 Обновляем переводы в профессиональной информации');

        // Обновляем пол
        const genderElement = document.getElementById('profile-gender');
        if (genderElement) {
            const currentGender = genderElement.getAttribute('data-gender');
            if (currentGender) {
                // Получаем переводы в зависимости от текущего языка
                const currentLang = window.currentLanguage || 'en';
                let genderText;
                
                if (currentLang === 'en') {
                    genderText = currentGender === 'male' ? 'Male' : 'Female';
                } else {
                    genderText = currentGender === 'male' ? 'Мужской' : 'Женский';
                }
                
                genderElement.textContent = genderText;
            } else {
                const currentLang = window.currentLanguage || 'en';
                genderElement.textContent = currentLang === 'en' ? 'Not specified' : 'Не указан';
            }
        }
        
        // Обновляем дату рождения
        const birthDateElement = document.getElementById('profile-birth-date');
        if (birthDateElement) {
            const currentLang = window.currentLanguage || 'en';
            const birthDate = birthDateElement.getAttribute('data-date');
            
            if (birthDate) {
                // Форматируем дату в зависимости от языка
                const date = new Date(birthDate);
                let formattedDate;
                
                if (currentLang === 'en') {
                    formattedDate = date.toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                    });
                } else {
                    formattedDate = date.toLocaleDateString('ru-RU', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                    });
                }
                
                birthDateElement.textContent = formattedDate;
            } else {
                birthDateElement.textContent = currentLang === 'en' ? 'Not specified' : 'Не указана';
            }
        }
        
        // Обновляем грейд
        const gradeElement = document.getElementById('profile-grade');
        if (gradeElement) {
            const currentGrade = gradeElement.getAttribute('data-grade');
            if (currentGrade) {
                const gradeLabels = {
                    'junior': (window.translations && window.translations.grade_junior) ? window.translations.grade_junior : 'Junior',
                    'middle': (window.translations && window.translations.grade_middle) ? window.translations.grade_middle : 'Middle', 
                    'senior': (window.translations && window.translations.grade_senior) ? window.translations.grade_senior : 'Senior'
                };
                gradeElement.textContent = gradeLabels[currentGrade] || currentGrade;
            } else {
                gradeElement.textContent = (window.translations && window.translations.not_specified) ? window.translations.not_specified : 'Не указан';
            }
        }
        
        // Обновляем технологии (если не указаны)
        const technologiesElement = document.getElementById('profile-technologies');
        if (technologiesElement && technologiesElement.querySelector('.no-data')) {
            technologiesElement.innerHTML = `<span class="no-data">${(window.translations && window.translations) ? window.translations.no_technologies || 'Технологии не указаны' : 'Технологии не указаны'}</span>`;
        }
    }

    function updateProfessionalInfo(userData) {
        console.log('💼 updateProfessionalInfo вызван с данными:', userData);
        console.log('🔍 userData.gender:', userData.gender);
        console.log('🔍 userData.birth_date:', userData.birth_date);
        
        // Обновляем пол
        const genderElement = document.getElementById('profile-gender');
        if (genderElement) {
            if (userData.gender) {
                genderElement.setAttribute('data-gender', userData.gender);
                const genderLabels = {
                    'male': (window.translations && window.translations) ? window.translations.male || 'Мужской' : 'Мужской',
                    'female': (window.translations && window.translations) ? window.translations.female || 'Женский' : 'Женский'
                };
                const genderText = genderLabels[userData.gender] || userData.gender;
                genderElement.textContent = genderText;
                console.log(`👤 Пол установлен: ${genderText} (${userData.gender})`);
            } else {
                genderElement.removeAttribute('data-gender');
                genderElement.textContent = (window.translations && window.translations) ? window.translations.gender_unknown || 'Не указан' : 'Не указан';
            }
        }
        
        // Обновляем дату рождения
        const birthDateElement = document.getElementById('profile-birth-date');
        if (birthDateElement) {
            if (userData.birth_date) {
                birthDateElement.setAttribute('data-date', userData.birth_date);
                // Форматируем дату для отображения
                const birthDate = new Date(userData.birth_date);
                const formattedDate = birthDate.toLocaleDateString('ru-RU', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                });
                birthDateElement.textContent = formattedDate;
                console.log(`📅 Дата рождения установлена: ${formattedDate} (${userData.birth_date})`);
            } else {
                birthDateElement.removeAttribute('data-date');
                birthDateElement.textContent = (window.translations && window.translations.gender_unknown) ? window.translations.gender_unknown : 'Не указана';
            }
        }
        
        // Обновляем грейд с эффектами
        const gradeElement = document.getElementById('profile-grade');
        if (gradeElement) {
            if (userData.grade) {
                gradeElement.setAttribute('data-grade', userData.grade);
                const gradeLabels = {
                    'junior': (window.translations && window.translations) ? window.translations.grade_junior || 'Junior' : 'Junior',
                    'middle': (window.translations && window.translations) ? window.translations.grade_middle || 'Middle' : 'Middle', 
                    'senior': (window.translations && window.translations) ? window.translations.grade_senior || 'Senior' : 'Senior'
                };
                const gradeText = gradeLabels[userData.grade] || userData.grade;
                
                // Добавляем классы для эффектов в зависимости от грейда
                gradeElement.className = `info-value grade-${userData.grade}`;
                gradeElement.textContent = gradeText;
                
                console.log(`🎯 Грейд установлен: ${gradeText} (${userData.grade})`);
            } else {
                gradeElement.removeAttribute('data-grade');
                gradeElement.className = 'info-value grade-none';
                gradeElement.textContent = (window.translations && window.translations) ? window.translations.not_specified || 'Не указан' : 'Не указан';
            }
        }
        
        // Обновляем технологии
        const technologiesElement = document.getElementById('profile-technologies');
        if (technologiesElement) {
            if (userData.programming_languages && userData.programming_languages.length > 0) {
                technologiesElement.removeAttribute('data-empty');
                technologiesElement.innerHTML = '';
                userData.programming_languages.forEach(tech => {
                    const techTag = document.createElement('span');
                    techTag.className = 'technology-tag';
                    techTag.textContent = tech;
                    technologiesElement.appendChild(techTag);
                });
            } else {
                technologiesElement.setAttribute('data-empty', 'true');
                technologiesElement.innerHTML = `<span class="no-data">${(window.translations && window.translations) ? window.translations.no_technologies || 'Технологии не указаны' : 'Технологии не указаны'}</span>`;
            }
        }
        
        // Обновляем переводы после загрузки данных
        setTimeout(() => {
            updateProfessionalInfoTranslations();
        }, 100);
    }

    async function loadTechnologies(selectedTechnologies = []) {
        console.log('🔧 loadTechnologies вызван с выбранными технологиями:', selectedTechnologies);
        
        const container = document.getElementById('technologies-container');
        if (!container) {
            console.error('❌ Контейнер технологий не найден');
            return;
        }
        
        container.innerHTML = '<div class="technologies-loading">Загрузка технологий...</div>';
        
        try {
                // Загружаем список технологий из API
                const response = await fetch('/api/accounts/programming-languages/');
            if (!response.ok) {
                throw new Error('Не удалось загрузить технологии');
            }
            
            const technologies = await response.json();
            console.log('📋 Загружены технологии:', technologies);
            
            // Создаем выпадающий список для выбора технологий
            container.innerHTML = `
                <select id="technologies-select" name="programming_language_ids" multiple>
                    ${technologies.map(tech => {
                        const isSelected = selectedTechnologies.some(selected => 
                            selected === tech.name || selected.id === tech.id
                        );
                        return `<option value="${tech.id}" ${isSelected ? 'selected' : ''}>${tech.name}</option>`;
                    }).join('')}
                </select>
            `;
            
        } catch (error) {
            console.error('❌ Ошибка загрузки технологий:', error);
            container.innerHTML = '<div class="technologies-error">Ошибка загрузки технологий</div>';
        }
    }

    async function loadTechnologiesWithNames(selectedTechnologyNames = []) {
        console.log('🔧 loadTechnologiesWithNames вызван с именами технологий:', selectedTechnologyNames);
        
        const container = document.getElementById('technologies-container');
        console.log('🔍 Контейнер технологий:', container);
        if (!container) {
            console.error('❌ Контейнер технологий не найден');
            return;
        }
        
            container.innerHTML = '<div class="technologies-loading">Загрузка технологий...</div>';
            console.log('⏳ Начата загрузка технологий...');
            
            // Добавляем тестовый select для проверки
            setTimeout(() => {
                if (container.innerHTML.includes('Загрузка технологий...')) {
                    console.log('⚠️ Тест: добавляем простой select для проверки');
                    container.innerHTML = `
                        <select id="test-select" multiple>
                            <option value="1">Test Option 1</option>
                            <option value="2">Test Option 2</option>
                        </select>
                    `;
                }
            }, 3000);
        
        try {
            // Загружаем список технологий из API
            console.log('🌐 Отправляем запрос на /api/accounts/programming-languages/');
            const response = await fetch('/api/accounts/programming-languages/');
            console.log('📡 Получен ответ:', response.status, response.statusText);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const technologies = await response.json();
            console.log('📋 Загружены технологии:', technologies);
            console.log('📊 Количество технологий:', technologies.length);
            
                // Создаем выпадающий список с чекбоксами для выбора технологий
                const selectHTML = `
                    <div class="technologies-dropdown" style="position: relative; width: 100%;">
                        <button type="button" id="technologies-toggle" class="technologies-toggle" style="
                            width: 100%; 
                            padding: 12px 16px; 
                            border: 2px solid #e1e5e9; 
                            border-radius: 8px; 
                            background: #ffffff; 
                            cursor: pointer;
                            text-align: left;
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            font-size: 14px;
                            color: #2c3e50;
                            transition: all 0.2s ease;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        " onmouseover="this.style.borderColor='#3498db'" onmouseout="this.style.borderColor='#e1e5e9'">
                            <span id="technologies-selected-text">Выберите технологии (необязательно)</span>
                            <span style="font-size: 12px; color: #7f8c8d;">▼</span>
                        </button>
                        <div id="technologies-dropdown-content" class="technologies-dropdown-content" style="
                            display: none;
                            position: absolute;
                            top: 100%;
                            left: 0;
                            right: 0;
                            background: white;
                            border: 2px solid #e1e5e9;
                            border-top: none;
                            border-radius: 0 0 8px 8px;
                            max-height: 200px;
                            overflow-y: auto;
                            z-index: 1000;
                            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
                        ">
                        ${technologies.map(tech => {
                            const isSelected = selectedTechnologyNames.includes(tech.name);
                            console.log(`🔍 Технология: ${tech.name}, ID: ${tech.id}, Выбрана: ${isSelected}`);
                                return `
                                    <label style="
                                        display: flex; 
                                        align-items: center;
                                        justify-content: space-between;
                                        padding: 12px 16px; 
                                        cursor: pointer; 
                                        border-bottom: 1px solid #f8f9fa;
                                        margin: 0;
                                        font-size: 14px;
                                        color: #2c3e50;
                                        transition: background-color 0.2s ease;
                                    " onmouseover="this.style.backgroundColor='#f8f9fa'" onmouseout="this.style.backgroundColor='white'">
                                        <span>${tech.name}</span>
                                        <input type="checkbox" 
                                               value="${tech.id}" 
                                               ${isSelected ? 'checked' : ''} 
                                               style="
                                                   margin: 0;
                                                   width: 16px;
                                                   height: 16px;
                                                   accent-color: #3498db;
                                               ">
                                    </label>
                                `;
                        }).join('')}
                        </div>
                    </div>
                    <div class="technologies-help" style="margin-top: 8px; font-size: 12px; color: #7f8c8d;">
                        💡 <span data-translate="technologies_help">Нажмите на список, чтобы выбрать несколько технологий. Поле можно оставить пустым.</span>
                    </div>
                    <div class="technologies-actions" style="margin-top: 8px; display: flex; gap: 8px;">
                        <button type="button" id="clear-technologies" style="
                            padding: 6px 12px;
                            background: #e74c3c;
                            color: white;
                            border: none;
                            border-radius: 4px;
                            cursor: pointer;
                            font-size: 12px;
                        " onmouseover="this.style.backgroundColor='#c0392b'" onmouseout="this.style.backgroundColor='#e74c3c'">
                            🗑️ <span data-translate="clear_all">Очистить все</span>
                        </button>
                        <button type="button" id="select-all-technologies" style="
                            padding: 6px 12px;
                            background: #3498db;
                            color: white;
                            border: none;
                            border-radius: 4px;
                            cursor: pointer;
                            font-size: 12px;
                        " onmouseover="this.style.backgroundColor='#2980b9'" onmouseout="this.style.backgroundColor='#3498db'">
                            ✅ <span data-translate="select_all">Выбрать все</span>
                        </button>
                    </div>
                    <input type="hidden" id="technologies-clear-flag" name="technologies_clear" value="false">
                `;
            
            console.log('🎨 HTML для select:', selectHTML);
            container.innerHTML = selectHTML;
            
            console.log('✅ Выпадающий список технологий создан');
            
            // Добавляем обработчики для выпадающего списка
            setupTechnologiesDropdown();
            
        } catch (error) {
            console.error('❌ Ошибка загрузки технологий:', error);
            container.innerHTML = '<div class="technologies-error">Ошибка загрузки технологий: ' + error.message + '</div>';
        }
    }

    function setupTechnologiesDropdown() {
        console.log('🔧 Настройка выпадающего списка технологий');
        
        const toggle = document.getElementById('technologies-toggle');
        const content = document.getElementById('technologies-dropdown-content');
        const selectedText = document.getElementById('technologies-selected-text');
        
        if (!toggle || !content || !selectedText) {
            console.error('❌ Элементы выпадающего списка не найдены');
            return;
        }
        
        // Обработчик клика по кнопке
        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = content.style.display !== 'none';
            content.style.display = isOpen ? 'none' : 'block';
            console.log('🔄 Выпадающий список:', isOpen ? 'закрыт' : 'открыт');
        });
        
        // Обработчик клика по чекбоксам
        content.addEventListener('change', (e) => {
            if (e.target.type === 'checkbox') {
                updateSelectedTechnologiesText();
                console.log('✅ Обновлен текст выбранных технологий');
            }
        });
        
        // Закрытие при клике вне списка
        document.addEventListener('click', (e) => {
            if (!toggle.contains(e.target) && !content.contains(e.target)) {
                content.style.display = 'none';
            }
        });
        
        // Обновляем текст при инициализации
        updateSelectedTechnologiesText();
        
        // Добавляем обработчики для кнопок
        const clearButton = document.getElementById('clear-technologies');
        const selectAllButton = document.getElementById('select-all-technologies');
        
        if (clearButton) {
            clearButton.addEventListener('click', () => {
                const checkboxes = content.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(cb => cb.checked = false);
                // Устанавливаем флаг для отправки пустого массива
                const clearFlag = document.getElementById('technologies-clear-flag');
                if (clearFlag) {
                    clearFlag.value = 'true';
                }
                updateSelectedTechnologiesText();
                console.log('🗑️ Все технологии очищены, установлен флаг очистки');
            });
        }
        
        if (selectAllButton) {
            selectAllButton.addEventListener('click', () => {
                const checkboxes = content.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(cb => cb.checked = true);
                updateSelectedTechnologiesText();
                console.log('✅ Все технологии выбраны');
            });
        }
        
        function updateSelectedTechnologiesText() {
            const checkboxes = content.querySelectorAll('input[type="checkbox"]');
            const selected = Array.from(checkboxes).filter(cb => cb.checked);
            
            if (selected.length === 0) {
                selectedText.textContent = window.translations.select_technologies_optional || 'Выберите технологии (необязательно)';
            } else if (selected.length === 1) {
                selectedText.textContent = selected[0].parentElement.querySelector('span').textContent;
            } else {
                const selectedTextLabel = window.translations.selected_technologies || 'Выбрано:';
                selectedText.textContent = `${selectedTextLabel} ${selected.length} ${window.translations.technologies || 'технологий'}`;
            }
            
            console.log('📋 Выбрано технологий:', selected.length);
        }
    }

    function updateSocialLinks(socialLinks, elements) {
        console.log('🔗 updateSocialLinks вызван с данными:', socialLinks);
        
        if (!elements.socials) {
            console.error('❌ Контейнер социальных ссылок не найден');
            return;
        }

        // Очищаем контейнер
        elements.socials.innerHTML = '';

        if (!socialLinks || socialLinks.length === 0) {
            elements.socials.innerHTML = '<p class="social-empty">Социальные сети не указаны.</p>';
            return;
        }

        // Создаем HTML для каждой социальной ссылки в правильном формате
        socialLinks.forEach(link => {
            const linkElement = document.createElement('a');
            linkElement.href = link.url;
            linkElement.target = '_blank';
            linkElement.rel = 'noopener noreferrer';
            linkElement.className = 'social-link-card';
            
            // Определяем правильную Font Awesome иконку для каждой социальной сети
            let iconClass = 'fas fa-link'; // По умолчанию
            
            switch (link.name) {
                case 'Веб-сайт':
                    iconClass = 'fas fa-globe';
                    break;
                case 'Telegram':
                    iconClass = 'fab fa-telegram';
                    break;
                case 'GitHub':
                    iconClass = 'fab fa-github';
                    break;
                case 'LinkedIn':
                    iconClass = 'fab fa-linkedin';
                    break;
                case 'Instagram':
                    iconClass = 'fab fa-instagram';
                    break;
                case 'Facebook':
                    iconClass = 'fab fa-facebook';
                    break;
                case 'YouTube':
                    iconClass = 'fab fa-youtube';
                    break;
                default:
                    iconClass = 'fas fa-link';
            }
            
            // Создаем правильную структуру HTML с Font Awesome иконками
            linkElement.innerHTML = `
                <div class="social-icon"><i class="${iconClass}"></i></div>
                <div class="social-info">
                    <div class="social-name">${link.name}</div>
                    <div class="social-url">${link.url.replace(/^(https?:\/\/)?(www\.)?/, '')}</div>
                </div>
            `;
            
            elements.socials.appendChild(linkElement);
        });
        
        console.log(`✅ Добавлено ${socialLinks.length} социальных ссылок`);
    }


    // Функция для AJAX обновления профиля после сохранения
    async function updateProfileAfterSave(userData) {
        console.log('🔄 updateProfileAfterSave вызван с данными:', userData);
        console.log('🔍 programming_languages в данных:', userData.programming_languages);
        console.log('🔍 Тип programming_languages:', typeof userData.programming_languages);
        console.log('🔍 Длина programming_languages:', userData.programming_languages ? userData.programming_languages.length : 'undefined');
        const elements = getDOMElements();
        
        try {
            // 1. Обновляем имя и username
            if (userData.first_name || userData.last_name || userData.username) {
                const fullName = userData.full_name || `${userData.first_name || ''} ${userData.last_name || ''}`.trim();
                if (elements.name) {
                    elements.name.textContent = fullName || 'Пользователь';
                    console.log('✅ Имя обновлено:', fullName);
                }
                if (elements.username) {
                    elements.username.textContent = userData.username ? `@${userData.username}` : 'скрыт';
                    console.log('✅ Username обновлен:', userData.username);
                }
            }
            
            // 2. Обновляем аватар
            if (userData.avatar) {
                const avatarUrl = userData.avatar + '?t=' + Date.now();
                if (elements.avatar) {
                    elements.avatar.src = avatarUrl;
                    elements.avatar.onload = () => console.log('✅ Аватар обновлен:', avatarUrl);
                    elements.avatar.onerror = () => console.log('❌ Ошибка загрузки аватара');
                }
            }
            
            // 3. Обновляем профессиональную информацию
            if (userData.gender || userData.birth_date || userData.grade) {
                updateProfessionalInfo(userData);
                console.log('✅ Профессиональная информация обновлена');
            }
            
            // 4. Обновляем социальные ссылки
            if (userData.social_links) {
                updateSocialLinks(userData.social_links, elements);
                console.log('✅ Социальные ссылки обновлены');
            }
            
            // 5. Обновляем технологии в профиле
            const technologiesElement = document.getElementById('profile-technologies');
            console.log('🔍 Элемент технологий найден:', technologiesElement);
            console.log('🔍 Данные технологий для обновления:', userData.programming_languages);
            
            if (technologiesElement) {
                if (userData.programming_languages && userData.programming_languages.length > 0) {
                    console.log('🔧 Обновляем технологии в профиле, количество:', userData.programming_languages.length);
                    technologiesElement.removeAttribute('data-empty');
                    technologiesElement.innerHTML = '';
                    userData.programming_languages.forEach((tech, index) => {
                        console.log(`🔧 Создаем тег для технологии ${index}:`, tech);
                        const techTag = document.createElement('span');
                        techTag.className = 'technology-tag';
                        // Проверяем, является ли tech объектом с полем name или строкой
                        techTag.textContent = typeof tech === 'object' && tech.name ? tech.name : tech;
                        technologiesElement.appendChild(techTag);
                        console.log(`✅ Тег технологии ${index} добавлен:`, techTag.textContent);
                    });
                    console.log('✅ Технологии в профиле обновлены:', userData.programming_languages.length);
                } else {
                    console.log('🔧 Нет технологий, очищаем профиль');
                    technologiesElement.innerHTML = '<span class="no-data" data-translate="no_technologies">Технологии не указаны</span>';
                    console.log('✅ Технологии очищены в профиле');
                }
            } else {
                console.log('❌ Элемент технологий не найден!');
            }
            
            // 6. Обновляем технологии в модальном окне
            if (userData.programming_languages && userData.programming_languages.length > 0) {
                console.log('🔧 Обновляем технологии в модальном окне:', userData.programming_languages);
                loadTechnologiesWithNames(userData.programming_languages);
            } else {
                console.log('🔧 Нет технологий, очищаем модальное окно');
                loadTechnologiesWithNames([]);
            }
            
            // 7. Обновляем поля формы
            if (elements.firstNameInput) {
                elements.firstNameInput.value = userData.first_name || '';
            }
            if (elements.lastNameInput) {
                elements.lastNameInput.value = userData.last_name || '';
            }
            
            // 8. Обновляем window.currentUser с новыми данными
            if (window.currentUser) {
                window.currentUser.programming_languages = userData.programming_languages || [];
                window.currentUser.first_name = userData.first_name || '';
                window.currentUser.last_name = userData.last_name || '';
                window.currentUser.full_name = userData.full_name || '';
                window.currentUser.username = userData.username || '';
                window.currentUser.avatar = userData.avatar || '';
                console.log('✅ window.currentUser обновлен с новыми данными');
            }
            
            console.log('✅ AJAX обновление профиля завершено');
            
        } catch (error) {
            console.error('❌ Ошибка при AJAX обновлении профиля:', error);
        }
    }

    function updateProfileDOM(userData) {
        console.log('🚀 updateProfileDOM вызван с данными:', userData);
        const elements = getDOMElements();
        
        if (!userData || !elements.profileContainer) {
            console.error('❌ Ошибка: нет данных или контейнера профиля');
            showError("Не удалось загрузить данные профиля.");
            return;
        }
        
        // Сохраняем Telegram ID в глобальной переменной для использования в формах
        if (userData.telegram_id) {
            window.telegramUserId = userData.telegram_id;
            console.log('💾 Telegram ID сохранен при загрузке:', userData.telegram_id);
        }
        
        console.log('🔍 Обновляем имя пользователя:', {
            first_name: userData.first_name,
            last_name: userData.last_name,
            username: userData.username,
            full_name: userData.full_name
        });
        
        // Если данные пользователя неполные, используем сохраненные данные
        if (!userData.first_name && !userData.last_name && !userData.username && !userData.full_name) {
            console.log('⚠️ Данные пользователя неполные, используем сохраненные данные');
            const savedUser = window.currentUser;
            if (savedUser && (savedUser.first_name || savedUser.last_name || savedUser.username || savedUser.full_name)) {
                userData.first_name = savedUser.first_name;
                userData.last_name = savedUser.last_name;
                userData.username = savedUser.username;
                userData.full_name = savedUser.full_name;
                console.log('✅ Восстановлены данные пользователя:', {
                    first_name: userData.first_name,
                    last_name: userData.last_name,
                    username: userData.username,
                    full_name: userData.full_name
                });
            }
        }
        
        // Обновляем глобальный объект currentUser с актуальными данными из БД
        window.currentUser = userData;
        console.log('💾 window.currentUser обновлен с актуальными данными:', userData);
        
        // Используем full_name если есть, иначе собираем из first_name и last_name
        const fullName = userData.full_name || `${userData.first_name || ''} ${userData.last_name || ''}`.trim();
        elements.name.textContent = fullName || 'Пользователь';
        elements.username.textContent = userData.username ? `@${userData.username}` : 'скрыт';
        
        console.log('✅ Имя пользователя обновлено:', {
            nameElement: elements.name.textContent,
            usernameElement: elements.username.textContent
        });
        
        updateAvatar(userData.avatar);
        updateProfessionalInfo(userData);
        updateSocialLinks(userData.social_links, elements);
        
        // Обновляем технологии если они есть в данных
        if (userData.programming_languages && userData.programming_languages.length > 0) {
            console.log('🔧 Обновляем технологии:', userData.programming_languages);
            loadTechnologiesWithNames(userData.programming_languages);
        } else {
            console.log('🔧 Нет технологий в данных, очищаем отображение');
            // Очищаем отображение технологий если их нет
            const technologiesContainer = document.getElementById('profile-technologies');
            if (technologiesContainer) {
                technologiesContainer.innerHTML = '<span class="no-data" data-translate="no_technologies">Технологии не указаны</span>';
            }
        }

        // Заполняем поля модального окна при загрузке профиля
        if (elements.firstNameInput) {
            elements.firstNameInput.value = userData.first_name || '';
            console.log('👤 Заполняем поле имени:', userData.first_name);
            console.log('🔍 Поле имени найдено:', elements.firstNameInput);
        } else {
            console.log('❌ Поле имени НЕ найдено!');
        }
        
        if (elements.lastNameInput) {
            elements.lastNameInput.value = userData.last_name || '';
            console.log('👤 Заполняем поле фамилии:', userData.last_name);
            console.log('🔍 Поле фамилии найдено:', elements.lastNameInput);
        } else {
            console.log('❌ Поле фамилии НЕ найдено!');
        }
        
        const socialLinks = userData.social_links || [];
        elements.websiteInput.value = socialLinks.find(link => link.name === 'Веб-сайт')?.url || '';
        elements.telegramInput.value = socialLinks.find(link => link.name === 'Telegram')?.url.replace('https://t.me/', '') || '';
        elements.githubInput.value = socialLinks.find(link => link.name === 'GitHub')?.url || '';
        elements.linkedinInput.value = socialLinks.find(link => link.name === 'LinkedIn')?.url || '';
        elements.instagramInput.value = socialLinks.find(link => link.name === 'Instagram')?.url || '';
        elements.facebookInput.value = socialLinks.find(link => link.name === 'Facebook')?.url || '';
        elements.youtubeInput.value = socialLinks.find(link => link.name === 'YouTube')?.url || '';

        hideLoader();
        
        // Принудительно показываем контейнер профиля
        elements.profileContainer.style.display = 'block';
        elements.profileContainer.style.visibility = 'visible';
        elements.profileContainer.style.opacity = '1';
        elements.profileContainer.removeAttribute('hidden');
        elements.profileContainer.classList.remove('hidden');
        
        console.log('✅ Профиль успешно обновлен и показан');
        console.log('🔍 Состояние контейнера в updateProfileDOM:', {
            display: elements.profileContainer.style.display,
            visibility: elements.profileContainer.style.visibility,
            opacity: elements.profileContainer.style.opacity,
            computedDisplay: window.getComputedStyle(elements.profileContainer).display,
            innerHTML: elements.profileContainer.innerHTML.length
        });
        
        // Принудительно обновляем содержимое профиля
        if (elements.profileContainer.innerHTML.length < 100) {
            console.log('⚠️ ПРОБЛЕМА: Контейнер профиля пустой! Принудительно перезагружаем профиль...');
            // Перезагружаем профиль с сервера
            setTimeout(() => {
                fetchProfileDataFromServer();
            }, 100);
        }
        
        // Дополнительная проверка через небольшую задержку
        setTimeout(() => {
            const elementsAfter = getDOMElements();
            if (elementsAfter.profileContainer) {
                const computedStyle = window.getComputedStyle(elementsAfter.profileContainer);
                console.log('🔍 Проверка видимости через 50ms:', {
                    styleDisplay: elementsAfter.profileContainer.style.display,
                    computedDisplay: computedStyle.display,
                    visibility: computedStyle.visibility,
                    opacity: computedStyle.opacity
                });
                
                if (computedStyle.display === 'none' || elementsAfter.profileContainer.style.display === 'none') {
                    elementsAfter.profileContainer.style.display = 'block';
                    elementsAfter.profileContainer.style.visibility = 'visible';
                    elementsAfter.profileContainer.style.opacity = '1';
                    elementsAfter.profileContainer.removeAttribute('hidden');
                    elementsAfter.profileContainer.classList.remove('hidden');
                    console.log('🔧 Исправление видимости профиля в updateProfileDOM');
                }
            }
        }, 50);
    }

    // --- Управление состоянием загрузки ---

    function showLoader() {
        console.log('🔄 showLoader вызван');
        const elements = getDOMElements();
        if (elements.loader) elements.loader.style.display = 'flex';
        if (elements.profileContainer) elements.profileContainer.style.display = 'none';
    }

    function hideLoader() {
        console.log('🔄 hideLoader вызван');
        const elements = getDOMElements();
        if (elements.loader) elements.loader.style.display = 'none';
    }

    function showError(message) {
        const elements = getDOMElements();
        hideLoader();
        if (elements.loader) {
            elements.loader.style.display = 'flex';
            elements.loader.innerHTML = `<p class="error-message">${message}</p>`;
        }
    }

    // --- Логика получения данных ---

    async function fetchProfileDataFromServer() {
        console.log('🔍 fetchProfileDataFromServer вызван');
        
        if (isLoading) {
            console.log('⏸️ Загрузка уже идет, пропускаем');
            return;
        }
        
        isLoading = true;
        showLoader();

        try {
            console.log('🔍 Начинаем загрузку профиля');
            
            const tg = getTelegramWebApp();
            console.log('🔍 Telegram WebApp:', tg);
            console.log('🔍 initData:', tg?.initData ? 'present' : 'missing');
            
            // Проверяем, есть ли telegram_id в URL (для просмотра чужого профиля)
            const urlTelegramId = getTelegramIdFromURL();
            
            if (urlTelegramId) {
                console.log('🔍 Загружаем профиль пользователя по telegram_id из URL:', urlTelegramId);
                
                try {
                    const profileResponse = await fetch(`/api/accounts/miniapp-users/by-telegram/${urlTelegramId}/`);
                    if (profileResponse.ok) {
                        const profileData = await profileResponse.json();
                        console.log('✅ Получены данные профиля через API:', profileData);
                        console.log('🔍 gender в API данных:', profileData.gender);
                        console.log('🔍 birth_date в API данных:', profileData.birth_date);
                        updateProfileDOM(profileData);
                        return;
                    } else {
                        console.error('❌ Ошибка загрузки профиля:', profileResponse.status);
                        showNotification('profile_load_error', 'error', null, getTranslation('profile_load_error', 'Ошибка загрузки профиля'));
                        return;
                    }
                } catch (error) {
                    console.error('❌ Ошибка при загрузке профиля:', error);
                    showNotification('profile_load_error', 'error', null, getTranslation('profile_load_error', 'Ошибка загрузки профиля'));
                    return;
                }
            }
            
            if (!tg || !tg.initData) {
                console.log('⚠️ Нет initData, пытаемся получить данные профиля через API');
                
                // Пытаемся получить данные профиля через API
                try {
                    const profileResponse = await fetch('/api/accounts/miniapp-users/by-telegram/7827592658/');
                    if (profileResponse.ok) {
                        const profileData = await profileResponse.json();
                        console.log('✅ Получены данные профиля через API:', profileData);
                        console.log('🔍 gender в API данных:', profileData.gender);
                        console.log('🔍 birth_date в API данных:', profileData.birth_date);
                        updateProfileDOM(profileData);
                        return;
                    }
                } catch (apiError) {
                    console.error('❌ Ошибка получения данных через API:', apiError);
                }
                
                // Fallback к заглушке
                console.log('⚠️ Fallback к заглушке');
                const mockData = {
                    first_name: 'Тестовый',
                    last_name: 'Пользователь',
                    username: 'test_user',
                    avatar: null,
                    points: 0,
                    rating: 0,
                    quizzes_completed: 0,
                    success_rate: 0,
                    social_links: [],
                    progress: [],
                    gender: 'male',  // Добавляем поле пола для тестирования
                    birth_date: '1990-01-01'  // Добавляем дату рождения для тестирования
                };
                updateProfileDOM(mockData);
                return;
            }

            // Основной рабочий процесс с initData
            console.log('📡 Отправляем запрос к /api/verify-init-data');
            const response = await fetch('/api/verify-init-data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ initData: tg.initData })
            });

            console.log('📡 Получен ответ:', response.status, response.statusText);

            if (!response.ok) {
                const errorBody = await response.text();
                console.error('❌ Ошибка ответа:', response.status, errorBody);
                throw new Error(`Ошибка ${response.status}: ${errorBody}`);
            }

            const data = await response.json();
            console.log('✅ Получены данные профиля:', data);
            console.log('🔍 gender в данных:', data.gender);
            console.log('🔍 birth_date в данных:', data.birth_date);
            
            updateProfileDOM(data);

        } catch (error) {
            console.error('❌ Ошибка при загрузке профиля:', error);
            showError(`Не удалось загрузить профиль. ${error.message}`);
        } finally {
            isLoading = false;
        }
    }

    // --- Глобальная функция инициализации ---
    window.initProfilePage = function() {
        console.log('🚀 initProfilePage вызван');
        
        const tg = getTelegramWebApp();
        if (tg) {
            tg.ready();
            tg.expand();
        }
        
        fetchProfileDataFromServer();

        // Инициализация обработчиков модального окна
        const elements = getDOMElements();
        if (elements.editProfileBtn) {
            elements.editProfileBtn.onclick = () => {
                elements.editModal.style.display = 'block';
                
                // Улучшенное позиционирование для мобильных устройств
                const modalContent = elements.editModal.querySelector('.modal-content');
                if (modalContent) {
                    // Сбрасываем любые предыдущие стили позиционирования
                    modalContent.style.position = '';
                    modalContent.style.top = '';
                    modalContent.style.left = '';
                    modalContent.style.transform = '';
                    
                    // Для мобильных устройств добавляем специальное позиционирование
                    if (window.innerWidth <= 768) {
                        // Прокручиваем к началу страницы для лучшего отображения
                        window.scrollTo(0, 0);
                        
                        // Добавляем небольшую задержку для корректного отображения
                        setTimeout(() => {
                            modalContent.style.position = 'relative';
                            modalContent.style.top = '10px';
                        }, 50);
                    }
                }
                
                // Заполняем поля формы текущими данными профиля
                const currentUser = window.currentUser; // Глобальная переменная из base.html
                console.log('🔍 Текущий пользователь для заполнения формы:', currentUser);
                
                // Проверяем, авторизован ли пользователь (есть ли реальные данные)
                if (!currentUser || !currentUser.id || currentUser.first_name === 'Тестовый') {
                    console.warn('⚠️ Пользователь не авторизован, показываем заглушку');
                    // Не заполняем поля, если пользователь не авторизован
                    return;
                }
                
                if (currentUser) {
                    const fullName = `${currentUser.first_name || ''} ${currentUser.last_name || ''}`.trim();
                    // elements.name.textContent = fullName || 'Пользователь'; // Это не input, а h1
                    // elements.username.textContent = currentUser.username ? `@${currentUser.username}` : translations.get('hidden', 'скрыт');
                    // Основные поля (имя, фамилия, username) не редактируются в этой форме
                    console.log('📝 Основные данные пользователя (не редактируются):', {
                        firstName: currentUser.first_name,
                        lastName: currentUser.last_name,
                        username: currentUser.username
                    });
                    
                    // Заполняем новые поля
                    const gradeInput = document.getElementById('grade-input');
                    if (gradeInput) {
                        gradeInput.value = currentUser.grade || '';
                        console.log('📝 Заполнен грейд:', currentUser.grade);
                    }
                    
                    const genderInput = document.getElementById('gender-input');
                    if (genderInput) {
                        genderInput.value = currentUser.gender || '';
                        console.log('📝 Заполнен пол:', currentUser.gender);
                    }
                    
                    const birthDateInput = document.getElementById('birth-date-input');
                    if (birthDateInput) {
                        birthDateInput.value = currentUser.birth_date || '';
                        console.log('📝 Заполнена дата рождения:', currentUser.birth_date);
                    }
                    
                    // Загружаем и заполняем технологии (передаем все выбранные)
                    if (currentUser.programming_languages && currentUser.programming_languages.length > 0) {
                        console.log('📝 Загружаем технологии, все выбранные:', currentUser.programming_languages);
                        loadTechnologiesWithNames(currentUser.programming_languages);
                    } else {
                        console.log('📝 Нет выбранных технологий, загружаем пустой список');
                        loadTechnologiesWithNames([]);
                    }
                    
                    // Заполняем поля имени и фамилии
                    if (elements.firstNameInput) {
                        elements.firstNameInput.value = currentUser.first_name || '';
                        console.log('👤 Заполняем поле имени в reinitializeProfilePage:', currentUser.first_name);
                        console.log('🔍 Поле имени найдено в reinitializeProfilePage:', elements.firstNameInput);
                    } else {
                        console.log('❌ Поле имени НЕ найдено в reinitializeProfilePage!');
                    }
                    
                    if (elements.lastNameInput) {
                        elements.lastNameInput.value = currentUser.last_name || '';
                        console.log('👤 Заполняем поле фамилии в reinitializeProfilePage:', currentUser.last_name);
                        console.log('🔍 Поле фамилии найдено в reinitializeProfilePage:', elements.lastNameInput);
                    } else {
                        console.log('❌ Поле фамилии НЕ найдено в reinitializeProfilePage!');
                    }
                    
                    // Также заполняем поля социальных сетей
                    const currentSocialLinks = currentUser.social_links || [];
                    elements.websiteInput.value = currentSocialLinks.find(link => link.name === 'Веб-сайт')?.url || '';
                    elements.telegramInput.value = currentSocialLinks.find(link => link.name === 'Telegram')?.url.replace('https://t.me/', '') || '';
                    elements.githubInput.value = currentSocialLinks.find(link => link.name === 'GitHub')?.url || '';
                    elements.linkedinInput.value = currentSocialLinks.find(link => link.name === 'LinkedIn')?.url || '';
                    elements.instagramInput.value = currentSocialLinks.find(link => link.name === 'Instagram')?.url || '';
                    elements.facebookInput.value = currentSocialLinks.find(link => link.name === 'Facebook')?.url || '';
                    elements.youtubeInput.value = currentSocialLinks.find(link => link.name === 'YouTube')?.url || '';
                    
                    // Предварительный просмотр текущего аватара
                    if (currentUser.avatar) {
                        elements.avatarPreview.innerHTML = `<img src="${currentUser.avatar}" alt="Current Avatar" style="max-width: 100px; max-height: 100px; border-radius: 50%; object-fit: cover;">`;
                    } else {
                        elements.avatarPreview.innerHTML = '';
                    }
                }
            };
        }

        if (elements.closeModalBtn) {
            elements.closeModalBtn.onclick = () => {
                elements.editModal.style.display = 'none';
            };
        }

        if (elements.cancelEditBtn) {
            elements.cancelEditBtn.onclick = () => {
                elements.editModal.style.display = 'none';
            };
        }

        // Обработчик кнопки "Обновить данные"
        if (elements.refreshBtn) {
            elements.refreshBtn.onclick = async () => {
                console.log('🔄 Кнопка "Обновить данные" нажата');
                // Используем глобальную функцию showNotification из base.html для автоматического исчезновения
                if (window.showNotification) {
                    window.showNotification('refreshing_data', 'info');
                } else {
                    showNotification('refreshing_data', 'info', null, 'Refreshing data...');
                }
                
                // Обновляем статус онлайн
                const telegramId = window.currentUser?.telegram_id;
                if (telegramId) {
                    try {
                        console.log('🟢 Обновление статуса онлайн для telegram_id:', telegramId);
                        const response = await fetch('/api/accounts/miniapp-users/update-last-seen/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ telegram_id: telegramId })
                        });
                        
                        if (response.ok) {
                            console.log('✅ Статус онлайн обновлен успешно');
                        } else {
                            console.warn('⚠️ Не удалось обновить статус онлайн:', response.status);
                        }
                    } catch (error) {
                        console.error('❌ Ошибка при обновлении статуса онлайн:', error);
                    }
                } else {
                    console.warn('⚠️ Не найден telegram_id для обновления статуса онлайн');
                }
                
                fetchProfileDataFromServer();
            };
        }

        // Обработка предварительного просмотра аватара
        if (elements.avatarInput) {
            elements.avatarInput.onchange = (event) => {
                const file = event.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        elements.avatarPreview.innerHTML = `<img src="${e.target.result}" alt="Avatar Preview" style="max-width: 100px; max-height: 100px; border-radius: 50%; object-fit: cover;">`;
                    };
                    reader.readAsDataURL(file);
                } else {
                    elements.avatarPreview.innerHTML = '';
                }
            };
        }

        // Обработка отправки формы редактирования
        if (elements.editProfileForm) {
            elements.editProfileForm.onsubmit = async (event) => {
                event.preventDefault();
                console.log('🚀 Форма отправлена!');
                
                        // Получаем Telegram ID из данных пользователя
        let telegramId = window.currentUser?.telegram_id;
        
        console.log('🔍 Telegram ID из currentUser:', telegramId);
        
        if (!telegramId) {
            showNotification('error_telegram_id_missing', 'error', null, getTranslation('error_telegram_id_missing', 'Не удалось получить данные пользователя. Попробуйте обновить страницу.'));
            return;
        }

                const formData = new FormData();
                // Добавляем файл аватара, если он выбран
                if (elements.avatarInput.files && elements.avatarInput.files[0]) {
                    console.log('📁 Добавляем файл аватара:', elements.avatarInput.files[0].name);
                    formData.append('avatar', elements.avatarInput.files[0]);
                } else {
                    console.log('📁 Файл аватара не выбран');
                }
                
                // Добавляем поля имени и фамилии
                if (elements.firstNameInput) {
                    formData.append('first_name', elements.firstNameInput.value);
                    console.log('👤 Добавляем имя:', elements.firstNameInput.value);
                }
                
                if (elements.lastNameInput) {
                    formData.append('last_name', elements.lastNameInput.value);
                    console.log('👤 Добавляем фамилию:', elements.lastNameInput.value);
                }
                
                // Добавляем новые поля
                const gradeInput = document.getElementById('grade-input');
                if (gradeInput) {
                    formData.append('grade', gradeInput.value);
                }
                
                const genderInput = document.getElementById('gender-input');
                if (genderInput) {
                    formData.append('gender', genderInput.value);
                }
                
                const birthDateInput = document.getElementById('birth-date-input');
                if (birthDateInput) {
                    formData.append('birth_date', birthDateInput.value);
                }
                
            // Собираем выбранные технологии из чекбоксов
            const technologiesContent = document.getElementById('technologies-dropdown-content');
            const clearFlag = document.getElementById('technologies-clear-flag');
            const shouldClear = clearFlag && clearFlag.value === 'true';
            
            if (technologiesContent) {
                const checkboxes = technologiesContent.querySelectorAll('input[type="checkbox"]');
                const selectedCheckboxes = Array.from(checkboxes).filter(cb => cb.checked);
                console.log('📋 Выбранные технологии:', selectedCheckboxes.map(cb => ({ id: cb.value, name: cb.parentElement.textContent.trim() })));
                console.log('📋 Флаг очистки:', shouldClear);
                
                if (shouldClear) {
                    // Отправляем пустой массив для удаления всех технологий
                    formData.append('programming_language_ids', '');
                    console.log('📋 Отправляем пустой массив для удаления всех технологий');
                } else if (selectedCheckboxes.length > 0) {
                // Отправляем каждый ID отдельно для FormData
                    selectedCheckboxes.forEach(checkbox => {
                        formData.append('programming_language_ids', checkbox.value);
                    });
                    console.log('📋 Отправляем programming_language_ids:', selectedCheckboxes.map(cb => cb.value));
            } else {
                    // Если ничего не выбрано и нет флага очистки, НЕ отправляем programming_language_ids
                    console.log('📋 Нет выбранных технологий, НЕ отправляем programming_language_ids (оставляем существующие)');
                }
            } else {
                console.log('📋 Контейнер технологий не найден');
            }
                
                // Добавляем остальные поля формы
                formData.append('website', elements.websiteInput.value);
                formData.append('telegram', elements.telegramInput.value);
                formData.append('github', elements.githubInput.value);
                formData.append('linkedin', elements.linkedinInput.value);
                formData.append('instagram', elements.instagramInput.value);
                formData.append('facebook', elements.facebookInput.value);
                formData.append('youtube', elements.youtubeInput.value);

                try {
                    const response = await fetch(`/api/accounts/miniapp-users/update/${telegramId}/`, {
                        method: 'PATCH', // Используем PATCH для частичного обновления
                        body: formData, // FormData автоматически устанавливает Content-Type: multipart/form-data
                        // headers: { 'Content-Type': 'multipart/form-data' } // Не устанавливать вручную для FormData
                    });

                    if (response.ok) {
                        const updatedUserData = await response.json();
                        console.log('✅ Профиль успешно обновлен:', updatedUserData);
                        console.log('🔍 programming_languages в ответе сервера:', updatedUserData.programming_languages);
                        showNotification('profile_update_success', 'success', null, getTranslation('profile_update_success', 'Профиль успешно обновлен!'));
                        
                        // Закрываем модальное окно сначала
                        elements.editModal.style.display = 'none';
                        
                        // Обновляем глобальный объект currentUser
                        window.currentUser = updatedUserData;
                        
                        // Сохраняем Telegram ID в глобальной переменной для использования в формах
                        if (updatedUserData.telegram_id) {
                            window.telegramUserId = updatedUserData.telegram_id;
                            console.log('💾 Telegram ID сохранен:', updatedUserData.telegram_id);
                        }
                        
                        // Обновляем отображение профиля с задержкой для корректного отображения
                        setTimeout(() => {
                            console.log('🔄 Обновляем отображение профиля после сохранения');
                            
                            // Принудительно показываем контейнер профиля
                            const elements = getDOMElements();
                            console.log('🔍 Состояние контейнера профиля до обновления:', {
                                exists: !!elements.profileContainer,
                                display: elements.profileContainer ? elements.profileContainer.style.display : 'не найден',
                                visibility: elements.profileContainer ? elements.profileContainer.style.visibility : 'не найден',
                                computedDisplay: elements.profileContainer ? window.getComputedStyle(elements.profileContainer).display : 'не найден',
                                innerHTML: elements.profileContainer ? elements.profileContainer.innerHTML.length : 'не найден'
                            });
                            
                            if (elements.profileContainer) {
                                // Принудительно показываем контейнер
                                elements.profileContainer.style.display = 'block';
                                elements.profileContainer.style.visibility = 'visible';
                                elements.profileContainer.style.opacity = '1';
                                elements.profileContainer.removeAttribute('hidden');
                                elements.profileContainer.classList.remove('hidden');
                                console.log('✅ Контейнер профиля принудительно показан');
                            }
                            
                            // AJAX обновление всех элементов профиля
                            console.log('🔄 AJAX обновление профиля после сохранения');
                            updateProfileAfterSave(updatedUserData);
                            
                            // Принудительно обновляем переводы после обновления профиля
                            setTimeout(() => {
                                console.log('🔄 Принудительное обновление переводов после сохранения профиля');
                                updateProfessionalInfoTranslations();
                                
                                // Дополнительная проверка видимости профиля
                                const elementsAfter = getDOMElements();
                                console.log('🔍 Состояние контейнера профиля после обновления:', {
                                    exists: !!elementsAfter.profileContainer,
                                    display: elementsAfter.profileContainer ? elementsAfter.profileContainer.style.display : 'не найден',
                                    visibility: elementsAfter.profileContainer ? elementsAfter.profileContainer.style.visibility : 'не найден',
                                    computedDisplay: elementsAfter.profileContainer ? window.getComputedStyle(elementsAfter.profileContainer).display : 'не найден',
                                    innerHTML: elementsAfter.profileContainer ? elementsAfter.profileContainer.innerHTML.length : 'не найден'
                                });
                                
                                if (elementsAfter.profileContainer) {
                                    elementsAfter.profileContainer.style.display = 'block';
                                    elementsAfter.profileContainer.style.visibility = 'visible';
                                    elementsAfter.profileContainer.style.opacity = '1';
                                    elementsAfter.profileContainer.removeAttribute('hidden');
                                    elementsAfter.profileContainer.classList.remove('hidden');
                                    console.log('🔧 Финальное исправление видимости профиля');
                                }
                                
                                // Дополнительная проверка через еще одну задержку
                                setTimeout(() => {
                                    const elementsFinal = getDOMElements();
                                    if (elementsFinal.profileContainer) {
                                        const computedStyle = window.getComputedStyle(elementsFinal.profileContainer);
                                        console.log('🔍 Финальная проверка видимости:', {
                                            styleDisplay: elementsFinal.profileContainer.style.display,
                                            computedDisplay: computedStyle.display,
                                            visibility: computedStyle.visibility,
                                            opacity: computedStyle.opacity,
                                            innerHTML: elementsFinal.profileContainer.innerHTML.length
                                        });
                                        
                                        if (computedStyle.display === 'none' || elementsFinal.profileContainer.style.display === 'none') {
                                            elementsFinal.profileContainer.style.display = 'block';
                                            elementsFinal.profileContainer.style.visibility = 'visible';
                                            elementsFinal.profileContainer.style.opacity = '1';
                                            elementsFinal.profileContainer.removeAttribute('hidden');
                                            elementsFinal.profileContainer.classList.remove('hidden');
                                            console.log('🔧 Экстренное исправление видимости профиля');
                                        }
                                        
                                        // Проверяем, есть ли содержимое в профиле
                                        if (elementsFinal.profileContainer.innerHTML.length < 100) {
                                            console.log('⚠️ ПРОБЛЕМА: Контейнер профиля пустой или почти пустой!');
                                            console.log('🔍 Содержимое контейнера:', elementsFinal.profileContainer.innerHTML);
                                        }
                                    }
                                }, 200);
                            }, 100);
                        }, 100);
                    } else {
                        const errorData = await response.json();
                        console.error('❌ Ошибка обновления профиля:', errorData);
                        showNotification('profile_update_error', 'error', null, getTranslation('profile_update_error', 'Ошибка при обновлении профиля: ') + JSON.stringify(errorData));
                    }
                } catch (error) {
                    console.error('❌ Ошибка при отправке формы профиля:', error);
                    showNotification('profile_update_error', 'error', null, getTranslation('profile_update_error', 'Ошибка при обновлении профиля.') + ` ${error.message}`);
                }
            };
        }
    };

    // --- Первичный запуск ---
    console.log('📜 Profile script loaded, DOM ready state:', document.readyState);
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            console.log('📜 DOMContentLoaded event fired');
            window.initProfilePage();
        });
    } else {
        console.log('📜 DOM already ready, calling initProfilePage immediately');
        window.initProfilePage();
    }

    // Функция для обновления профессиональной информации при смене языка
    window.updateProfessionalInfoOnLanguageChange = function() {
        console.log('🌐 Обновление профессиональной информации при смене языка');
        
        // Обновляем грейд если он есть
        const gradeElement = document.getElementById('profile-grade');
        if (gradeElement && window.currentUser && window.currentUser.grade) {
            const gradeLabels = {
                'junior': (window.translations && window.translations) ? window.translations.grade_junior || 'Junior' : 'Junior',
                'middle': (window.translations && window.translations) ? window.translations.grade_middle || 'Middle' : 'Middle', 
                'senior': (window.translations && window.translations) ? window.translations.grade_senior || 'Senior' : 'Senior'
            };
            const gradeText = gradeLabels[window.currentUser.grade] || window.currentUser.grade;
            gradeElement.textContent = gradeText;
            console.log(`🔄 Грейд обновлен: ${gradeText}`);
        }
        
        // Обновляем текст "Не указан" если грейда нет
        if (gradeElement && (!window.currentUser || !window.currentUser.grade)) {
            gradeElement.textContent = (window.translations && window.translations) ? window.translations.not_specified || 'Не указан' : 'Не указан';
        }
        
        // Обновляем текст "Не указаны" для технологий если их нет
        const technologiesElement = document.getElementById('profile-technologies');
        if (technologiesElement && (!window.currentUser || !window.currentUser.programming_languages || window.currentUser.programming_languages.length === 0)) {
            const noDataElement = technologiesElement.querySelector('.no-data');
            if (noDataElement) {
                noDataElement.textContent = (window.translations && window.translations) ? window.translations.no_technologies || 'Технологии не указаны' : 'Технологии не указаны';
            }
        }
    };

    // Обработчик смены языка
    window.onLanguageChanged = function() {
        console.log('🌐 Язык изменен, обновляем переводы в профиле');
        updateProfessionalInfoTranslations();
    };

    // Альтернативный обработчик для совместимости
    window.updateProfessionalInfoOnLanguageChange = function() {
        console.log('🌐 Альтернативный обработчик смены языка вызван');
        updateProfessionalInfoTranslations();
    };

    // Вызываем обновление переводов при загрузке страницы
    document.addEventListener('DOMContentLoaded', function() {
        console.log('🌐 DOM загружен, проверяем переводы в профиле');
        setTimeout(() => {
            updateProfessionalInfoTranslations();
        }, 500);
    });

    // Функция для переинициализации при SPA навигации
    window.reinitializeProfilePage = function() {
        console.log('🔄 reinitializeProfilePage вызван для SPA навигации');
        
        // Переинициализируем обработчики событий
        const elements = getDOMElements();
        
        // Добавляем обработчик изменения размера окна для корректного позиционирования модального окна
        window.addEventListener('resize', () => {
            if (elements.editModal && elements.editModal.style.display === 'block') {
                const modalContent = elements.editModal.querySelector('.modal-content');
                if (modalContent) {
                    // Сбрасываем стили позиционирования при изменении размера
                    modalContent.style.position = '';
                    modalContent.style.top = '';
                    modalContent.style.left = '';
                    modalContent.style.transform = '';
                    
                    // Применяем новое позиционирование для мобильных устройств
                    if (window.innerWidth <= 768) {
                        setTimeout(() => {
                            modalContent.style.position = 'relative';
                            modalContent.style.top = '10px';
                        }, 100);
                    }
                }
            }
        });
        
        // Переинициализируем обработчик кнопки редактирования
        if (elements.editProfileBtn) {
            elements.editProfileBtn.onclick = () => {
                elements.editModal.style.display = 'block';
                
                // Улучшенное позиционирование для мобильных устройств
                const modalContent = elements.editModal.querySelector('.modal-content');
                if (modalContent) {
                    // Сбрасываем любые предыдущие стили позиционирования
                    modalContent.style.position = '';
                    modalContent.style.top = '';
                    modalContent.style.left = '';
                    modalContent.style.transform = '';
                    
                    // Для мобильных устройств добавляем специальное позиционирование
                    if (window.innerWidth <= 768) {
                        // Прокручиваем к началу страницы для лучшего отображения
                        window.scrollTo(0, 0);
                        
                        // Добавляем небольшую задержку для корректного отображения
                        setTimeout(() => {
                            modalContent.style.position = 'relative';
                            modalContent.style.top = '10px';
                        }, 50);
                    }
                }
                
                // Заполняем поля формы текущими данными профиля
                const currentUser = window.currentUser;
                console.log('🔍 Текущий пользователь для заполнения формы:', currentUser);
                
                if (currentUser && currentUser.id && currentUser.first_name !== 'Тестовый') {
                    // Заполняем поля формы
                    const gradeInput = document.getElementById('grade-input');
                    if (gradeInput) {
                        gradeInput.value = currentUser.grade || '';
                    }
                    
                    const genderInput = document.getElementById('gender-input');
                    if (genderInput) {
                        genderInput.value = currentUser.gender || '';
                    }
                    
                    const birthDateInput = document.getElementById('birth-date-input');
                    if (birthDateInput) {
                        birthDateInput.value = currentUser.birth_date || '';
                    }
                    
                    // Загружаем технологии (передаем все выбранные)
                    if (currentUser.programming_languages && currentUser.programming_languages.length > 0) {
                        console.log('📝 Загружаем технологии, все выбранные:', currentUser.programming_languages);
                        loadTechnologiesWithNames(currentUser.programming_languages);
                    } else {
                        console.log('📝 Нет выбранных технологий, загружаем пустой список');
                        loadTechnologiesWithNames([]);
                    }
                    
                    // Заполняем социальные сети
                    const currentSocialLinks = currentUser.social_links || [];
                    elements.websiteInput.value = currentSocialLinks.find(link => link.name === 'Веб-сайт')?.url || '';
                    elements.telegramInput.value = currentSocialLinks.find(link => link.name === 'Telegram')?.url.replace('https://t.me/', '') || '';
                    elements.githubInput.value = currentSocialLinks.find(link => link.name === 'GitHub')?.url || '';
                    elements.linkedinInput.value = currentSocialLinks.find(link => link.name === 'LinkedIn')?.url || '';
                    elements.instagramInput.value = currentSocialLinks.find(link => link.name === 'Instagram')?.url || '';
                    elements.facebookInput.value = currentSocialLinks.find(link => link.name === 'Facebook')?.url || '';
                    elements.youtubeInput.value = currentSocialLinks.find(link => link.name === 'YouTube')?.url || '';
                    
                    // Предварительный просмотр аватара
                    if (currentUser.avatar) {
                        elements.avatarPreview.innerHTML = `<img src="${currentUser.avatar}" alt="Current Avatar" style="max-width: 100px; max-height: 100px; border-radius: 50%; object-fit: cover;">`;
                    } else {
                        elements.avatarPreview.innerHTML = '';
                    }
                }
            };
        }
        
        // Переинициализируем обработчик кнопки обновления
        if (elements.refreshBtn) {
            elements.refreshBtn.onclick = async () => {
                console.log('🔄 Кнопка "Обновить данные" нажата');
                if (window.showNotification) {
                    window.showNotification('refreshing_data', 'info');
                } else {
                    showNotification('refreshing_data', 'info', null, 'Refreshing data...');
                }
                
                // Обновляем статус онлайн
                const telegramId = window.currentUser?.telegram_id;
                if (telegramId) {
                    try {
                        console.log('🟢 Обновление статуса онлайн для telegram_id:', telegramId);
                        const response = await fetch('/api/accounts/miniapp-users/update-last-seen/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ telegram_id: telegramId })
                        });
                        
                        if (response.ok) {
                            console.log('✅ Статус онлайн обновлен успешно');
                        } else {
                            console.warn('⚠️ Не удалось обновить статус онлайн:', response.status);
                        }
                    } catch (error) {
                        console.error('❌ Ошибка при обновлении статуса онлайн:', error);
                    }
                } else {
                    console.warn('⚠️ Не найден telegram_id для обновления статуса онлайн');
                }
                
                fetchProfileDataFromServer();
            };
        }
        
        console.log('✅ Profile page переинициализирован для SPA навигации');
    };

})(window);
