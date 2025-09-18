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

    function updateSocialLinks(socialLinks, elements) {
        elements.socials.innerHTML = '';
        if (socialLinks && socialLinks.length > 0) {
            socialLinks.forEach(link => {
                const iconClass = `fab fa-${link.name.toLowerCase()}`;
                const socialItem = document.createElement('a');
                socialItem.className = 'social-link-card';
                socialItem.href = link.url;
                socialItem.target = '_blank';
                socialItem.innerHTML = `
                    <div class="social-icon"><i class="${iconClass}"></i></div>
                    <div class="social-info">
                        <div class="social-name">${link.name}</div>
                        <div class="social-url">${link.url.replace(/^(https?:\/\/)?(www\.)?/, '')}</div>
                    </div>
                `;
                elements.socials.appendChild(socialItem);
            });
        } else {
            elements.socials.innerHTML = '<p class="social-empty">Социальные сети не указаны.</p>';
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
        
        // Обновляем глобальный объект currentUser с актуальными данными из БД
        window.currentUser = userData;
        console.log('💾 window.currentUser обновлен с актуальными данными:', userData);

        const fullName = `${userData.first_name || ''} ${userData.last_name || ''}`.trim();
        elements.name.textContent = fullName || 'Пользователь';
        elements.username.textContent = userData.username ? `@${userData.username}` : 'скрыт';
        
        updateAvatar(userData.avatar);
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
                if (currentUser) {
                    const fullName = `${currentUser.first_name || ''} ${currentUser.last_name || ''}`.trim();
                    // elements.name.textContent = fullName || 'Пользователь'; // Это не input, а h1
                    // elements.username.textContent = currentUser.username ? `@${currentUser.username}` : translations.get('hidden', 'скрыт');
                    // Здесь нужно заполнить поля ввода, а не текстовые элементы
                    elements.editProfileForm.querySelector('input[name="first_name"]').value = currentUser.first_name || '';
                    elements.editProfileForm.querySelector('input[name="last_name"]').value = currentUser.last_name || '';
                    elements.editProfileForm.querySelector('input[name="username"]').value = currentUser.username || '';
                    
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

})(window);
