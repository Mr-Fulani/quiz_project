document.addEventListener('DOMContentLoaded', function () {
    // ================================
    // 1. Переключение вкладок (Tabs)
    // ================================
    const tabs = document.querySelectorAll('.tab-btn');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Убираем класс active у всех кнопок и блоков
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));

            // Добавляем класс active для выбранной кнопки и соответствующего контента
            tab.classList.add('active');
            document.querySelector(`[data-tab-content="${tab.dataset.tab}"]`).classList.add('active');
        });
    });

    // ================================
    // 2. Avatar upload (загрузка аватара)
    // ================================
    const avatarUpload = document.getElementById('avatar-form');
    if (avatarUpload) {
        avatarUpload.addEventListener('change', function () {
            this.submit();
        });
    }

    // ================================
    // 3. Обработка настроек
    // ================================
    const settingsToggles = document.querySelectorAll('.settings-list input[type="checkbox"]');
    settingsToggles.forEach(toggle => {
        toggle.addEventListener('change', async function () {
            try {
                const response = await fetch('{% url "accounts:update_settings" %}', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': '{{ csrf_token }}'
                    },
                    body: JSON.stringify({
                        setting: this.name,
                        value: this.checked
                    })
                });
                if (!response.ok) throw new Error('Settings update failed');
            } catch (error) {
                console.error('Error:', error);
                this.checked = !this.checked; // Возвращаем переключатель в исходное состояние при ошибке
            }
        });
    });

    // ===============================================
    // 4. Переключение между входящими и отправленными
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
    // 5. Показать/скрыть форму сообщения
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
    // 6. Удаление сообщений
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
    // 7. Обработка выбора файлов для вложений
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
                    // Создаем новый FileList без удаленного файла
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
    // 8. Отправка формы сообщения
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
                    // Очищаем форму
                    this.reset();
                    selectedFilesContainer.innerHTML = '';
                    // Скрываем форму
                    this.style.display = 'none';
                    document.getElementById('showMessageForm').style.display = 'block';
                    // Показываем уведомление
                    showNotification('Message sent successfully!', 'success');
                }
            } catch (error) {
                console.error('Error sending message:', error);
                showNotification('Failed to send message', 'error');
            }
        });
    }

    // ===============================================
    // 9. Обработка параметра URL "tab" для переключения вкладок
    // ===============================================
    const urlParams = new URLSearchParams(window.location.search);
    const activeTab = urlParams.get('tab');

    if (activeTab) {
        // Ищем кнопку вкладки, у которой data-tab равен значению параметра
        const tabButton = document.querySelector(`.profile-tabs .tab-btn[data-tab="${activeTab}"]`);
        if (tabButton) {
            // Имитируем клик для переключения вкладки
            tabButton.click();
        }
    }
});