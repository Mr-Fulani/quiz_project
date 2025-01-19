document.addEventListener('DOMContentLoaded', function() {
    const profileForm = document.getElementById('profile-settings-form');
    
    if (profileForm) {
        profileForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const telegramId = document.querySelector('.page-wrapper').getAttribute('data-telegram-id');
            
            fetch(`/profile/${telegramId}/update/`, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Обновляем все изображения аватара на странице
                    const avatarImages = document.querySelectorAll('.avatar-wrapper img');
                    avatarImages.forEach(img => {
                        img.src = data.avatar_url + '?t=' + new Date().getTime();
                    });
                    
                    // Обновляем превью в форме настроек
                    const settingsPreview = document.querySelector('.settings-preview');
                    if (settingsPreview) {
                        settingsPreview.src = data.avatar_url + '?t=' + new Date().getTime();
                    }
                    
                    // Показываем сообщение об успехе
                    showNotification('success', 'Профиль успешно обновлен');
                    
                    // Обновляем секцию профиля
                    const profileSection = document.querySelector('[data-section="profile"]');
                    if (profileSection) {
                        profileSection.click();
                    }
                } else {
                    showNotification('error', data.message || 'Произошла ошибка');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('error', 'Произошла ошибка при обновлении профиля');
            });
        });
    }
});

function showNotification(type, message) {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'success' ? 'success' : 'danger'} notification`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Анимация появления
    setTimeout(() => notification.classList.add('show'), 100);
    
    // Автоматическое скрытие через 3 секунды
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
} 