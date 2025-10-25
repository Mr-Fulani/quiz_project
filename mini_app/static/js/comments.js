/**
 * Модуль для работы с комментариями к задачам
 * Поддерживает древовидную структуру, изображения и модерацию
 */

class CommentsManager {
    constructor(translationId, telegramId, username) {
        this.translationId = translationId;
        this.telegramId = telegramId;
        this.username = username;
        this.currentPage = 1;
        this.hasMore = false;
        this.comments = [];
        this.replyingTo = null;
    }

    /**
     * Инициализация менеджера комментариев
     */
    async init() {
        this.setupEventListeners();
        await this.loadComments();
        await this.loadCommentsCount();
    }

    /**
     * Загрузка комментариев с сервера
     */
    async loadComments(page = 1) {
        const container = document.getElementById(`comments-list-${this.translationId}`);
        if (!container) return;

        // Показываем индикатор загрузки
        if (page === 1) {
            container.innerHTML = '<div class="comments-loading">Загрузка комментариев</div>';
        }

        try {
            const response = await fetch(
                `/api/tasks/translations/${this.translationId}/comments/?page=${page}&ordering=-created_at`
            );

            if (!response.ok) {
                throw new Error('Ошибка загрузки комментариев');
            }

            const data = await response.json();
            
            console.log(`📥 Loaded comments for translation ${this.translationId}:`, data);
            console.log(`📊 Comments count: ${data.results?.length || 0}`);
            
            if (page === 1) {
                this.comments = data.results || [];
                container.innerHTML = '';
            } else {
                this.comments.push(...(data.results || []));
            }

            this.currentPage = page;
            this.hasMore = !!data.next;

            console.log(`📋 Total comments in memory: ${this.comments.length}`);

            if (this.comments.length === 0 && page === 1) {
                container.innerHTML = '<div class="comments-list empty">Комментариев пока нет. Будьте первым!</div>';
            } else {
                console.log(`🎨 Rendering ${this.comments.length} comments...`);
                this.renderComments();
            }

        } catch (error) {
            console.error('Ошибка загрузки комментариев:', error);
            container.innerHTML = '<div class="comments-list empty">Ошибка загрузки комментариев</div>';
        }
    }

    /**
     * Загрузка количества комментариев
     */
    async loadCommentsCount() {
        try {
            const response = await fetch(
                `/api/tasks/translations/${this.translationId}/comments/count/`
            );
            const data = await response.json();
            
            const countElement = document.querySelector(`#comments-${this.translationId} .comments-count`);
            if (countElement && data.count !== undefined) {
                countElement.textContent = `(${data.count})`;
            }
        } catch (error) {
            console.error('Ошибка загрузки количества комментариев:', error);
        }
    }

    /**
     * Рендеринг списка комментариев
     */
    renderComments() {
        const container = document.getElementById(`comments-list-${this.translationId}`);
        console.log(`🔍 Container found:`, container);
        console.log(`🔍 Container ID:`, `comments-list-${this.translationId}`);
        
        if (!container) {
            console.error(`❌ Container not found: comments-list-${this.translationId}`);
            return;
        }

        container.innerHTML = '';
        
        // Подсчитываем корневые комментарии
        const rootComments = this.comments.filter(c => !c.parent_comment);
        console.log(`📊 Root comments to render: ${rootComments.length} из ${this.comments.length}`);

        // Рендерим корневые комментарии
        rootComments.forEach((comment, index) => {
            console.log(`🎨 Rendering comment ${index + 1}/${rootComments.length}:`, comment);
            const element = this.createCommentElement(comment, 0);
            console.log(`✅ Created element:`, element);
            container.appendChild(element);
        });

        console.log(`✅ Rendered ${rootComments.length} comments to DOM`);

        // Добавляем кнопку "Загрузить ещё"
        if (this.hasMore) {
            const loadMoreBtn = document.createElement('div');
            loadMoreBtn.className = 'comments-load-more';
            loadMoreBtn.innerHTML = `
                <button class="load-more-btn" data-action="load-more" data-translation-id="${this.translationId}">
                    Загрузить ещё
                </button>
            `;
            container.appendChild(loadMoreBtn);
        }
    }

    /**
     * Создание HTML элемента комментария
     */
    createCommentElement(comment, level) {
        const div = document.createElement('div');
        div.className = `comment-item level-${level}`;
        div.dataset.commentId = comment.id;
        div.dataset.translationId = this.translationId;
        
        if (comment.is_deleted) {
            div.classList.add('deleted');
        }

        const canDelete = comment.author_telegram_id == this.telegramId;

        div.innerHTML = `
            <div class="comment-header">
                <span class="comment-author">${this.escapeHtml(comment.author_username)}</span>
                <span class="comment-date">${comment.created_at_formatted}</span>
            </div>
            <div class="comment-text">${this.escapeHtml(comment.text)}</div>
            ${comment.images && comment.images.length > 0 ? `
                <div class="comment-images">
                    ${comment.images.map(img => `
                        <img src="${img.image_url}" alt="Изображение" class="comment-image" 
                             onclick="window.open('${img.image_url}', '_blank')">
                    `).join('')}
                </div>
            ` : ''}
            <div class="comment-actions">
                ${level < 2 && !comment.is_deleted ? `
                    <button class="comment-action" data-action="reply" data-comment-id="${comment.id}" data-translation-id="${this.translationId}">
                        💬 Ответить
                    </button>
                ` : ''}
                ${canDelete && !comment.is_deleted ? `
                    <button class="comment-action danger" data-action="delete" data-comment-id="${comment.id}" data-translation-id="${this.translationId}">
                        🗑️ Удалить
                    </button>
                ` : ''}
                ${!comment.is_deleted && comment.author_telegram_id != this.telegramId ? `
                    <button class="comment-action" data-action="report" data-comment-id="${comment.id}" data-translation-id="${this.translationId}">
                        ⚠️ Пожаловаться
                    </button>
                ` : ''}
            </div>
            <div class="comment-replies" id="replies-${comment.id}"></div>
        `;

        // Рендерим ответы
        if (comment.replies && comment.replies.length > 0) {
            const repliesContainer = div.querySelector(`#replies-${comment.id}`);
            comment.replies.forEach(reply => {
                repliesContainer.appendChild(this.createCommentElement(reply, level + 1));
            });
        }

        return div;
    }

    /**
     * Настройка обработчиков событий
     */
    setupEventListeners() {
        console.log(`🔧 setupEventListeners for translation ${this.translationId}`);
        // Обработчики теперь в глобальном слушателе ниже
    }

    /**
     * Превью выбранных изображений
     */
    previewImages(input, form) {
        const files = Array.from(input.files);
        
        // Валидация количества
        if (files.length > 3) {
            alert('Максимум 3 изображения');
            input.value = '';
            return;
        }

        // Валидация размера и типа файлов
        const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
        const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
        
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            
            // Проверка размера
            if (file.size > MAX_FILE_SIZE) {
                alert(`Изображение "${file.name}" слишком большое!\nМаксимум: 5 MB\nТекущий размер: ${(file.size / (1024 * 1024)).toFixed(2)} MB`);
                input.value = '';
                return;
            }
            
            // Проверка типа
            if (!ALLOWED_TYPES.includes(file.type)) {
                alert(`Недопустимый формат "${file.name}": ${file.type}\nРазрешены: JPEG, PNG, GIF, WebP`);
                input.value = '';
                return;
            }
        }

        // Удаляем старый превью
        let previewContainer = form.querySelector('.comment-images-preview');
        if (previewContainer) {
            previewContainer.remove();
        }

        if (files.length === 0) return;

        // Создаём новый превью
        previewContainer = document.createElement('div');
        previewContainer.className = 'comment-images-preview';

        files.forEach((file, index) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const preview = document.createElement('div');
                preview.className = 'comment-image-preview';
                
                // Форматируем размер файла
                const sizeKB = (file.size / 1024).toFixed(1);
                const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
                const sizeText = file.size < 1024 * 1024 ? `${sizeKB} KB` : `${sizeMB} MB`;
                
                preview.innerHTML = `
                    <img src="${e.target.result}" alt="Preview">
                    <div style="position: absolute; bottom: 25px; left: 5px; background: rgba(0,0,0,0.7); color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">
                        📦 ${sizeText}
                    </div>
                    <button class="comment-image-remove" data-action="remove-image" data-image-index="${index}" data-translation-id="${this.translationId}">×</button>
                `;
                previewContainer.appendChild(preview);
            };
            reader.readAsDataURL(file);
        });

        form.insertBefore(previewContainer, form.querySelector('.comment-form-actions'));
    }

    /**
     * Удаление изображения из превью
     */
    removeImage(index) {
        const input = document.querySelector(`#comments-${this.translationId} .comment-image-input`);
        if (!input) return;

        const dt = new DataTransfer();
        const files = Array.from(input.files);
        
        files.forEach((file, i) => {
            if (i !== index) dt.items.add(file);
        });

        input.files = dt.files;
        
        // Обновляем превью
        const form = input.closest('.comment-form');
        this.previewImages(input, form);
    }

    /**
     * Отправка комментария
     */
    async submitComment(form, parentId = null) {
        const textarea = form.querySelector('textarea');
        const imageInput = form.querySelector('.comment-image-input');
        const submitBtn = form.querySelector('.comment-submit-btn');
        
        const text = textarea.value.trim();
        
        if (text.length < 3) {
            alert('Комментарий должен содержать минимум 3 символа');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = 'Отправка...';

        try {
            const formData = new FormData();
            formData.append('text', text);
            formData.append('author_telegram_id', this.telegramId);
            formData.append('author_username', this.username);
            
            if (parentId) {
                formData.append('parent_comment', parentId);
            }

            // Добавляем изображения
            if (imageInput && imageInput.files.length > 0) {
                Array.from(imageInput.files).forEach(file => {
                    formData.append('images', file);
                });
            }

            const response = await fetch(
                `/api/tasks/translations/${this.translationId}/comments/`,
                {
                    method: 'POST',
                    body: formData
                }
            );

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка создания комментария');
            }

            // Очищаем форму
            textarea.value = '';
            if (imageInput) {
                imageInput.value = '';
                const preview = form.querySelector('.comment-images-preview');
                if (preview) preview.remove();
            }

            // Скрываем форму ответа если это был ответ
            if (parentId) {
                form.remove();
                this.replyingTo = null;
            }

            // Перезагружаем комментарии
            await this.loadComments(1);
            await this.loadCommentsCount();

        } catch (error) {
            console.error('Ошибка отправки комментария:', error);
            alert(error.message || 'Ошибка отправки комментария');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Отправить';
        }
    }

    /**
     * Показать форму ответа на комментарий
     */
    showReplyForm(commentId) {
        // Удаляем предыдущую форму ответа
        const oldForm = document.querySelector('.reply-form');
        if (oldForm) oldForm.remove();

        const commentElement = document.querySelector(`[data-comment-id="${commentId}"]`);
        if (!commentElement) return;

        const form = document.createElement('div');
        form.className = 'comment-form reply-form';
        form.innerHTML = `
            <textarea placeholder="Напишите ответ..."></textarea>
            <div class="comment-form-actions">
                <div class="comment-form-left">
                    <input type="file" class="comment-image-input" accept="image/*" multiple>
                    <button class="comment-image-btn">📷 Фото</button>
                </div>
                <div>
                    <button class="comment-cancel-btn">Отмена</button>
                    <button class="comment-submit-btn">Ответить</button>
                </div>
            </div>
        `;

        commentElement.appendChild(form);
        this.replyingTo = commentId;

        // Обработчики уже настроены через глобальное делегирование событий
        // Нужен только обработчик для кнопки "Отмена"
        const textarea = form.querySelector('textarea');
        const cancelBtn = form.querySelector('.comment-cancel-btn');

        const self = this;
        cancelBtn.onclick = () => {
            form.remove();
            self.replyingTo = null;
        };

        textarea.focus();
    }

    /**
     * Удаление комментария
     */
    async deleteComment(commentId) {
        if (!confirm('Вы уверены, что хотите удалить комментарий?')) {
            return;
        }

        try {
            const response = await fetch(
                `/api/tasks/translations/${this.translationId}/comments/${commentId}/?telegram_id=${this.telegramId}`,
                { method: 'DELETE' }
            );

            if (!response.ok) {
                throw new Error('Ошибка удаления комментария');
            }

            // Перезагружаем комментарии
            await this.loadComments(1);
            await this.loadCommentsCount();

        } catch (error) {
            console.error('Ошибка удаления комментария:', error);
            alert('Ошибка удаления комментария');
        }
    }

    /**
     * Показать модальное окно жалобы
     */
    showReportModal(commentId) {
        const modal = document.createElement('div');
        modal.className = 'report-modal';
        modal.dataset.commentId = commentId;
        modal.dataset.translationId = this.translationId;
        modal.innerHTML = `
            <div class="report-modal-content">
                <h3>Пожаловаться на комментарий</h3>
                <div class="report-reason-group">
                    <label class="report-reason-label">
                        <input type="radio" name="reason" value="spam" checked>
                        Спам
                    </label>
                    <label class="report-reason-label">
                        <input type="radio" name="reason" value="offensive">
                        Оскорбительный контент
                    </label>
                    <label class="report-reason-label">
                        <input type="radio" name="reason" value="inappropriate">
                        Неуместный контент
                    </label>
                    <label class="report-reason-label">
                        <input type="radio" name="reason" value="other">
                        Другое
                    </label>
                </div>
                <textarea class="report-description" placeholder="Дополнительное описание (необязательно)"></textarea>
                <div class="report-modal-actions">
                    <button class="comment-cancel-btn" data-action="close-modal">
                        Отмена
                    </button>
                    <button class="comment-submit-btn" data-action="submit-report" data-comment-id="${commentId}" data-translation-id="${this.translationId}">
                        Отправить
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Закрытие по клику вне модального окна
        modal.onclick = (e) => {
            if (e.target === modal) modal.remove();
        };
    }

    /**
     * Отправка жалобы
     */
    async submitReport(commentId, modal) {
        const reason = modal.querySelector('input[name="reason"]:checked').value;
        const description = modal.querySelector('.report-description').value.trim();

        try {
            const response = await fetch(
                `/api/tasks/translations/${this.translationId}/comments/${commentId}/report/`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        reporter_telegram_id: this.telegramId,
                        reason: reason,
                        description: description || null
                    })
                }
            );

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка отправки жалобы');
            }

            alert('Жалоба отправлена. Спасибо!');
            modal.remove();

        } catch (error) {
            console.error('Ошибка отправки жалобы:', error);
            alert(error.message || 'Ошибка отправки жалобы');
        }
    }

    /**
     * Загрузка следующей страницы комментариев
     */
    async loadMore() {
        await this.loadComments(this.currentPage + 1);
    }

    /**
     * Экранирование HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Глобальная переменная для доступа из HTML
let commentsManager = null;

// Глобальный обработчик событий для кнопок комментариев
document.addEventListener('click', (e) => {
    // Обработка кнопок с data-action
    const btn = e.target.closest('[data-action]');
    if (btn) {
        const action = btn.dataset.action;
        const commentId = btn.dataset.commentId ? parseInt(btn.dataset.commentId) : null;
        const translationId = btn.dataset.translationId ? parseInt(btn.dataset.translationId) : null;
        
        // Обработка действий которые не требуют менеджера
        if (action === 'close-modal') {
            const modal = btn.closest('.report-modal');
            if (modal) modal.remove();
            return;
        }
        
        // Получаем менеджер для данного перевода
        const manager = translationId && window.commentManagers && window.commentManagers[translationId];
        if (!manager && translationId) {
            console.error('Comments manager not found for translation', translationId);
            return;
        }
        
        switch (action) {
            case 'reply':
                manager.showReplyForm(commentId);
                break;
            case 'delete':
                manager.deleteComment(commentId);
                break;
            case 'report':
                manager.showReportModal(commentId);
                break;
            case 'load-more':
                manager.loadMore();
                break;
            case 'submit-report':
                const modal = btn.closest('.report-modal');
                if (modal) {
                    manager.submitReport(commentId, modal);
                }
                break;
            case 'remove-image':
                if (manager) {
                    const imageIndex = parseInt(btn.dataset.imageIndex);
                    manager.removeImage(imageIndex);
                }
                break;
        }
        return;
    }
    
    // Обработка кнопок формы комментариев (без data-action)
    const imageBtn = e.target.closest('.comment-image-btn');
    if (imageBtn) {
        console.log('📷 Image button clicked via delegation');
        const form = imageBtn.closest('.comment-form');
        if (form) {
            const imageInput = form.querySelector('.comment-image-input');
            if (imageInput) imageInput.click();
        }
        return;
    }
    
    const submitBtn = e.target.closest('.comment-submit-btn');
    if (submitBtn) {
        console.log('📤 Submit button clicked via delegation');
        const form = submitBtn.closest('.comment-form');
        if (form) {
            // Ищем comments-section (может быть выше для reply-формы)
            let section = form.closest('.comments-section');
            
            // Если не нашли (reply-форма), ищем через родительский comment-item
            if (!section) {
                const commentItem = form.closest('.comment-item');
                if (commentItem) {
                    section = commentItem.closest('.comments-section');
                }
            }
            
            if (section) {
                const translationId = parseInt(section.dataset.translationId);
                const manager = window.commentManagers && window.commentManagers[translationId];
                if (manager) {
                    // Проверяем, это reply-форма или основная
                    const isReplyForm = form.classList.contains('reply-form');
                    if (isReplyForm) {
                        const commentElement = form.closest('.comment-item');
                        const parentCommentId = commentElement ? parseInt(commentElement.dataset.commentId) : null;
                        manager.submitComment(form, parentCommentId);
                    } else {
                        manager.submitComment(form);
                    }
                } else {
                    console.error('Manager not found for translation', translationId);
                }
            } else {
                console.error('Comments section not found for submit');
            }
        }
        return;
    }
});

// Обработчик для изменения файлов
document.addEventListener('change', (e) => {
    const imageInput = e.target.closest('.comment-image-input');
    if (imageInput) {
        console.log('📸 Image input changed');
        const form = imageInput.closest('.comment-form');
        if (form) {
            // Ищем comments-section (может быть выше для reply-формы)
            let section = form.closest('.comments-section');
            
            // Если не нашли (reply-форма), ищем через родительский comment-item
            if (!section) {
                const commentItem = form.closest('.comment-item');
                if (commentItem) {
                    section = commentItem.closest('.comments-section');
                }
            }
            
            if (section) {
                const translationId = parseInt(section.dataset.translationId);
                const manager = window.commentManagers && window.commentManagers[translationId];
                if (manager) {
                    console.log('📸 Calling previewImages for translation', translationId);
                    manager.previewImages(imageInput, form);
                } else {
                    console.error('Manager not found for translation', translationId);
                }
            } else {
                console.error('Comments section not found');
            }
        }
    }
});

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // Будет инициализирована для каждой задачи отдельно
});

