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
    
    // Очищаем предыдущие ошибки
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
            // Показываем ошибки под каждым полем
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
            // Успешная смена пароля
            showNotification('Password changed successfully!', 'success');
            this.reset(); // Очищаем форму
            
            // Добавляем зеленую подсветку полей на короткое время
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

    // Автоматическая отправка формы при выборе нового аватара
    const avatarInput = document.getElementById('id_avatar');
    const avatarForm = document.getElementById('avatar-form');
    const avatarImg = document.querySelector('.avatar-img');

    if (avatarInput && avatarForm) {
        avatarInput.addEventListener('change', function(e) {
            console.log('File selected:', this.files[0]); // Отладочный вывод
            avatarForm.submit();
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
                            'Accept-Language': 'ru', // Добавим русский язык
                            'User-Agent': 'YourApp' // Требуется для API
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

        // Обработка выбора локации
        suggestions.addEventListener('click', (e) => {
            const item = e.target.closest('.location-item');
            if (item) {
                locationInput.value = item.dataset.location;
                suggestions.style.display = 'none';
            }
        });

        // Скрываем подсказки при клике вне
        document.addEventListener('click', (e) => {
            if (!locationInput.contains(e.target) && !suggestions.contains(e.target)) {
                suggestions.style.display = 'none';
            }
        });
    }

    // Анимация для активной вкладки
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            tabButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
        });
    });
});
// Вспомогательные функции
function showNotification(message, type = 'success') {
    // Удаляем предыдущие уведомления
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
    
    // Анимация появления
    setTimeout(() => notification.classList.add('show'), 100);
    
    // Автоматическое скрытие через 3 секунды
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Добавим функцию для генерации URL профиля
function getProfileUrl(username) {
    return `/profile/${username}/`;
}

// Вспомогательная функция debounce
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
