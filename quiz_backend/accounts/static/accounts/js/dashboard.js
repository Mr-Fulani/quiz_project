/**
 * JavaScript для dashboard: вкладки, аватар, настройки, мобильное меню.
 */
document.addEventListener('DOMContentLoaded', function () {
    // ================================
    // 1. Переключение вкладок (Tabs)
    // ================================
    const tabs = document.querySelectorAll('.tab-btn');
    const mobileTabs = document.querySelectorAll('.mobile-tab-btn');
    const contents = document.querySelectorAll('.tab-content');

    /**
     * Переключает вкладки и загружает содержимое через AJAX, если есть data-url.
     * @param {HTMLElement} tab - Кнопка вкладки.
     * @param {boolean} isMobile - Флаг мобильного меню.
     */
    function switchTab(tab, isMobile = false) {
        // Удаляем класс active у всех вкладок и контента
        tabs.forEach(t => t.classList.remove('active'));
        mobileTabs.forEach(mt => mt.classList.remove('active'));
        contents.forEach(c => c.classList.remove('active'));

        // Добавляем класс active для текущей вкладки
        tab.classList.add('active');
        const tabId = tab.dataset.tab;
        const content = document.querySelector(`[data-tab-content="${tabId}"]`);
        content.classList.add('active');

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
                    showNotification('Failed to load content', 'error');
                });
            }
        }

        // Закрываем мобильное меню, если это мобильная вкладка
        if (isMobile) {
            document.querySelector('.mobile-menu-content').classList.remove('active');
        }
    }

    // Переключение вкладок для десктопных кнопок
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            switchTab(tab);
        });
    });

    // Переключение вкладок для мобильных кнопок
    mobileTabs.forEach(tab => {
        tab.addEventListener('click', () => {
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
                const data = await response.json();
                if (response.ok && data.status === 'success') {
                    showNotification('Avatar updated successfully!', 'success');
                    const avatarImg = document.querySelector('.profile-avatar img');
                    avatarImg.src = data.avatar_url;
                } else {
                    showNotification(data.message || 'Failed to update avatar', 'error');
                }
            } catch (error) {
                console.error('Error uploading avatar:', error);
                showNotification('Failed to update avatar', 'error');
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
                    showNotification('Профиль успешно обновлён!', 'success');
                    const dashboardUrl = document.querySelector('.profile').dataset.dashboardUrl || '/users/dashboard/';
                    window.location.href = dashboardUrl;
                } else {
                    showNotification(data.message || 'Не удалось обновить профиль', 'error');
                }
            } catch (error) {
                console.error('Personal info form submission error:', error);
                showNotification('Не удалось обновить профиль', 'error');
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
                    showNotification('Пароль успешно изменён!', 'success');

                    // Создаем элемент для успешного сообщения
                    const successElement = document.createElement('div');
                    successElement.className = 'success';
                    successElement.textContent = 'Пароль успешно изменён!';
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
                        for (const [field, errorList] of Object.entries(errors)) {
                            const input = document.querySelector(`#id_${field}`);
                            if (input) {
                                const errorDiv = document.createElement('div');
                                errorDiv.className = 'error';
                                errorDiv.textContent = errorList.map(e => e.message).join(' ');
                                input.parentNode.appendChild(errorDiv);
                            }
                        }
                    }
                    showNotification(data.message || 'Не удалось сменить пароль', 'error');
                }
            } catch (error) {
                console.error('Security form submission error:', error);
                showNotification('Не удалось сменить пароль', 'error');
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
                const response = await fetch('/users/settings/update/', {
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
                showNotification('Settings updated successfully!', 'success');
            } catch (error) {
                console.error('Error:', error);
                this.checked = !this.checked;
                showNotification('Failed to update settings', 'error');
            }
        });
    });

    // ================================
    // 5. Обработка параметра URL "tab" для переключения вкладок
    // ================================
    // Исправленная обработка параметра URL "tab" (строки ~290-310)
    const urlParams = new URLSearchParams(window.location.search);
    const activeTab = urlParams.get('tab');
    if (activeTab) {
        const tabButton = document.querySelector(`.profile-tabs .tab-btn[data-tab="${activeTab}"]`);
        if (tabButton) {
            switchTab(tabButton);
        }
    } else {
        // Проверяем, есть ли уже активная вкладка в HTML
        const alreadyActiveTab = document.querySelector('.tab-btn.active');
        if (!alreadyActiveTab) {
            // Только если нет активной вкладки, активируем Personal Info по умолчанию
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
    // 7. Функция для показа уведомлений
    // ================================
    function showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.position = 'fixed';
        notification.style.top = '20px';
        notification.style.right = '20px';
        notification.style.padding = '15px 25px';
        notification.style.borderRadius = '8px';
        notification.style.color = 'white';
        notification.style.fontSize = '14px';
        notification.style.zIndex = '1000';
        notification.style.boxShadow = '0 2px 5px rgba(0, 0, 0, 0.2)';
        notification.style.transform = 'translateX(120%)';
        notification.style.transition = 'transform 0.3s ease';

        if (type === 'success') {
            notification.style.backgroundColor = '#4CAF50';
        } else if (type === 'error') {
            notification.style.backgroundColor = '#f44336';
        }

        document.body.appendChild(notification);

        // Показываем уведомление
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);

        // Удаляем уведомление через 3 секунды
        setTimeout(() => {
            notification.style.transform = 'translateX(120%)';
            setTimeout(() => {
                if (notification && notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        }, 3000);
    }

    // ================================
    // 8. Инициализация графиков (Statistics)
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
                    label: 'Решено задач',
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
                    label: 'Количество задач',
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