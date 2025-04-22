/**
 * JavaScript для профиля: переключение вкладок, обработка форм, автозаполнение локации, смена пароля, отправка сообщений.
 */
document.addEventListener('DOMContentLoaded', function() {
    /**
     * Показывает ошибки формы под соответствующими полями.
     * @param {HTMLFormElement} form - Форма.
     * @param {Object} errors - Объект с ошибками.
     */
    function showFormErrors(form, errors) {
        form.querySelectorAll('.error-message').forEach(el => el.remove());
        Object.entries(errors).forEach(([field, messages]) => {
            const input = form.querySelector(`[name="${field}"]`);
            if (input) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error-message';
                errorDiv.textContent = messages.join(', ');
                input.parentNode.insertBefore(errorDiv, input.nextSibling);
                input.classList.add('error');
            }
        });
    }

    /**
     * Показывает уведомление с сообщением.
     * @param {string} message - Текст уведомления.
     * @param {string} type - Тип уведомления ('success' или 'error').
     */
    function showNotification(message, type = 'success') {
        document.querySelectorAll('.notification').forEach(n => n.remove());
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <ion-icon name="${type === 'success' ? 'checkmark-circle' : 'alert-circle'}"></ion-icon>
                <span>${message}</span>
            </div>
        `;
        document.body.appendChild(notification);
        setTimeout(() => notification.classList.add('show'), 100);
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    /**
     * Debounce-функция для задержки выполнения.
     * @param {Function} func - Функция для выполнения.
     * @param {number} wait - Задержка в миллисекундах.
     * @returns {Function} Обёрнутая функция.
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Инициализация вкладок при загрузке
    function initializeTabs() {
        console.log('Initializing tabs...');
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.querySelector('.tab-content[data-tab-content="info"]').classList.add('active');
    }

    // Переключение вкладок
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            console.log(`Switching to tab: ${tabName}`);

            // Удаляем класс active у всех кнопок и контента
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

            // Добавляем класс active текущей кнопке и контенту
            this.classList.add('active');
            document.querySelector(`.tab-content[data-tab-content="${tabName}"]`).classList.add('active');
        });
    });

    // Вызываем инициализацию вкладок
    initializeTabs();

    // Обработка загрузки файлов
    const fileInput = document.getElementById('attachments');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            const container = document.getElementById('selected-files');
            container.innerHTML = '';
            Array.from(this.files).forEach(file => {
                const fileDiv = document.createElement('div');
                fileDiv.className = 'selected-file';
                fileDiv.innerHTML = `
                    <span class="filename">${file.name}</span>
                    <ion-icon name="close-outline" class="remove-file" onclick="removeFile(this)"></ion-icon>
                `;
                container.appendChild(fileDiv);
            });
        });
    }

    // Удаление файла из списка
    window.removeFile = function(element) {
        const fileInput = document.getElementById('attachments');
        const dt = new DataTransfer();
        const files = fileInput.files;
        const fileName = element.previousElementSibling.textContent;

        for (let i = 0; i < files.length; i++) {
            if (files[i].name !== fileName) {
                dt.items.add(files[i]);
            }
        }

        fileInput.files = dt.files;
        element.parentElement.remove();
    };

    // Асинхронная отправка формы сообщения
    const messageForm = document.querySelector('.message-form form');
    if (messageForm) {
        messageForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            document.querySelectorAll('.message-notification').forEach(note => note.remove());

            const formData = new FormData(this);

            try {
                const response = await fetch(this.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    credentials: 'same-origin'
                });

                const data = await response.json();

                if (data.status === 'sent') {
                    showNotification('Message sent successfully!', 'success');
                    this.reset();
                    document.getElementById('selected-files').innerHTML = '';
                } else {
                    if (data.errors) {
                        showFormErrors(this, data.errors);
                    }
                    showNotification(data.message || 'Error sending message. Please try again.', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showNotification('Error sending message. Please try again.', 'error');
            }
        });
    }

    // Обработка ссылок на профиль
    document.querySelectorAll('[data-profile-link]').forEach(link => {
        link.addEventListener('click', function(e) {
            const username = this.dataset.username;
            const href = this.href;
            if (username || (href && href !== '#' && !href.includes('login'))) {
                return;
            }
            e.preventDefault();
            const loginUrl = window.loginUrl || '/?open_login=true';
            window.location.href = `${loginUrl}?next=${encodeURIComponent(window.location.pathname)}`;
        });
    });

    // Автозаполнение локации
    const locationInput = document.querySelector('.location-input');
    const suggestions = document.querySelector('.location-suggestions');

    if (locationInput && suggestions) {
        locationInput.addEventListener('input', debounce(async (e) => {
            const query = e.target.value;
            if (query.length < 3) {
                suggestions.style.display = 'none';
                return;
            }

            try {
                const response = await fetch(
                    `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`,
                    {
                        headers: {
                            'Accept-Language': 'ru',
                            'User-Agent': 'YourApp'
                        }
                    }
                );
                const data = await response.json();

                if (data.length > 0) {
                    suggestions.innerHTML = data
                        .slice(0, 5)
                        .map(place => `
                            <div class="location-item" data-location="${place.display_name}">
                                ${place.display_name}
                            </div>
                        `)
                        .join('');
                    suggestions.style.display = 'block';
                } else {
                    suggestions.style.display = 'none';
                }
            } catch (error) {
                console.error('Error fetching locations:', error);
            }
        }, 300));

        suggestions.addEventListener('click', (e) => {
            const item = e.target.closest('.location-item');
            if (item) {
                locationInput.value = item.dataset.location;
                suggestions.style.display = 'none';
            }
        });

        document.addEventListener('click', (e) => {
            if (!locationInput.contains(e.target) && !suggestions.contains(e.target)) {
                suggestions.style.display = 'none';
            }
        });
    }

    // Обработчик отправки формы смены пароля
    document.querySelector('form[action*="change-password"]')?.addEventListener('submit', async function(e) {
        e.preventDefault();
        this.querySelectorAll('.error-message').forEach(el => el.remove());

        try {
            const response = await fetch(this.action, {
                method: 'POST',
                body: new FormData(this),
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });

            const data = await response.json();

            if (!response.ok) {
                Object.entries(data.errors).forEach(([field, messages]) => {
                    const input = this.querySelector(`[name="${field}"]`);
                    if (input) {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'error-message';
                        errorDiv.textContent = messages.join(', ');
                        input.parentNode.insertBefore(errorDiv, input.nextSibling);
                        input.classList.add('error');
                    }
                });
            } else {
                showNotification('Password changed successfully!', 'success');
                this.reset();
                this.querySelectorAll('input').forEach(input => {
                    input.classList.add('success');
                    setTimeout(() => input.classList.remove('success'), 2000);
                });
            }
        } catch (error) {
            console.error('Error:', error);
            showNotification('Failed to change password. Please try again.', 'error');
        }
    });
});