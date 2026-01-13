document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const recipientInput = document.getElementById('recipient-username');
    const attachmentsInput = document.getElementById('chat-attachments');
    const selectedFilesContainer = document.getElementById('selected-files');
    const dialogsList = document.querySelector('.dialogs-list');
    const chatWindow = document.querySelector('.chat-window');
    let currentUsername = null;

    // Инициализация
    console.log('DOM загружен, инициализация...');
    if (!dialogsList || !chatWindow) {
        console.error('Ошибка: dialogsList или chatWindow не найдены', { dialogsList, chatWindow });
        return;
    }

    if (window.innerWidth <= 768) {
        console.log('Мобильный режим: показываем dialogs-list');
        dialogsList.classList.add('active');
        dialogsList.style.display = 'block';
        chatWindow.classList.remove('active');
        chatWindow.style.display = 'none';
    } else {
        console.log('Десктопный режим: ничего не меняем');
    }

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

    // Отображение количества выбранных файлов
    if (attachmentsInput && selectedFilesContainer) {
        const attachmentLabel = document.querySelector('.attachment-label');
        attachmentsInput.addEventListener('change', function() {
            const fileCount = this.files.length;
            // Удаляем существующий счётчик, если он есть
            const existingCount = attachmentLabel.querySelector('.file-count');
            if (existingCount) {
                existingCount.remove();
            }
            // Если есть файлы, показываем количество
            if (fileCount > 0) {
                const countElement = document.createElement('span');
                countElement.className = 'file-count';
                countElement.textContent = fileCount;
                attachmentLabel.appendChild(countElement);
            }
            // Очищаем selected-files, так как список больше не нужен
            selectedFilesContainer.innerHTML = '';
        });

        // При отправке формы очищаем счётчик
        chatForm.addEventListener('submit', function() {
            const existingCount = attachmentLabel.querySelector('.file-count');
            if (existingCount) {
                existingCount.remove();
            }
        });
    } else {
        console.error('Ошибка: attachmentsInput или selectedFilesContainer не найдены', { attachmentsInput, selectedFilesContainer });
    }

    window.loadConversation = function(username) {
        console.log('Загрузка диалога:', username);
        currentUsername = username;
        if (recipientInput) recipientInput.value = username;
        const chatRecipient = document.getElementById('chat-recipient');
        if (chatRecipient) chatRecipient.textContent = username;

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
            dialogsList.style.display = 'none';
            chatWindow.classList.add('active');
            chatWindow.style.display = 'flex';
        }

        const url = window.conversationUrlTemplate.replace('__USERNAME__', username);

        fetch(url, {
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            console.log('Ответ сервера:', response.status);
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
                            <h4>${window.inboxTranslations?.attachments || 'Attachments'}:</h4>
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
            const errorMsg = window.inboxTranslations?.error_loading_conversation || 'Error loading conversation.';
            showNotification(errorMsg, 'error');
        });
    };

    window.showDialogsList = function() {
        console.log('Показываем список диалогов');
        if (window.innerWidth <= 768) {
            dialogsList.classList.add('active');
            dialogsList.style.display = 'block';
            chatWindow.classList.remove('active');
            chatWindow.style.display = 'none';
        }
    };

    // Обработка отправки формы
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        console.log('Отправка формы, currentUsername:', currentUsername);

        if (!recipientInput.value) {
            console.log('Ошибка: получатель не выбран');
            const selectDialogMsg = window.inboxTranslations?.select_dialog || 'Select a dialog to send a message.';
            showNotification(selectDialogMsg, 'error');
            return;
        }

        const submitButton = chatForm.querySelector('.send-btn');
        if (!submitButton) {
            console.error('Кнопка отправки не найдена');
            const sendButtonErrorMsg = window.inboxTranslations?.send_button_not_found || 'Error: send button not found.';
            showNotification(sendButtonErrorMsg, 'error');
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
            const enterMessageMsg = window.inboxTranslations?.enter_message_or_file || 'Enter a message or attach a file.';
            showNotification(enterMessageMsg, 'error');
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
                            <h4>${window.inboxTranslations?.attachments || 'Attachments'}:</h4>
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

                const messageSentMsg = window.inboxTranslations?.message_sent || 'Message sent successfully!';
                showNotification(messageSentMsg, 'success');

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
                const errorSendingMsg = window.inboxTranslations?.error_sending_message || 'Error sending message.';
                showNotification(data.message || errorSendingMsg, 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка фронтенда:', error.message);
            const errorSendingMsg = window.inboxTranslations?.error_sending_message || 'Error sending message.';
            showNotification(`${errorSendingMsg} ${error.message}`, 'error');
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
            dialogsList.style.display = 'block';
            chatWindow.classList.remove('active');
            chatWindow.style.display = 'none';
        }
    };

    /**
     * Удаляет сообщение через POST-запрос с учётом языка сайта
     * @param {string} messageId ID сообщения для удаления
     */
    window.deleteMessage = function(messageId) {
        console.log('Удаление сообщения:', messageId);
        const button = document.querySelector(`.delete-btn[data-message-id="${messageId}"]`);
        if (button.disabled) {
            console.log('Кнопка заблокирована, пропуск');
            return;
        }
        button.disabled = true;

        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (!csrfToken) {
            console.error('CSRF-токен не найден!');
            const csrfErrorMsg = window.inboxTranslations?.csrf_token_not_found || 'Error: CSRF token not found.';
            showNotification(csrfErrorMsg, 'error');
            button.disabled = false;
            return;
        }

        // Получаем текущий язык из атрибута <html lang> или cookie
        let language = document.documentElement.lang || 'en'; // По умолчанию 'en'
        if (!['en', 'ru'].includes(language)) {
            console.warn(`Неизвестный язык: ${language}, используем 'en'`);
            language = 'en';
        }
        console.log(`Текущий язык: ${language}`);

        // Формируем URL с языковым префиксом
        const deleteUrl = `/${language}/messages/delete/${messageId}/`;
        console.log(`URL удаления: ${deleteUrl}`);

        fetch(deleteUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken.value,
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json'
            },
            redirect: 'manual' // Отключаем автоматические редиректы
        })
        .then(response => {
            console.log('Ответ удаления:', {
                status: response.status,
                ok: response.ok,
                type: response.type,
                headers: Object.fromEntries(response.headers.entries())
            });
            if (response.status === 302) {
                console.warn('Получен редирект (302), игнорируем...');
                return { status: 'success' }; // Предполагаем успех
            }
            if (!response.ok && response.status !== 404) {
                return response.text().then(text => {
                    throw new Error(`Сервер: ${response.status} - ${text}`);
                });
            }
            return response.status === 200 ? response.json() : { status: 'deleted' };
        })
        .then(data => {
            console.log('JSON удаления:', data);
            if (data.status === 'deleted' || data.status === 'success' || data.success || response.status === 404) {
                const messageElement = document.querySelector(`.message-item[data-message-id="${messageId}"]`);
                if (messageElement) {
                    messageElement.remove();
                    console.log('Сообщение удалено из DOM');
                }
                const messageDeletedMsg = window.inboxTranslations?.message_deleted || 'Message deleted.';
                showNotification(messageDeletedMsg, 'success');
            } else {
                console.log('Ошибка сервера:', data);
                const errorDeletingMsg = window.inboxTranslations?.error_deleting_message || 'Error deleting message.';
                showNotification(data.message || errorDeletingMsg, 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка фронтенда:', error.message);
            const errorDeletingMsg = window.inboxTranslations?.error_deleting_message || 'Error deleting message.';
            showNotification(`${errorDeletingMsg} ${error.message}`, 'error');
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
                <div class="modal-caption">${filename}</div>
            </div>
        `;
        document.body.appendChild(modal);
        modal.style.display = 'flex';

        // Закрытие при клике вне области .modal-content
        modal.addEventListener('click', function(event) {
            const modalContent = modal.querySelector('.modal-content');
            // Проверяем, что клик был вне .modal-content
            if (!modalContent.contains(event.target)) {
                modal.remove();
            }
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