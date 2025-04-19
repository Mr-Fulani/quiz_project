/**
 * JavaScript для dashboard: вкладки, аватар, настройки, сообщения, вложения, мобильное меню.
 */
document.addEventListener('DOMContentLoaded', function () {
    // ================================
    // 1. Переключение вкладок (Tabs)
    // ================================
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
    if (personalInfoForm) {
        personalInfoForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const formData = new FormData(this);
            try {
                const response = await fetch(this.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    }
                });
                if (response.ok) {
                    showNotification('Profile updated successfully!', 'success');
                    const dashboardUrl = document.querySelector('.profile').dataset.dashboardUrl;
                    window.location.href = dashboardUrl;
                } else {
                    const data = await response.json();
                    showNotification(data.message || 'Failed to update profile', 'error');
                }
            } catch (error) {
                console.error('Error updating profile:', error);
                showNotification('Failed to update profile', 'error');
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

    // ===============================================
    // 5. Переключение между входящими и отправленными
    // ===============================================
    const filterBtns = document.querySelectorAll('.filter-btn');
    const messageLists = document.querySelectorAll('.messages-list');

    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            messageLists.forEach(l => l.classList.remove('active'));
            btn.classList.add('active');
            document.querySelector(`[data-messages="${btn.dataset.filter}"]`).classList.add('active');
        });
    });

    // ===============================================
    // 6. Показать/скрыть форму сообщения
    // ===============================================
    const showMessageBtn = document.getElementById('showMessageForm');
    const messageForm = document.getElementById('messageForm');
    const cancelBtn = document.getElementById('cancelMessage');

    if (showMessageBtn && messageForm && cancelBtn) {
        showMessageBtn.addEventListener('click', () => {
            messageForm.style.display = 'block';
            showMessageBtn.style.display = 'none';
        });

        cancelBtn.addEventListener('click', () => {
            messageForm.style.display = 'none';
            showMessageBtn.style.display = 'block';
        });
    }

    // ===============================================
    // 7. Удаление сообщений
    // ===============================================
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to delete this message?')) {
                const messageId = btn.dataset.messageId;
                try {
                    const response = await fetch(`/messages/delete/${messageId}/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                        }
                    });
                    if (response.ok) {
                        btn.closest('.message-item').remove();
                    }
                } catch (error) {
                    console.error('Error deleting message:', error);
                }
            }
        });
    });

    // ===============================================
    // 8. Обработка выбора файлов для вложений
    // ===============================================
    const attachmentsInput = document.getElementById('attachments');
    const selectedFilesContainer = document.getElementById('selected-files');

    if (attachmentsInput) {
        attachmentsInput.addEventListener('change', function () {
            selectedFilesContainer.innerHTML = '';
            Array.from(this.files).forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.innerHTML = `
                    <span class="file-name">${file.name}</span>
                    <ion-icon name="close-outline" class="remove-file"></ion-icon>
                `;
                fileItem.querySelector('.remove-file').addEventListener('click', function () {
                    fileItem.remove();
                    const dt = new DataTransfer();
                    Array.from(attachmentsInput.files)
                        .filter(f => f.name !== file.name)
                        .forEach(f => dt.items.add(f));
                    attachmentsInput.files = dt.files;
                });
                selectedFilesContainer.appendChild(fileItem);
            });
        });
    }

    // ===============================================
    // 9. Отправка формы сообщения
    // ===============================================
    if (messageForm) {
        messageForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const formData = new FormData(this);
            try {
                const response = await fetch(this.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    }
                });
                const data = await response.json();
                if (data.status === 'sent') {
                    this.reset();
                    selectedFilesContainer.innerHTML = '';
                    this.style.display = 'none';
                    document.getElementById('showMessageForm').style.display = 'block';
                    showNotification('Message sent successfully!', 'success');
                }
            } catch (error) {
                console.error('Error sending message:', error);
                showNotification('Failed to send message', 'error');
            }
        });
    }

    // ===============================================
    // 10. Обработка параметра URL "tab" для переключения вкладок
    // ===============================================
    const urlParams = new URLSearchParams(window.location.search);
    const activeTab = urlParams.get('tab');
    if (activeTab) {
        const tabButton = document.querySelector(`.profile-tabs .tab-btn[data-tab="${activeTab}"]`);
        if (tabButton) {
            tabButton.click();
        }
    }

    // ================================
    // 11. Мобильное меню
    // ================================
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const mobileMenuContent = document.querySelector('.mobile-menu-content');
    const mobileTabs = document.querySelectorAll('.mobile-tab-btn');

    if (mobileMenuBtn && mobileMenuContent) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenuContent.classList.toggle('active');
        });
        mobileTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                if (!tab.href) {
                    tabs.forEach(t => t.classList.remove('active'));
                    contents.forEach(c => c.classList.remove('active'));
                    mobileTabs.forEach(mt => mt.classList.remove('active'));
                    tab.classList.add('active');
                    document.querySelector(`[data-tab-content="${tab.dataset.tab}"]`).classList.add('active');
                    mobileMenuContent.classList.remove('active');
                }
            });
        });
        document.addEventListener('click', (e) => {
            if (!mobileMenuBtn.contains(e.target) && !mobileMenuContent.contains(e.target)) {
                mobileMenuContent.classList.remove('active');
            }
        });
    }

    // ===============================================
    // 12. Функция для показа уведомлений
    // ===============================================
    function showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
});