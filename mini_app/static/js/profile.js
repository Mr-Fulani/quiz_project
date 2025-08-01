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
    // Выносим получение элементов в одну функцию для централизации
    function getDOMElements() {
        return {
            loader: document.getElementById('loader'),
            profileContainer: document.getElementById('profile-container'),
            name: document.getElementById('profile-name'),
            username: document.getElementById('profile-username'),
            avatar: document.getElementById('profile-avatar'),
            points: document.getElementById('profile-points'),
            rating: document.getElementById('profile-rating'),
            quizzes: document.getElementById('profile-quizzes'),
            success: document.getElementById('profile-success'),
            progress: document.getElementById('progress-container'),
            socials: document.getElementById('social-links-container'),
        };
    }

    // --- Функции обновления UI ---

    function updateAvatar(avatarUrl) {
        const { avatar } = getDOMElements();
        if (avatar) {
            // Если avatarUrl не пришел или пустой, используем заглушку.
            // В противном случае, используем пришедший URL.
            const finalUrl = avatarUrl || '/static/images/default_avatar.png';
            avatar.src = finalUrl;
            avatar.style.display = 'block';
            
            // Добавляем обработчик ошибок, чтобы в случае битой ссылки
            // также показать заглушку.
            avatar.onerror = () => {
                avatar.src = '/static/images/default_avatar.png';
                avatar.onerror = null; // Убираем обработчик, чтобы избежать бесконечного цикла
            };
        }
    }

    function updateSocialLinks(socialLinks, elements) {
        elements.socials.innerHTML = ''; // Очищаем контейнер
        if (socialLinks && socialLinks.length > 0) {
            socialLinks.forEach(link => {
                // Предполагаем, что иконки - это FontAwesome или подобные классы
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
    
    function updateProgress(progressData, elements) {
        elements.progress.innerHTML = '';
        if (progressData && progressData.length > 0) {
            progressData.forEach(item => {
                const progressItem = document.createElement('div');
                progressItem.className = 'progress-item';
                progressItem.innerHTML = `
                    <div class="progress-info">
                        <span class="progress-topic">${item.topic_name}</span>
                        <span class="progress-details">${item.completed_quizzes} / ${item.total_quizzes}</span>
                    </div>
                    <div class="progress-bar-background">
                        <div class="progress-bar-fill" style="width: ${item.progress_percentage}%;"></div>
                    </div>`;
                elements.progress.appendChild(progressItem);
            });
        } else {
            elements.progress.innerHTML = '<p>Нет данных о прогрессе.</p>';
        }
    }


                function updateProfileDOM(userData) {
                console.log('🚀 updateProfileDOM вызван с данными:', userData);
                const elements = getDOMElements();
                console.log('🔍 DOM элементы:', elements);
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
        updateProgress(userData.progress, elements);

        elements.points.textContent = userData.points || 0;
        elements.rating.textContent = userData.rating || 0;
        elements.quizzes.textContent = userData.quizzes_completed || 0;
        elements.success.textContent = `${(userData.success_rate || 0).toFixed(1)}%`;

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
        // Устанавливаем флаг, что загрузка началась
        window.profileLoading = true;
    }

    function hideLoader() {
        console.log('🔄 hideLoader вызван');
        const elements = getDOMElements();
        if (elements.loader) elements.loader.style.display = 'none';
        // Сбрасываем флаг загрузки
        window.profileLoading = false;
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
        console.log('🔍 fetchProfileDataFromServer вызван, isLoading:', isLoading, 'window.profileLoading:', window.profileLoading);
        
        // Если уже идет загрузка или профиль уже загружен, не запускаем повторно
        if (isLoading || window.profileLoading) {
            console.log('⏸️ Загрузка уже идет, пропускаем');
            return;
        }
        
        isLoading = true;
        showLoader();

        try {
            console.log('🔍 fetchProfileDataFromServer вызван');
            console.log('window.currentUser:', window.currentUser);
            console.log('window.isUserInitialized:', window.isUserInitialized);
            
            // Проверяем, есть ли уже инициализированные данные пользователя в localStorage
            const savedUserData = localStorage.getItem('telegramUserData');
            console.log('🔍 localStorage.getItem("telegramUserData"):', savedUserData);
            if (savedUserData) {
                try {
                    const userData = JSON.parse(savedUserData);
                    console.log('✅ Используем сохраненные данные пользователя из localStorage');
                    updateProfileDOM(userData);
                    return;
                } catch (e) {
                    console.log('❌ Ошибка при парсинге сохраненных данных:', e);
                    localStorage.removeItem('telegramUserData');
                }
            } else {
                console.log('❌ Нет сохраненных данных в localStorage');
            }

            const tg = getTelegramWebApp();
            console.log('🔍 Telegram WebApp:', tg);
            console.log('🔍 initData:', tg?.initData);
            
            if (!tg || !tg.initData) {
                console.log('⚠️ Нет initData, показываем тестового пользователя');
                // В браузере показываем заглушку профиля
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
            const response = await fetch('/api/verify-init-data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ initData: tg.initData })
            });

            if (!response.ok) {
                const errorBody = await response.text();
                throw new Error(`Ошибка ${response.status}: ${errorBody}`);
            }

            const data = await response.json();
            
            // Сохраняем данные пользователя в localStorage для повторного использования
            localStorage.setItem('telegramUserData', JSON.stringify(data));
            
            updateProfileDOM(data);

        } catch (error) {
            console.error('Ошибка при загрузке профиля:', error);
            showError(`Не удалось загрузить профиль. ${error.message}`);
        } finally {
            isLoading = false;
        }
    }

    // --- Глобальная функция инициализации ---
    // Эта функция будет вызываться из base.html при навигации
    window.initProfilePage = function() {
        tg = window.Telegram?.WebApp;
        if (tg) {
            tg.ready();
            tg.expand();
        }
        fetchProfileDataFromServer();
    };

    // --- Первичный запуск ---
    // Вызываем при первой загрузке скрипта
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', window.initProfilePage);
    } else {
        window.initProfilePage();
    }

})(window);
