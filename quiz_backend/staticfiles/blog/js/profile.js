// Функция для отображения ошибок формы
function showFormErrors(form, errors) {
    // Очищаем предыдущие ошибки
    form.querySelectorAll('.error-message').forEach(el => el.remove());
    
    // Добавляем новые ошибки
    Object.entries(errors).forEach(([field, messages]) => {
        const input = form.querySelector(`[name="${field}"]`);
        if (input) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = messages.join(', ');
            input.parentNode.insertBefore(errorDiv, input.nextSibling);
        }
    });
}

// Обработчик отправки формы смены пароля
document.querySelector('form[action*="change-password"]')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
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
            showFormErrors(this, data.errors);
        } else {
            // Перезагружаем страницу при успешной смене пароля
            window.location.reload();
        }
    } catch (error) {
        console.error('Error:', error);
    }
});

document.addEventListener('DOMContentLoaded', function() {
    // Обработка переключения табов
    const tabs = document.querySelectorAll('.tab-btn');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.querySelector(`[data-tab-content="${tab.dataset.tab}"]`).classList.add('active');
        });
    });

    // Обработка загрузки аватара
    const avatarUpload = document.getElementById('avatar-upload');
    if (avatarUpload) {
        avatarUpload.addEventListener('change', function() {
            this.form.submit();
        });
    }

    // Обработка настроек профиля
    const settingsToggles = document.querySelectorAll('.settings-list input[type="checkbox"]');
    settingsToggles.forEach(toggle => {
        toggle.addEventListener('change', async function() {
            try {
                const response = await fetch('/profile/update-settings/', {
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

                if (!response.ok) {
                    throw new Error('Settings update failed');
                }

                // Показываем уведомление об успехе
                showNotification('Settings updated successfully!', 'success');
            } catch (error) {
                console.error('Error:', error);
                // Возвращаем переключатель в предыдущее состояние
                this.checked = !this.checked;
                showNotification('Failed to update settings', 'error');
            }
        });
    });

    // Обработка формы смены пароля
    const passwordForm = document.querySelector('form[action*="change-password"]');
    if (passwordForm) {
        passwordForm.addEventListener('submit', async function(e) {
            e.preventDefault();
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
                    showFormErrors(this, data.errors);
                } else {
                    showNotification('Password changed successfully!', 'success');
                    this.reset();
                }
            } catch (error) {
                console.error('Error:', error);
                showNotification('Failed to change password', 'error');
            }
        });
    }

    // Обработка ссылок на профиль
    document.querySelectorAll('[data-profile-link]').forEach(link => {
        link.addEventListener('click', function(e) {
            const username = this.dataset.username;
            if (!username) {
                e.preventDefault();
                window.location.href = '{% url "login" %}?next=' + window.location.pathname;
            }
        });
    });
});

// Вспомогательные функции
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `message ${type}`;
    notification.textContent = message;

    const container = document.querySelector('.profile-content');
    container.insertBefore(notification, container.firstChild);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Добавим функцию для генерации URL профиля
function getProfileUrl(username) {
    return `/profile/${username}/`;
} 