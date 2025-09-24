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
            
            avatar.src = finalUrl;
            avatar.style.display = 'block';
            
            avatar.onerror = () => {
                console.warn('Ошибка загрузки аватара:', finalUrl);
                avatar.src = '/static/images/default_avatar.png';
                avatar.onerror = null;
            };
        }
    }

    function updateProfessionalInfo(userData) {
        console.log('💼 updateProfessionalInfo вызван с данными:', userData);
        
        // Обновляем грейд с эффектами
        const gradeElement = document.getElementById('profile-grade');
        if (gradeElement) {
            if (userData.grade) {
                const gradeLabels = {
                    'junior': (window.translations && window.translations.get) ? window.translations.get('grade_junior', 'Junior') : 'Junior',
                    'middle': (window.translations && window.translations.get) ? window.translations.get('grade_middle', 'Middle') : 'Middle', 
                    'senior': (window.translations && window.translations.get) ? window.translations.get('grade_senior', 'Senior') : 'Senior'
                };
                const gradeText = gradeLabels[userData.grade] || userData.grade;
                
                // Добавляем классы для эффектов в зависимости от грейда
                gradeElement.className = `info-value grade-${userData.grade}`;
                gradeElement.textContent = gradeText;
                
                console.log(`🎯 Грейд установлен: ${gradeText} (${userData.grade})`);
            } else {
                gradeElement.className = 'info-value grade-none';
                gradeElement.textContent = (window.translations && window.translations.get) ? window.translations.get('not_specified', 'Не указан') : 'Не указан';
            }
        }
        
        // Обновляем технологии
        const technologiesElement = document.getElementById('profile-technologies');
        if (technologiesElement) {
            if (userData.programming_languages && userData.programming_languages.length > 0) {
                technologiesElement.innerHTML = '';
                userData.programming_languages.forEach(tech => {
                    const techTag = document.createElement('span');
                    techTag.className = 'technology-tag';
                    techTag.textContent = tech;
                    technologiesElement.appendChild(techTag);
                });
            } else {
                technologiesElement.innerHTML = '<span class="no-data">Технологии не указаны</span>';
            }
        }
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
            
                // Создаем обычный выпадающий список для выбора одной технологии
                const selectHTML = `
                    <select id="technologies-select" name="programming_language_ids">
                        <option value="">Выберите технологию</option>
                        ${technologies.map(tech => {
                            const isSelected = selectedTechnologyNames.includes(tech.name);
                            console.log(`🔍 Технология: ${tech.name}, ID: ${tech.id}, Выбрана: ${isSelected}`);
                            return `<option value="${tech.id}" ${isSelected ? 'selected' : ''}>${tech.name}</option>`;
                        }).join('')}
                    </select>
                `;
            
            console.log('🎨 HTML для select:', selectHTML);
            container.innerHTML = selectHTML;
            
            console.log('✅ Выпадающий список технологий создан');
            console.log('🎯 Созданный select элемент:', document.getElementById('technologies-select'));
            
        } catch (error) {
            console.error('❌ Ошибка загрузки технологий:', error);
            container.innerHTML = '<div class="technologies-error">Ошибка загрузки технологий: ' + error.message + '</div>';
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
        
        // Обновляем глобальный объект currentUser с актуальными данными из БД
        window.currentUser = userData;
        console.log('💾 window.currentUser обновлен с актуальными данными:', userData);

        const fullName = `${userData.first_name || ''} ${userData.last_name || ''}`.trim();
        elements.name.textContent = fullName || 'Пользователь';
        elements.username.textContent = userData.username ? `@${userData.username}` : 'скрыт';
        
        updateAvatar(userData.avatar);
        updateProfessionalInfo(userData);
        updateSocialLinks(userData.social_links, elements);

        // Заполняем поля модального окна при загрузке профиля
        const socialLinks = userData.social_links || [];
        elements.websiteInput.value = socialLinks.find(link => link.name === 'Веб-сайт')?.url || '';
        elements.telegramInput.value = socialLinks.find(link => link.name === 'Telegram')?.url.replace('https://t.me/', '') || '';
        elements.githubInput.value = socialLinks.find(link => link.name === 'GitHub')?.url || '';
        elements.linkedinInput.value = socialLinks.find(link => link.name === 'LinkedIn')?.url || '';
        elements.instagramInput.value = socialLinks.find(link => link.name === 'Instagram')?.url || '';
        elements.facebookInput.value = socialLinks.find(link => link.name === 'Facebook')?.url || '';
        elements.youtubeInput.value = socialLinks.find(link => link.name === 'YouTube')?.url || '';

        hideLoader();
        elements.profileContainer.style.display = 'block';
        console.log('✅ Профиль успешно обновлен и показан');
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
            
            if (!tg || !tg.initData) {
                console.log('⚠️ Нет initData, показываем заглушку');
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
                    progress: []
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
                    
                    // Загружаем и заполняем технологии (берем только первую)
                    if (currentUser.programming_languages && currentUser.programming_languages.length > 0) {
                        const firstTechnology = currentUser.programming_languages[0];
                        console.log('📝 Загружаем технологии, первая выбрана:', firstTechnology);
                        loadTechnologiesWithNames([firstTechnology]);
                    } else {
                        console.log('📝 Нет выбранных технологий, загружаем пустой список');
                        loadTechnologiesWithNames([]);
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
            elements.refreshBtn.onclick = () => {
                console.log('🔄 Кнопка "Обновить данные" нажата');
                // Используем глобальную функцию showNotification из base.html для автоматического исчезновения
                if (window.showNotification) {
                    window.showNotification('refreshing_data', 'info', null, 'Обновление данных...');
                } else {
                    showNotification('refreshing_data', 'info', null, 'Обновление данных...');
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
                
            // Собираем выбранную технологию из выпадающего списка (одну)
            const technologiesSelect = document.getElementById('technologies-select');
            if (technologiesSelect && technologiesSelect.value) {
                const selectedTechnologyId = parseInt(technologiesSelect.value);
                // Отправляем как массив чисел, а не как JSON строку
                formData.append('programming_language_ids', `[${selectedTechnologyId}]`);
                console.log('📋 Отправляем programming_language_ids:', `[${selectedTechnologyId}]`);
            } else {
                console.log('📋 Нет выбранной технологии, не отправляем programming_language_ids');
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
                        showNotification('profile_update_success', 'success', null, getTranslation('profile_update_success', 'Профиль успешно обновлен!'));
                        
                        // Обновляем отображение аватара и других данных
                        updateProfileDOM(updatedUserData);
                        elements.editModal.style.display = 'none';
                        
                        // Обновляем глобальный объект currentUser
                        window.currentUser = updatedUserData;
                        
                        // Сохраняем Telegram ID в глобальной переменной для использования в формах
                        if (updatedUserData.telegram_id) {
                            window.telegramUserId = updatedUserData.telegram_id;
                            console.log('💾 Telegram ID сохранен:', updatedUserData.telegram_id);
                        }
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
                'junior': (window.translations && window.translations.get) ? window.translations.get('grade_junior', 'Junior') : 'Junior',
                'middle': (window.translations && window.translations.get) ? window.translations.get('grade_middle', 'Middle') : 'Middle', 
                'senior': (window.translations && window.translations.get) ? window.translations.get('grade_senior', 'Senior') : 'Senior'
            };
            const gradeText = gradeLabels[window.currentUser.grade] || window.currentUser.grade;
            gradeElement.textContent = gradeText;
            console.log(`🔄 Грейд обновлен: ${gradeText}`);
        }
        
        // Обновляем текст "Не указан" если грейда нет
        if (gradeElement && (!window.currentUser || !window.currentUser.grade)) {
            gradeElement.textContent = (window.translations && window.translations.get) ? window.translations.get('not_specified', 'Не указан') : 'Не указан';
        }
        
        // Обновляем текст "Не указаны" для технологий если их нет
        const technologiesElement = document.getElementById('profile-technologies');
        if (technologiesElement && (!window.currentUser || !window.currentUser.programming_languages || window.currentUser.programming_languages.length === 0)) {
            const noDataElement = technologiesElement.querySelector('.no-data');
            if (noDataElement) {
                noDataElement.textContent = (window.translations && window.translations.get) ? window.translations.get('no_technologies', 'Технологии не указаны') : 'Технологии не указаны';
            }
        }
    };

})(window);
