document.addEventListener('DOMContentLoaded', function() {
    const profileForm = document.getElementById('profile-settings-form');
    
    if (profileForm) {
        profileForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const telegramId = document.querySelector('.page-wrapper').getAttribute('data-telegram-id');
            
            fetch(`/users/profile/${telegramId}/update/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Обновляем все изображения аватара на странице
                    const avatarImages = document.querySelectorAll('.avatar-wrapper img');
                    avatarImages.forEach(img => {
                        img.src = data.avatar_url;
                    });
                    
                    // Обновляем превью в форме настроек
                    const settingsPreview = document.querySelector('#profile-settings-form img');
                    if (settingsPreview) {
                        settingsPreview.src = data.avatar_url;
                    }
                    
                    // Показываем сообщение об успехе
                    alert('Профиль успешно обновлен');
                    
                    // Обновляем секцию профиля
                    const section = document.querySelector('[data-section="profile"]');
                    if (section) {
                        section.click();
                    }
                } else {
                    alert('Ошибка: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Произошла ошибка при обновлении профиля');
            });
        });
    }
}); 