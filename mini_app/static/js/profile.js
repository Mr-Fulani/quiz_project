/**
 * JavaScript модуль для управления профилем пользователя в Telegram Mini App.
 * Обеспечивает загрузку и отображение данных профиля, а также
 * предоставляет глобальную функцию для инициализации при SPA-навигации.
 */

// Обертка для инкапсуляции логики и предотвращения засорения глобальной области
(function(window) {
    // Переменные состояния модуля
    let isLoading = false;
    
    // Функция для получения актуального состояния Telegram WebApp
    function getTelegramWebApp() {
        return window.Telegram?.WebApp;
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
        };
    }

    // --- Функции обновления UI ---

    function updateAvatar(avatarUrl) {
        const { avatar } = getDOMElements();
        if (avatar) {
            const finalUrl = avatarUrl || '/static/images/default_avatar.png';
            avatar.src = finalUrl;
            avatar.style.display = 'block';
            
            avatar.onerror = () => {
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

        const fullName = `${userData.first_name || ''} ${userData.last_name || ''}`.trim();
        elements.name.textContent = fullName || 'Пользователь';
        elements.username.textContent = userData.username ? `@${userData.username}` : 'скрыт';
        
        updateAvatar(userData.avatar);
        updateSocialLinks(userData.social_links, elements);

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
