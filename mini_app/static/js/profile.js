/**
 * JavaScript модуль для управления профилем пользователя в Telegram Mini App.
 * Обеспечивает загрузку и отображение данных профиля, а также
 * предоставляет глобальную функцию для инициализации при SPA-навигации.
 */

// Обертка для инкапсуляции логики и предотвращения засорения глобальной области
(function(window) {
    // Переменные состояния модуля
    let isLoading = false;
    let tg = window.Telegram?.WebApp;

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
        const { profileAvatar } = getDOMElements();
        if (profileAvatar) {
            // Если avatarUrl не пришел или пустой, используем заглушку.
            // В противном случае, используем пришедший URL.
            profileAvatar.src = avatarUrl || '/static/images/default_avatar.png';
            profileAvatar.style.display = 'block';
            
            // Добавляем обработчик ошибок, чтобы в случае битой ссылки
            // также показать заглушку.
            profileAvatar.onerror = () => {
                console.warn(`Не удалось загрузить аватар по ссылке: ${avatarUrl}. Установлена заглушка.`);
                profileAvatar.src = '/static/images/default_avatar.png';
                profileAvatar.onerror = null; // Убираем обработчик, чтобы избежать бесконечного цикла
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
        const elements = getDOMElements();
        if (!userData || !elements.profileContainer) {
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
    }


    // --- Управление состоянием загрузки ---

    function showLoader() {
        const elements = getDOMElements();
        if (elements.loader) elements.loader.style.display = 'flex';
        if (elements.profileContainer) elements.profileContainer.style.display = 'none';
    }

    function hideLoader() {
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
        if (isLoading) {
            console.log("Загрузка уже в процессе.");
            return;
        }
        isLoading = true;
        showLoader();

        try {
            if (!tg || !tg.initData) {
                console.warn("Телеграм не определен. Используется тестовый вызов.");
                // Для локальной разработки можно использовать тестовый эндпоинт
                const response = await fetch('/api/profile/by-telegram/123456/');
                 if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                updateProfileDOM(data);
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
        console.log("Инициализация страницы профиля...");
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
