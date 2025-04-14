// inbox.js

function openImagePreview(url, filename) {
    const modal = document.getElementById('imagePreviewModal');
    const previewImage = document.getElementById('previewImage');
    const caption = document.querySelector('.modal-caption');

    previewImage.src = url;
    previewImage.alt = filename;
    caption.textContent = filename;
    modal.style.display = 'block';
}

document.querySelector('.close-modal').addEventListener('click', function() {
    document.getElementById('imagePreviewModal').style.display = 'none';
});

// Закрытие модального окна при клике вне изображения
document.getElementById('imagePreviewModal').addEventListener('click', function(e) {
    if (e.target === this) {
        this.style.display = 'none';
    }
});

// Обработка клавиши Escape для закрытия модального окна
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.getElementById('imagePreviewModal').style.display = 'none';
    }
});

// Функция для удаления сообщения
function deleteMessage(messageId) {
    if (confirm('Are you sure you want to delete this message?')) {
        fetch(`/messages/delete/${messageId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin' // Важно для CSRF
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
                messageElement.style.opacity = '0';
                setTimeout(() => {
                    messageElement.remove();
                    if (document.querySelectorAll('.message-item').length === 0) {
                        const noMessages = document.createElement('div');
                        noMessages.className = 'no-messages';
                        noMessages.innerHTML = `
                            <ion-icon name="mail-outline"></ion-icon>
                            <p>No messages yet.</p>
                        `;
                        document.querySelector('.messages-container').appendChild(noMessages);
                    }
                }, 300);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error deleting message. Please try again.');
        });
    }
}


// Функция для ответа на сообщение
function replyToMessage(username) {
    const modal = document.createElement('div');
    modal.className = 'reply-modal';
    modal.innerHTML = `
        <div class="reply-modal-content">
            <div class="reply-modal-header">
                <h3>Reply to ${username}</h3>
                <span class="close-reply-modal">&times;</span>
            </div>
            <form id="replyForm" method="POST" action="/messages/send/" enctype="multipart/form-data">
                <input type="hidden" name="csrfmiddlewaretoken" value="${document.querySelector('[name=csrfmiddlewaretoken]').value}">
                <input type="hidden" name="recipient_username" value="${username}">
                <textarea name="content" placeholder="Write your reply..." required></textarea>
                <div class="attachment-section">
                    <label for="reply-attachments" class="attachment-label">
                        <ion-icon name="attach-outline"></ion-icon>
                        Add Files
                    </label>
                    <input type="file" id="reply-attachments" name="attachments" multiple style="display: none;">
                    <div id="selected-files-reply" class="selected-files"></div>
                </div>
                <div class="reply-modal-footer">
                    <button type="submit" class="send-reply-btn">
                        <ion-icon name="send-outline"></ion-icon>
                        Send
                    </button>
                </div>
            </form>
        </div>
    `;
    document.body.appendChild(modal);

    // Обработчик закрытия модального окна
    const closeBtn = modal.querySelector('.close-reply-modal');
    closeBtn.onclick = function() {
        modal.remove();
    };

    // Закрытие по клику вне модального окна
    modal.onclick = function(event) {
        if (event.target === modal) {
            modal.remove();
        }
    };

    // Обработка файлов
    const attachmentsInput = modal.querySelector('#reply-attachments');
    const selectedFilesContainer = modal.querySelector('#selected-files-reply');

    attachmentsInput.onchange = function() {
        selectedFilesContainer.innerHTML = '';
        Array.from(this.files).forEach(file => {
            // Клиентская проверка размера файла (20 МБ = 20,971,520 байт)
            const maxFileSize = 20 * 1024 * 1024;
            if (file.size > maxFileSize) {
                alert(`Файл "${file.name}" превышает лимит в 20 МБ`);
                attachmentsInput.value = ''; // Очищаем input
                return;
            }
            const fileItem = document.createElement('div');
            fileItem.className = 'selected-file-item';
            fileItem.innerHTML = `
                <span>${file.name}</span>
                <ion-icon name="close-outline" class="remove-file"></ion-icon>
            `;
            fileItem.querySelector('.remove-file').onclick = function() {
                fileItem.remove();
                const dt = new DataTransfer();
                Array.from(attachmentsInput.files)
                    .filter(f => f.name !== file.name)
                    .forEach(f => dt.items.add(f));
                attachmentsInput.files = dt.files;
            };
            selectedFilesContainer.appendChild(fileItem);
        });
    };

    // Обработка отправки формы ответа
    const form = modal.querySelector('#replyForm');
    form.onsubmit = function(e) {
        e.preventDefault();
        const formData = new FormData(this);

        fetch(this.action, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'sent') {
                modal.remove();
                const notification = document.createElement('div');
                notification.className = 'message-notification success';
                notification.textContent = 'Reply sent successfully!';
                document.querySelector('.messages-container').prepend(notification);
                setTimeout(() => {
                    notification.remove();
                }, 3000);
                location.reload(); // Обновляем страницу
            } else {
                const notification = document.createElement('div');
                notification.className = 'message-notification error';
                notification.textContent = data.message || 'Error sending reply. Please try again.';
                form.prepend(notification);
                setTimeout(() => {
                    notification.remove();
                }, 3000);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            const notification = document.createElement('div');
            notification.className = 'message-notification error';
            notification.textContent = 'Error sending reply. Please try again.';
            form.prepend(notification);
            setTimeout(() => {
                notification.remove();
            }, 3000);
        });
    };
}

// Функция для получения CSRF токена (если потребуется)
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Добавляем JavaScript для переключения вкладок
document.addEventListener('DOMContentLoaded', function() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const messageTabs = document.querySelectorAll('.messages-tab');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // Убираем активный класс у всех кнопок и вкладок
            tabBtns.forEach(b => b.classList.remove('active'));
            messageTabs.forEach(tab => tab.classList.remove('active'));

            // Добавляем активный класс нажатой кнопке
            this.classList.add('active');

            // Показываем соответствующую вкладку
            const tabId = this.dataset.tab + '-messages';
            document.getElementById(tabId).classList.add('active');
        });
    });
});