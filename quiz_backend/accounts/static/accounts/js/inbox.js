document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const recipientInput = document.getElementById('recipient-username');
    const attachmentsInput = document.getElementById('chat-attachments');
    const selectedFilesContainer = document.getElementById('selected-files');
    const dialogsList = document.querySelector('.dialogs-list');
    const chatWindow = document.querySelector('.chat-window');
    let currentUsername = null;

    // Функция показа уведомлений
    function showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `message-notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    // Отображение выбранных файлов
    attachmentsInput.addEventListener('change', function() {
        selectedFilesContainer.innerHTML = '';
        Array.from(this.files).forEach(file => {
            const fileElement = document.createElement('div');
            fileElement.className = 'selected-file';
            fileElement.innerHTML = `
                <span>${file.name}</span>
                <button type="button" class="remove-file">
                    <ion-icon name="close-outline"></ion-icon>
                </button>
            `;
            fileElement.querySelector('.remove-file').addEventListener('click', () => {
                fileElement.remove();
                const dataTransfer = new DataTransfer();
                Array.from(attachmentsInput.files)
                    .filter(f => f.name !== file.name)
                    .forEach(f => dataTransfer.items.add(f));
                attachmentsInput.files = dataTransfer.files;
            });
            selectedFilesContainer.appendChild(fileElement);
        });
    });

    // Функция загрузки диалога
    window.loadConversation = function(username) {
        console.log('Загрузка диалога:', username);
        currentUsername = username;
        recipientInput.value = username;
        document.getElementById('chat-recipient').textContent = username;

        // Обнуляем счётчик непрочитанных
        const dialogItem = document.querySelector(`.dialog-item[data-username="${username}"]`);
        const unreadCount = dialogItem ? dialogItem.querySelector('.unread-count') : null;
        if (unreadCount) {
            unreadCount.remove();
        }

        // Переключение для мобильных
        if (window.innerWidth <= 768) {
            console.log('Мобильный режим: показываем чат');
            dialogsList.classList.remove('active');
            chatWindow.classList.add('active');
            chatWindow.style.display = 'flex';
        }

        fetch(`/messages/conversation/${username}/`, {
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Ошибка загрузки диалога: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            chatMessages.innerHTML = '';
            console.log('Данные диалога:', data);
            data.messages.forEach(message => {
                console.log(`Сообщение ${message.id}, вложения:`, message.attachments);
                const messageElement = document.createElement('div');
                messageElement.className = `message-item ${message.is_sent_by_user ? 'sent' : 'received'}`;
                messageElement.dataset.messageId = message.id;
                messageElement.innerHTML = `
                    <div class="message-content">${message.content.replace(/\n/g, '<br>')}</div>
                    <div class="message-meta">${message.created_at}</div>
                    ${message.attachments.length > 0 ? `
                        <div class="message-attachments">
                            <h4>Вложения:</h4>
                            <div class="attachments-grid">
                                ${message.attachments.map(att => {
                                    console.log(`Рендеринг вложения: ${att.filename}, URL: ${att.url}`);
                                    return `
                                        <div class="attachment-item">
                                            ${att.is_image ? `
                                                <div class="attachment-preview">
                                                    <img src="${att.url}" alt="${att.filename}"
                                                         onclick="openImagePreview('${att.url}', '${att.filename}')">
                                                </div>
                                            ` : `
                                                <div class="attachment-icon">
                                                    <ion-icon name="${att.filename.endsWith('.pdf') ? 'document-text-outline' :
                                                        att.filename.match(/\.(doc|docx)$/) ? 'document-outline' :
                                                        att.filename.match(/\.(xls|xlsx)$/) ? 'grid-outline' :
                                                        'document-attach-outline'}"></ion-icon>
                                                </div>
                                            `}
                                            <a href="/messages/attachment/${att.id}/" class="attachment-download"
                                               ${!att.is_image ? 'download' : ''}>
                                                <span class="filename">${att.filename}</span>
                                                <ion-icon name="download-outline"></ion-icon>
                                            </a>
                                        </div>
                                    `;
                                }).join('')}
                            </div>
                        </div>
                    ` : ''}
                    <div class="message-actions">
                        <button class="delete-btn" data-message-id="${message.id}">
                            <ion-icon name="trash-outline"></ion-icon>
                        </button>
                    </div>
                `;
                chatMessages.appendChild(messageElement);
            });
            chatMessages.scrollTop = chatMessages.scrollHeight;
        })
        .catch(error => {
            console.error('Ошибка загрузки диалога:', error);
            showNotification('Ошибка загрузки диалога.', 'error');
        });
    };

    // Обработка отправки формы
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        console.log('Отправка формы, currentUsername:', currentUsername);

        if (!recipientInput.value) {
            console.log('Ошибка: получатель не выбран');
            showNotification('Выберите диалог для отправки сообщения.', 'error');
            return;
        }

        const submitButton = chatForm.querySelector('.send-btn');
        if (!submitButton) {
            console.error('Кнопка отправки не найдена');
            showNotification('Ошибка: кнопка отправки не найдена.', 'error');
            return;
        }

        if (submitButton.disabled) {
            console.log('Кнопка отключена');
            return;
        }
        submitButton.disabled = true;

        const content = chatForm.querySelector('textarea[name="content"]').value.trim();
        const files = attachmentsInput.files;
        console.log('Содержимое:', content, 'Файлы:', Array.from(files).map(f => ({ name: f.name || 'undefined', size: f.size || 0 })));

        if (!content && files.length === 0) {
            console.log('Ошибка: нет текста или файлов');
            showNotification('Введите сообщение или прикрепите файл.', 'error');
            submitButton.disabled = false;
            return;
        }

        const formData = new FormData(chatForm);
        console.log('Запрос на:', chatForm.action);

        fetch(chatForm.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            console.log('Ответ:', { status: response.status, ok: response.ok });
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(`Сервер: ${response.status} - ${text}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('JSON:', data);
            if (data.status === 'sent') {
                console.log('Рендерим сообщение, ID:', data.message_id);
                const messageElement = document.createElement('div');
                messageElement.className = 'message-item sent';
                messageElement.dataset.messageId = data.message_id;

                let attachmentsHtml = '';
                if (files.length > 0) {
                    console.log('Обрабатываем файлы:', Array.from(files).map(f => ({ name: f.name || 'undefined', size: f.size || 0 })));
                    attachmentsHtml = Array.from(files)
                        .filter(file => file && typeof file.name === 'string')
                        .map((file, index) => {
                            console.log('Файл:', { name: file.name, type: file.type, size: file.size });
                            const isImage = typeof file.name === 'string' && (
                                file.name.toLowerCase().endsWith('.jpg') ||
                                file.name.toLowerCase().endsWith('.jpeg') ||
                                file.name.toLowerCase().endsWith('.png') ||
                                file.name.toLowerCase().endsWith('.gif') ||
                                file.name.toLowerCase().endsWith('.webp')
                            );
                            const attachmentId = data.attachment_ids && data.attachment_ids[index] ? data.attachment_ids[index] : null;
                            const tempUrl = attachmentId ? `/messages/attachment/${attachmentId}/` : (isImage ? URL.createObjectURL(file) : '/static/icons/placeholder.png');
                            console.log('Вложение:', file.name, 'URL:', tempUrl, 'Изображение:', isImage, 'Attachment ID:', attachmentId);
                            return `
                                <div class="attachment-item">
                                    ${isImage ? `
                                        <div class="attachment-preview">
                                            <img src="${tempUrl}" alt="${file.name}" onerror="console.error('Ошибка загрузки: ${file.name}, URL: ${tempUrl}')">
                                        </div>
                                    ` : `
                                        <div class="attachment-icon">
                                            <ion-icon name="${file.name.toLowerCase().endsWith('.pdf') ? 'document-text-outline' :
                                                file.name.match(/\.(doc|docx)$/) ? 'document-outline' :
                                                file.name.match(/\.(xls|xlsx)$/) ? 'grid-outline' :
                                                'document-attach-outline'}"></ion-icon>
                                        </div>
                                    `}
                                    <a href="${attachmentId ? `/messages/attachment/${attachmentId}/` : '#'}" class="attachment-download">
                                        <span class="filename">${file.name}</span>
                                        <ion-icon name="download-outline"></ion-icon>
                                    </a>
                                </div>
                            `;
                        }).join('');
                }

                messageElement.innerHTML = `
                    <div class="message-content">${content.replace(/\n/g, '<br>')}</div>
                    <div class="message-meta">${data.created_at}</div>
                    ${attachmentsHtml ? `
                        <div class="message-attachments">
                            <h4>Вложения:</h4>
                            <div class="attachments-grid">${attachmentsHtml}</div>
                        </div>
                    ` : ''}
                    <div class="message-actions">
                        <button class="delete-btn" data-message-id="${data.message_id}">
                            <ion-icon name="trash-outline"></ion-icon>
                        </button>
                    </div>
                `;
                console.log('Добавляем в чат');
                chatMessages.appendChild(messageElement);
                chatMessages.scrollTop = chatMessages.scrollHeight;

                console.log('Сбрасываем форму');
                chatForm.reset();
                selectedFilesContainer.innerHTML = '';
                attachmentsInput.value = '';

                showNotification('Сообщение отправлено!', 'success');

                if (currentUsername && currentUsername !== 'null') {
                    console.log('Синхронизация:', currentUsername);
                    setTimeout(() => {
                        loadConversation(currentUsername);
                    }, 1000);
                } else {
                    console.warn('Синхронизация пропущена: currentUsername=', currentUsername);
                }
            } else {
                console.log('Ошибка сервера:', data);
                showNotification(data.message || 'Ошибка отправки.', 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка фронтенда:', error.message);
            showNotification(`Ошибка: ${error.message}`, 'error');
        })
        .finally(() => {
            console.log('Разблокировка кнопки');
            submitButton.disabled = false;
        });
    });

    window.showDialogsList = function() {
        console.log('Показываем список диалогов');
        if (window.innerWidth <= 768) {
            dialogsList.classList.add('active');
            chatWindow.classList.remove('active');
            chatWindow.style.display = 'none';
        }
    };

    window.deleteMessage = function(messageId) {
        console.log('Удаление сообщения:', messageId);
        const button = document.querySelector(`.delete-btn[data-message-id="${messageId}"]`);
        if (button.disabled) {
            console.log('Кнопка заблокирована, пропуск');
            return;
        }
        button.disabled = true;
        fetch(`/messages/delete/${messageId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            console.log('Ответ удаления:', { status: response.status, ok: response.ok });
            if (!response.ok && response.status !== 404) {
                return response.text().then(text => {
                    throw new Error(`Сервер: ${response.status} - ${text}`);
                });
            }
            return response.status === 200 ? response.json() : { status: 'deleted' };
        })
        .then(data => {
            console.log('JSON удаления:', data);
            if (data.status === 'deleted' || data.status === 'success' || data.success || data.status === 404) {
                const messageElement = document.querySelector(`.message-item[data-message-id="${messageId}"]`);
                if (messageElement) {
                    messageElement.remove();
                    console.log('Сообщение удалено из DOM');
                }
                showNotification('Сообщение удалено.', 'success');
                if (currentUsername && currentUsername !== 'null') {
                    console.log('Синхронизация чата:', currentUsername);
                    setTimeout(() => {
                        loadConversation(currentUsername);
                    }, 500);
                } else {
                    console.warn('Синхронизация пропущена: currentUsername=', currentUsername);
                }
            } else {
                console.log('Ошибка сервера:', data);
                showNotification(data.message || 'Ошибка удаления сообщения.', 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка фронтенда:', error.message);
            showNotification(`Ошибка: ${error.message}`, 'error');
        })
        .finally(() => {
            button.disabled = false;
            console.log('Кнопка разблокирована');
        });
    };

    // Функция предпросмотра изображения
    window.openImagePreview = function(url, filename) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <img src="${url}" alt="${filename}">
                <span class="close-modal">×</span>
                <div class="modal-caption">${filename}</div>
            </div>
        `;
        document.body.appendChild(modal);
        modal.style.display = 'flex';
        modal.querySelector('.close-modal').addEventListener('click', () => {
            modal.remove();
        });
    };

    document.addEventListener('click', function(e) {
        if (e.target.closest('.delete-btn')) {
            const messageId = e.target.closest('.delete-btn').dataset.messageId;
            console.log('Клик по удалению:', messageId);
            if (messageId) {
                deleteMessage(messageId);
            }
        }
    });
});