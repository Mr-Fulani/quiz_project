/**
 * JavaScript модуль для управления профилем пользователя в Telegram Mini App
 */
document.addEventListener('DOMContentLoaded', function() {
    const tg = window.Telegram?.WebApp;
    if (tg) {
        tg.expand();
        tg.ready();
    }

    const loader = document.getElementById('loader');
    const profileContainer = document.getElementById('profile-container');
    const refreshBtn = document.getElementById('refresh-btn');
    const modal = document.getElementById('edit-modal');
    const editBtn = document.getElementById('edit-profile-btn');
    const closeBtn = document.querySelector('.close');
    const cancelBtn = document.querySelector('.btn-cancel');
    const editForm = document.getElementById('edit-profile-form');
    
    let currentUserData = null;
    let isLoading = false;

    function updateProfileDOM(userData) {
        currentUserData = userData;
        
        if (!userData) {
            console.error("No user data received");
            showError("Не удалось загрузить данные профиля.");
            return;
        }

        const fullName = `${userData.first_name || ''} ${userData.last_name || ''}`.trim();
        document.getElementById('profile-name').textContent = fullName || 'Пользователь';
        document.getElementById('profile-username').textContent = userData.username ? `@${userData.username}` : 'скрыт';
        
        updateAvatar(userData);
        
        document.getElementById('profile-points').textContent = userData.points || 0;
        document.getElementById('profile-rating').textContent = userData.rating || 0;
        document.getElementById('profile-quizzes').textContent = userData.quizzes_completed || 0;
        document.getElementById('profile-success').textContent = `${(userData.success_rate || 0).toFixed(1)}%`;

        updateProgress(userData.progress);
        updateSocialLinks(userData.social_links);

        hideLoader();
        profileContainer.style.display = 'block';
    }

    function updateAvatar(userData) {
        const avatarDiv = document.getElementById('profile-avatar');
        if (userData.avatar) {
            avatarDiv.innerHTML = `<img src="${userData.avatar}" alt="Avatar" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                                   <span style="display:none;">${(userData.first_name || 'U').charAt(0)}</span>`;
        } else {
            const initial = (userData.first_name || 'U').charAt(0);
            avatarDiv.innerHTML = `<span>${initial}</span>`;
            avatarDiv.style.backgroundColor = '#764ba2';
        }
    }

    function updateProgress(progressData) {
        const progressContainer = document.getElementById('progress-container');
        progressContainer.innerHTML = '';
        
        if (progressData && progressData.length > 0) {
            progressData.forEach(item => {
                const progressItem = document.createElement('div');
                progressItem.className = 'progress-item';
                progressItem.innerHTML = `
                    <div class="progress-info">
                        <div class="progress-topic">${item.topic_name}</div>
                        <div class="progress-details">${item.completed_quizzes} / ${item.total_quizzes} квизов</div>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${item.progress_percentage}%;"></div>
                    </div>
                `;
                progressContainer.appendChild(progressItem);
            });
        } else {
            progressContainer.innerHTML = '<p>Нет данных о прогрессе.</p>';
        }
    }

    function updateSocialLinks(socialLinks) {
        const socialContainer = document.getElementById('social-links-container');
        socialContainer.innerHTML = '';
        
        if (socialLinks && socialLinks.length > 0) {
            socialLinks.forEach(link => {
                const socialItem = document.createElement('a');
                socialItem.className = 'social-link-card';
                socialItem.href = link.url;
                socialItem.target = '_blank';
                socialItem.innerHTML = `
                    <div class="social-icon">${link.icon}</div>
                    <div class="social-info">
                        <div class="social-name">${link.name}</div>
                        <div class="social-url">${link.url}</div>
                    </div>
                `;
                socialContainer.appendChild(socialItem);
            });
        } else {
            socialContainer.innerHTML = '<p class="social-empty">Социальные сети не указаны.</p>';
        }
    }

    function showLoader() {
        if (loader) {
            loader.style.display = 'flex';
            loader.innerHTML = '<div class="spinner"></div><p>Загрузка профиля...</p>';
        }
        if (profileContainer) {
            profileContainer.style.display = 'none';
        }
    }

    function hideLoader() {
        if (loader) {
            loader.style.display = 'none';
        }
    }

    function showError(message) {
        hideLoader();
        if (loader) {
            loader.style.display = 'flex';
            loader.innerHTML = `<p style="color: #ff6b6b;">${message}</p>`;
        }
    }

    async function fetchProfileData() {
        if (isLoading) return;
        
        isLoading = true;
        showLoader();

        try {
            if (!tg || !tg.initData) {
                console.warn("Telegram WebApp не доступен");
                await loadProfileByTelegramId(123456);
                return;
            }

            await sendInitData(tg.initData);
        } catch (error) {
            console.error('Error in fetchProfileData:', error);
            showError(`Ошибка при загрузке: ${error.message}`);
        } finally {
            isLoading = false;
        }
    }

    async function loadProfileByTelegramId(telegramId) {
        try {
            const response = await fetch(`/api/profile/by-telegram/${telegramId}/`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            updateProfileDOM(data);
        } catch (error) {
            console.error('Error loading profile:', error);
            showError(`Ошибка при загрузке профиля: ${error.message}`);
        }
    }

    async function sendInitData(initData) {
        try {
            const response = await fetch('/api/profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ initData: initData })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            updateProfileDOM(data);
        } catch (error) {
            console.error('Error sending init data:', error);
            showError(`Ошибка аутентификации: ${error.message}`);
        }
    }

    function fillEditForm() {
        if (!currentUserData) return;

        editForm.reset();
        document.getElementById('avatar-preview').innerHTML = '';

        if (currentUserData.social_links) {
            const fieldMap = {
                'Веб-сайт': 'website-input',
                'Telegram': 'telegram-input',
                'GitHub': 'github-input',
                'LinkedIn': 'linkedin-input',
                'Instagram': 'instagram-input',
                'Facebook': 'facebook-input',
                'YouTube': 'youtube-input'
            };
            
            currentUserData.social_links.forEach(link => {
                const inputId = fieldMap[link.name];
                if (inputId) {
                    const input = document.getElementById(inputId);
                    if (input) {
                        if (link.name === 'Telegram' && link.url.startsWith('https://t.me/')) {
                            input.value = link.url.replace('https://t.me/', '');
                        } else {
                            input.value = link.url;
                        }
                    }
                }
            });
        }
    }

    async function updateProfile(formData) {
        try {
            const telegramId = tg?.initDataUnsafe?.user?.id || 123456;
            
            const response = await fetch(`/api/profile/${telegramId}/update/`, {
                method: 'PATCH',
                body: formData
            });
            
            if (response.ok) {
                const updatedData = await response.json();
                updateProfileDOM(updatedData);
                closeModal();
                showNotification('Профиль успешно обновлен!', 'success');
            } else {
                const errorData = await response.json();
                showNotification('Ошибка: ' + (errorData.error || 'Неизвестная ошибка'), 'error');
            }
        } catch (error) {
            console.error('Error updating profile:', error);
            showNotification('Ошибка при обновлении профиля', 'error');
        }
    }

    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            left: 20px;
            right: 20px;
            margin: 0 auto;
            max-width: 400px;
            padding: 15px 20px;
            border-radius: 12px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            background: ${type === 'success' ? '#22c55e' : type === 'error' ? '#ef4444' : '#3b82f6'};
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => {
                if (document.body.contains(notification)) {
                    document.body.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    function openModal() {
        if (modal) {
            modal.style.display = 'block';
            document.body.style.overflow = 'hidden';
            fillEditForm();
        }
    }

    function closeModal() {
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    // Event Listeners
    if (refreshBtn) refreshBtn.addEventListener('click', fetchProfileData);
    if (editBtn) editBtn.addEventListener('click', openModal);
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

    if (modal) {
        modal.addEventListener('click', function(event) {
            if (event.target === modal) closeModal();
        });
    }

    const avatarInput = document.getElementById('avatar-input');
    if (avatarInput) {
        avatarInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            const preview = document.getElementById('avatar-preview');
            
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.innerHTML = `<img src="${e.target.result}" alt="Preview" style="max-width: 100px; max-height: 100px; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.3);">`;
                };
                reader.readAsDataURL(file);
            } else {
                preview.innerHTML = '';
            }
        });
    }

    if (editForm) {
        editForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData();
            
            const avatarFile = document.getElementById('avatar-input').files[0];
            if (avatarFile) {
                formData.append('avatar', avatarFile);
            }
            
            const socialFields = [
                'website-input', 'telegram-input', 'github-input', 
                'linkedin-input', 'instagram-input', 'facebook-input', 'youtube-input'
            ];
            
            socialFields.forEach(fieldId => {
                const input = document.getElementById(fieldId);
                if (input && input.value.trim()) {
                    const fieldName = fieldId.replace('-input', '');
                    formData.append(fieldName, input.value.trim());
                }
            });
            
            updateProfile(formData);
        });
    }

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal && modal.style.display === 'block') {
            closeModal();
        }
    });

    // Инициализация
    fetchProfileData();
});
