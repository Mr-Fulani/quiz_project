/**
 * JavaScript для dashboard: вкладки, аватар, настройки, мобильное меню.
 */
document.addEventListener('DOMContentLoaded', function () {
    // ================================
    // НАДЕЖНАЯ ФУНКЦИЯ УВЕДОМЛЕНИЙ
    // ================================
    // Проверяем, существует ли глобальная функция, и если нет, создаем свою (alert).
    // Это предотвращает падение скрипта, если другой файл с showNotification сломался.
    if (typeof window.showNotification !== 'function') {
        console.warn('Global showNotification() not found. Using fallback alert().');
        window.showNotification = function(message, type = 'success') {
            alert(message);
        };
    }

    // ================================
    // 0. Проверяем наличие переменной messages из шаблона
    // ================================
    if (typeof messages === 'undefined') {
        console.warn('Messages object not found. Using default English messages.');
        window.messages = {
            avatar_updated: "Аватар успешно обновлен!",
            avatar_error: "Ошибка обновления аватара.",
            avatar_too_large: "Файл аватара слишком большой. Максимальный размер: 50 МБ.",
            avatar_invalid_format: "Недопустимый формат файла. Разрешены: JPG, PNG, GIF.",
            profile_updated: "Профиль успешно обновлен!",
            profile_error: "Ошибка обновления профиля.",
            settings_updated: "Настройки обновлены!",
            settings_error: "Ошибка обновления настроек.",
            password_changed: "Пароль успешно изменен!",
            password_error: "Ошибка изменения пароля.",
            content_load_error: "Не удалось загрузить содержимое.",
            solved_tasks: "Решенные задачи",
            task_count: "Количество задач",
            file_too_large: "Файл слишком большой. Максимальный размер: 50 МБ.",
            invalid_file_format: "Недопустимый формат файла.",
            upload_error: "Ошибка загрузки файла.",
            network_error: "Ошибка сети. Проверьте подключение к интернету."
        };
    }

    // ================================
    // 1. Переключение вкладок (Tabs)
    // ================================
    const tabs = document.querySelectorAll('.tab-btn');
    const mobileTabs = document.querySelectorAll('.mobile-tab-btn');
    const contents = document.querySelectorAll('.tab-content');

    console.log('Found tabs:', tabs.length, 'mobile tabs:', mobileTabs.length, 'contents:', contents.length);

    /**
     * Переключает вкладки и загружает содержимое через AJAX, если есть data-url.
     * @param {HTMLElement} tab - Кнопка вкладки.
     * @param {boolean} isMobile - Флаг мобильного меню.
     */
    function switchTab(tab, isMobile = false) {
        console.log('Switching to tab:', tab.dataset.tab, 'isMobile:', isMobile);

        // Удаляем класс active у всех вкладок и контента
        tabs.forEach(t => t.classList.remove('active'));
        mobileTabs.forEach(mt => mt.classList.remove('active'));
        contents.forEach(c => c.classList.remove('active'));

        // Добавляем класс active для текущей вкладки
        const tabId = tab.dataset.tab;
        tab.classList.add('active');

        // Синхронизируем десктопные и мобильные кнопки
        const desktopTab = document.querySelector(`.profile-tabs .tab-btn[data-tab="${tabId}"]`);
        const mobileTab = document.querySelector(`.mobile-tab-btn[data-tab="${tabId}"]`);

        if (desktopTab) desktopTab.classList.add('active');
        if (mobileTab) mobileTab.classList.add('active');

        // Активируем соответствующий контент
        const content = document.querySelector(`[data-tab-content="${tabId}"]`);
        if (content) {
            content.classList.add('active');
            console.log('Activated content for tab:', tabId);
        } else {
            console.warn('Content not found for tab:', tabId);
        }

        // Если есть data-url, загружаем содержимое через AJAX
        if (tab.dataset.url) {
            const contentContainer = content.querySelector(`#${tabId}-content`);
            if (contentContainer) {
                fetch(tab.dataset.url, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => response.text())
                .then(data => {
                    contentContainer.innerHTML = data;

                    // Если загружаем Statistics, инициализируем графики
                    if (tabId === 'statistics') {
                        initializeCharts();
                    }
                })
                .catch(error => {
                    console.error('Error loading content:', error);
                    showNotification(messages.content_load_error, 'error');
                });
            }
        }

        // Закрываем мобильное меню, если это мобильная вкладка
        if (isMobile) {
            const mobileMenuContent = document.querySelector('.mobile-menu-content');
            if (mobileMenuContent) {
                mobileMenuContent.classList.remove('active');
            }
        }
    }

    // Переключение вкладок для десктопных кнопок
    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Desktop tab clicked:', tab.dataset.tab);
            switchTab(tab);
        });
    });

    // Переключение вкладок для мобильных кнопок
    mobileTabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Mobile tab clicked:', tab.dataset.tab);
            switchTab(tab, true);
        });
    });

    // ================================
    // 2. Avatar upload (загрузка аватара)
    // ================================
    const avatarUpload = document.getElementById('avatar-form');
    if (avatarUpload) {
        const avatarInput = avatarUpload.querySelector('#id_avatar');
        avatarInput.addEventListener('change', async function (e) {
            e.preventDefault();
            
            // Проверяем размер файла перед загрузкой
            const file = e.target.files[0];
            if (file) {
                const maxSize = 50 * 1024 * 1024; // 50 МБ
                if (file.size > maxSize) {
                    showNotification(messages.avatar_too_large, 'error');
                    e.target.value = ''; // Очищаем input
                    return;
                }
                
                // Проверяем формат файла
                const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif'];
                if (!allowedTypes.includes(file.type)) {
                    showNotification(messages.avatar_invalid_format, 'error');
                    e.target.value = ''; // Очищаем input
                    return;
                }
            }
            
            const formData = new FormData(avatarUpload);
            try {
                const response = await fetch(avatarUpload.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                
                // Проверяем статус ответа
                if (response.status === 413) {
                    showNotification(messages.file_too_large, 'error');
                    return;
                }
                
                const data = await response.json();
                if (response.ok && data.status === 'success') {
                    showNotification(messages.avatar_updated, 'success');
                    const avatarImg = document.querySelector('.profile-avatar img');
                    // РЕШЕНИЕ: Добавляем параметр для сброса кэша браузера
                    avatarImg.src = data.avatar_url + '?v=' + new Date().getTime();
                } else {
                    showNotification(data.message || messages.avatar_error, 'error');
                }
            } catch (error) {
                console.error('Error uploading avatar:', error);
                if (error.name === 'TypeError' && error.message.includes('fetch')) {
                    showNotification(messages.network_error, 'error');
                } else {
                    showNotification(messages.upload_error, 'error');
                }
            }
        });
        // Предотвращаем стандартную отправку формы
        avatarUpload.addEventListener('submit', (e) => e.preventDefault());
    }

    // ================================
    // 3. Personal Info Form
    // ================================
    const personalInfoForm = document.getElementById('personal-info-form');
    const securityForm = document.querySelector('.security-form');

    if (personalInfoForm) {
        personalInfoForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            console.log('Submitting personal-info-form');
            const formData = new FormData(this);
            console.log('Sending form data:', Object.fromEntries(formData));
            try {
                const response = await fetch(this.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                console.log('Response status:', response.status);
                const data = await response.json();
                console.log('Response data:', data);
                if (response.ok && data.status === 'success') {
                    alert(messages.profile_updated || 'Профиль успешно обновлен!');
                    const dashboardUrl = document.querySelector('.profile').dataset.dashboardUrl || '/accounts/dashboard/';
                    window.location.href = dashboardUrl;
                } else {
                    alert(data.message || messages.profile_error || 'Ошибка при обновлении профиля.');
                }
            } catch (error) {
                console.error('Personal info form submission error:', error);
                alert(messages.profile_error || 'Ошибка при обновлении профиля.');
            }
        });
    }

    // Исправленная функция обработки формы смены пароля (строки ~140-200)
    if (securityForm) {
        securityForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            console.log('Submitting security-form');
            const formData = new FormData(this);

            // Очищаем предыдущие ошибки и сообщения об успехе
            document.querySelectorAll('.security-form .error').forEach(el => el.remove());
            const existingSuccess = document.querySelector('.security-form .success');
            if (existingSuccess) {
                existingSuccess.remove();
            }

            try {
                const response = await fetch(this.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                const data = await response.json();

                if (response.ok && data.status === 'success') {
                    // Успешная смена пароля
                    alert(messages.password_changed || 'Пароль успешно изменен!');

                    // Создаем элемент для успешного сообщения
                    const successElement = document.createElement('div');
                    successElement.className = 'success';
                    successElement.textContent = messages.password_changed;
                    successElement.style.display = 'block';

                    // Вставляем сообщение в начало формы
                    this.insertBefore(successElement, this.firstChild);

                    // Очищаем поля формы
                    this.reset();

                    // Скрываем сообщение через 5 секунд
                    setTimeout(() => {
                        if (successElement && successElement.parentNode) {
                            successElement.remove();
                        }
                    }, 5000);

                    // УБИРАЕМ автоматическую перезагрузку страницы
                    // setTimeout(() => {
                    //     window.location.reload();
                    // }, 2000);

                } else {
                    // Обработка ошибок
                    if (data.errors) {
                        const errors = JSON.parse(data.errors);
                        let errorMessages = '';
                        for (const [field, errorList] of Object.entries(errors)) {
                            errorMessages += `${field}: ${errorList.map(e => e.message).join(', ')}\n`;
                        }
                        alert(errorMessages);
                    } else {
                        alert(data.message || 'Произошла ошибка.');
                    }
                }
            } catch (error) {
                console.error('Security form submission error:', error);
                alert('Произошла критическая ошибка.');
            }
        });
    }

    // ================================
    // 4. Обработка настроек
    // ================================
    const settingsToggles = document.querySelectorAll('.settings-list input[type="checkbox"]');
    settingsToggles.forEach(toggle => {
        toggle.addEventListener('change', async function () {
            try {
                const response = await fetch('/accounts/settings/update/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify({
                        setting: this.name,
                        value: this.checked
                    })
                });
                if (!response.ok) throw new Error('Settings update failed');
                showNotification(messages.settings_updated, 'success');
            } catch (error) {
                console.error('Error:', error);
                this.checked = !this.checked;
                showNotification(messages.settings_error, 'error');
            }
        });
    });

    // ================================
    // 5. Обработка параметра URL "tab" для переключения вкладок
    // ================================
    // Исправленная обработка параметра URL "tab"
    const urlParams = new URLSearchParams(window.location.search);
    const activeTabFromUrl = urlParams.get('tab');

    if (activeTabFromUrl) {
        // Если есть параметр tab в URL, переключаемся на эту вкладку
        const tabButton = document.querySelector(`.profile-tabs .tab-btn[data-tab="${activeTabFromUrl}"]`);
        if (tabButton) {
            switchTab(tabButton);
        }
    } else {
        // Проверяем, какая вкладка активна в HTML (из Django шаблона)
        const activeTabButton = document.querySelector('.tab-btn.active');
        if (activeTabButton) {
            // Если есть активная кнопка, убеждаемся что соответствующий контент тоже активен
            const tabId = activeTabButton.dataset.tab;
            const activeContent = document.querySelector(`[data-tab-content="${tabId}"]`);
            if (activeContent && !activeContent.classList.contains('active')) {
                activeContent.classList.add('active');
            }
            // Синхронизируем мобильные кнопки
            const mobileTabButton = document.querySelector(`.mobile-tab-btn[data-tab="${tabId}"]`);
            if (mobileTabButton && !mobileTabButton.classList.contains('active')) {
                mobileTabButton.classList.add('active');
            }
        } else {
            // Если нет активной вкладки, активируем Personal Info по умолчанию
            const defaultTabButton = document.querySelector('.profile-tabs .tab-btn[data-tab="personal"]');
            if (defaultTabButton) {
                switchTab(defaultTabButton);
            }
        }
    }

    // ================================
    // 6. Мобильное меню
    // ================================
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const mobileMenuContent = document.querySelector('.mobile-menu-content');

    if (mobileMenuBtn && mobileMenuContent) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenuContent.classList.toggle('active');
        });
        document.addEventListener('click', (e) => {
            if (!mobileMenuBtn.contains(e.target) && !mobileMenuContent.contains(e.target)) {
                mobileMenuContent.classList.remove('active');
            }
        });
    }

    // ================================
    // 7. Инициализация графиков (Statistics)
    // ================================
    function initializeCharts() {
        const activityChartCanvas = document.getElementById('activityChart');
        const categoriesChartCanvas = document.getElementById('categoriesChart');
        const scoresChartCanvas = document.getElementById('scoresChart');

        if (!activityChartCanvas || !categoriesChartCanvas || !scoresChartCanvas) return;

        // Предполагаем, что данные для графиков передаются через атрибуты data-*
        const activityDates = JSON.parse(activityChartCanvas.dataset.dates || '[]');
        const activityData = JSON.parse(activityChartCanvas.dataset.data || '[]');
        const categoriesLabels = JSON.parse(categoriesChartCanvas.dataset.labels || '[]');
        const categoriesData = JSON.parse(categoriesChartCanvas.dataset.data || '[]');
        const scoresDistribution = JSON.parse(scoresChartCanvas.dataset.distribution || '[]');

        Chart.defaults.color = '#fff';
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';

        new Chart(activityChartCanvas, {
            type: 'line',
            data: {
                labels: activityDates,
                datasets: [{
                    label: messages.solved_tasks,
                    data: activityData,
                    borderColor: '#f5a623',
                    backgroundColor: 'rgba(245, 166, 35, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        });

        new Chart(categoriesChartCanvas, {
            type: 'doughnut',
            data: {
                labels: categoriesLabels,
                datasets: [{
                    data: categoriesData,
                    backgroundColor: ['#f5a623', '#4a90e2', '#50e3c2', '#e54d42', '#b8e986']
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        new Chart(scoresChartCanvas, {
            type: 'bar',
            data: {
                labels: ['1-5', '6-10', '11-15', '16-20', '21-25'],
                datasets: [{
                    label: messages.task_count,
                    data: scoresDistribution,
                    backgroundColor: '#4a90e2'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        });
    }
});

/**
 * DEPRECATED: Вместо этой функции теперь используется alert()
 * Показывает уведомление в правом верхнем углу.
 * @param {string} message - Сообщение для уведомления.
 * @param {string} type - 'success' или 'error'.
 */
function showNotification(message, type = 'success') {
    // Этот код больше не используется, но оставлен для истории.
    // Мы перешли на alert() для максимальной надежности и устранения
    // ошибок "ReferenceError: showNotification is not defined".
    console.warn("showNotification is deprecated. Using alert() instead.", { message, type });
    alert(`${type.toUpperCase()}: ${message}`);

    /*
    const container = document.getElementById('notification-container');
    if (!container) {
        console.error('Notification container not found!');
        alert(message); // Fallback to alert
        return;
    }

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    container.appendChild(notification);

    // Показываем уведомление
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);

    // Скрываем и удаляем уведомление через 3 секунды
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            container.removeChild(notification);
        }, 500);
    }, 3000);
    */
}