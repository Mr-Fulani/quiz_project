/**
 * Модуль для работы с комментариями к задачам
 * Поддерживает древовидную структуру, изображения и модерацию
 */

class CommentsManager {
    constructor(translationId, telegramId, username, language = 'en') {
        this.translationId = translationId;
        this.telegramId = telegramId;
        this.username = username;
        this.language = language || 'en';
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
        this.setupToggle();
        await this.loadComments();
        await this.loadCommentsCount();
    }

    /**
     * Настройка сворачивания/разворачивания секции
     */
    setupToggle() {
        const section = document.getElementById(`comments-${this.translationId}`);
        const header = section?.querySelector('h4');
        
        if (!header) return;
        
        // Обработчик клика по заголовку
        header.addEventListener('click', () => {
            section.classList.toggle('collapsed');
        });
    }

    /**
     * Загрузка комментариев с сервера
     */
    async loadComments(page = 1) {
        const container = document.getElementById(`comments-list-${this.translationId}`);
        if (!container) return;

        // Показываем индикатор загрузки
        if (page === 1) {
            const loadingText = window.translations?.loading_comments || 'Загрузка комментариев';
            container.innerHTML = `<div class="comments-loading">${loadingText}</div>`;
        }

        try {
            const response = await fetch(
                `/api/tasks/translations/${this.translationId}/comments/?page=${page}&ordering=-created_at&language=${this.language}`
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
                const emptyText = window.translations?.no_comments_yet || 'Комментариев пока нет. Будьте первым!';
                container.innerHTML = `<div class="comments-list empty">${emptyText}</div>`;
            } else {
                console.log(`🎨 Rendering ${this.comments.length} comments...`);
                this.renderComments();
            }

        } catch (error) {
            console.error('Ошибка загрузки комментариев:', error);
            const errorText = window.translations?.error_loading_comments || 'Ошибка загрузки комментариев';
            container.innerHTML = `<div class="comments-list empty">${errorText}</div>`;
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
     * Рендеринг списка комментариев в плоской структуре (как в Instagram)
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

        // Рендерим корневые комментарии и их ответы в плоской структуре
        rootComments.forEach((comment, index) => {
            console.log(`🎨 Rendering comment ${index + 1}/${rootComments.length}:`, comment);
            
            // Добавляем основной комментарий
            const element = this.createCommentElement(comment, null, null);
            console.log(`✅ Created element:`, element);
            container.appendChild(element);
            
            // Добавляем все ответы линейно (не вложенно)
            if (comment.replies && comment.replies.length > 0) {
                this.renderRepliesFlat(comment, container);
            }
        });

        console.log(`✅ Rendered ${rootComments.length} comments to DOM`);

        // Добавляем кнопку "Загрузить ещё"
        if (this.hasMore) {
            const loadMoreText = window.translations?.load_more || 'Загрузить ещё';
            const loadMoreBtn = document.createElement('div');
            loadMoreBtn.className = 'comments-load-more';
            loadMoreBtn.innerHTML = `
                <button class="load-more-btn" data-action="load-more" data-translation-id="${this.translationId}">
                    ${loadMoreText}
                </button>
            `;
            container.appendChild(loadMoreBtn);
        }
    }
    
    /**
     * Рекурсивный рендеринг ответов в плоской структуре
     */
    renderRepliesFlat(comment, container) {
        if (!comment.replies || comment.replies.length === 0) return;
        
        comment.replies.forEach(reply => {
            // Создаем элемент ответа с указанием автора родительского комментария
            const replyElement = this.createCommentElement(reply, comment.author_username, comment.author_telegram_id);
            container.appendChild(replyElement);
            
            // Рекурсивно добавляем ответы на этот ответ
            if (reply.replies && reply.replies.length > 0) {
                this.renderRepliesFlat(reply, container);
            }
        });
    }

    /**
     * Создание HTML элемента комментария (плоская структура)
     */
    createCommentElement(comment, parentAuthor = null, parentAuthorTelegramId = null) {
        const div = document.createElement('div');
        // Определяем класс: reply если есть parent_comment, иначе root
        const commentClass = comment.parent_comment ? 'comment-item comment-reply' : 'comment-item comment-root';
        div.className = commentClass;
        div.id = `comment-${comment.id}`; // ID для возможности прокрутки к конкретному комментарию
        div.dataset.commentId = comment.id;
        div.dataset.translationId = this.translationId;
        
        if (comment.is_deleted) {
            div.classList.add('deleted');
        }

        const canDelete = comment.author_telegram_id == this.telegramId;
        
        // Получаем URL для возврата (текущая страница с параметрами)
        const returnUrl = this.getReturnUrl();
        
        // Если это ответ и есть информация о родительском авторе
        const replyToHtml = parentAuthor && parentAuthorTelegramId ? 
            `<div class="reply-to">↳ ${window.translations?.reply_to || 'в ответ'} <a href="/user_profile/${parentAuthorTelegramId}${returnUrl}" class="reply-to-author">@${this.escapeHtml(parentAuthor)}</a></div>` : 
            parentAuthor ? 
            `<div class="reply-to">↳ ${window.translations?.reply_to || 'в ответ'} <span class="reply-to-author">@${this.escapeHtml(parentAuthor)}</span></div>` : '';

        // Создаем кликабельный username с параметрами возврата
        const authorUsername = comment.author_telegram_id ? 
            `<a href="/user_profile/${comment.author_telegram_id}${returnUrl}" class="comment-author-link">${this.escapeHtml(comment.author_username)}</a>` :
            `<span class="comment-author">${this.escapeHtml(comment.author_username)}</span>`;

        div.innerHTML = `
            <div class="comment-header">
                ${authorUsername}
                <span class="comment-date">${comment.created_at_formatted}</span>
            </div>
            ${replyToHtml}
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
                ${!comment.is_deleted ? `
                    <button class="comment-action" data-action="reply" data-comment-id="${comment.id}" data-translation-id="${this.translationId}">
                        💬 ${window.translations?.reply || 'Ответить'}
                    </button>
                ` : ''}
                ${canDelete && !comment.is_deleted ? `
                    <button class="comment-action danger" data-action="delete" data-comment-id="${comment.id}" data-translation-id="${this.translationId}">
                        🗑️ ${window.translations?.delete || 'Удалить'}
                    </button>
                ` : ''}
                ${!comment.is_deleted && comment.author_telegram_id != this.telegramId ? `
                    ${comment.has_reported_by_current_user ? `
                        <span class="comment-action reported" style="color: rgba(0, 255, 0, 0.5); cursor: default;" title="${window.translations?.report_already_sent || 'Жалоба уже отправлена'}">
                            ✅ ${window.translations?.reported || 'Жалоба отправлена'}
                        </span>
                    ` : `
                        <button class="comment-action" data-action="report" data-comment-id="${comment.id}" data-translation-id="${this.translationId}">
                            ⚠️ ${window.translations?.report || 'Пожаловаться'}
                        </button>
                    `}
                ` : ''}
            </div>
        `;

        return div;
    }

    /**
     * Получение URL для возврата на страницу комментариев
     */
    getReturnUrl() {
        // Получаем текущий URL страницы
        const currentPath = window.location.pathname;
        const currentSearch = window.location.search;
        
        // Извлекаем subtopic_id из пути /subtopic/{subtopic_id}/tasks
        const pathMatch = currentPath.match(/\/subtopic\/(\d+)\/tasks/);
        if (pathMatch) {
            const subtopicId = pathMatch[1];
            // Формируем параметры для возврата
            const params = new URLSearchParams({
                return_to: 'comments',
                subtopic_id: subtopicId,
                translation_id: this.translationId.toString()
            });
            
            // Добавляем язык если есть
            if (this.language) {
                params.set('lang', this.language);
            }
            
            return `?${params.toString()}`;
        }
        
        // Если не нашли subtopic_id, возвращаем минимальные параметры
        const params = new URLSearchParams({
            return_to: 'comments',
            translation_id: this.translationId.toString()
        });
        
        if (this.language) {
            params.set('lang', this.language);
        }
        
        return `?${params.toString()}`;
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
            const maxImagesError = window.translations?.max_images_error || 'Максимум 3 изображения';
            alert(maxImagesError);
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
                const tooLargeText = window.translations?.image_too_large || 'Изображение слишком большое!\nМаксимум: 5 MB\nТекущий размер:';
                alert(`${tooLargeText} ${(file.size / (1024 * 1024)).toFixed(2)} MB\n"${file.name}"`);
                input.value = '';
                return;
            }
            
            // Проверка типа
            if (!ALLOWED_TYPES.includes(file.type)) {
                const invalidFormatText = window.translations?.invalid_format || 'Недопустимый формат. Разрешены: JPEG, PNG, GIF, WebP';
                alert(`"${file.name}": ${file.type}\n\n${invalidFormatText}`);
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
            const minTextError = window.translations?.min_text_error || 'Комментарий должен содержать минимум 3 символа';
            alert(minTextError);
            return;
        }

        submitBtn.disabled = true;
        
        // Определяем язык для перевода текста кнопки
        let btnLanguage = this.language;
        if (!btnLanguage || !['en', 'ru'].includes(btnLanguage)) {
            const urlParams = new URLSearchParams(window.location.search);
            btnLanguage = urlParams.get('lang') || urlParams.get('language') || 'en';
        }
        
        // Переводим текст кнопки в зависимости от языка
        const sendingText = btnLanguage === 'en' ? 'Sending...' : 'Отправка...';
        submitBtn.textContent = sendingText;

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

            // Добавляем язык в URL как query параметр
            const url = `/api/tasks/translations/${this.translationId}/comments/`;
            // Определяем язык для запроса - используем this.language или из URL/cookie
            let requestLanguage = this.language;
            if (!requestLanguage || !['en', 'ru'].includes(requestLanguage)) {
                const urlParams = new URLSearchParams(window.location.search);
                requestLanguage = urlParams.get('lang') || urlParams.get('language') || 'en';
            }
            const urlWithLang = requestLanguage ? `${url}?language=${requestLanguage}` : url;
            
            const response = await fetch(
                urlWithLang,
                {
                    method: 'POST',
                    body: formData
                }
            );

            if (!response.ok) {
                const errorData = await response.json();
                
                // Проверяем, это ошибка бана
                if (response.status === 403 && errorData.is_banned) {
                    // Показываем специальное сообщение о бане, передаем язык запроса
                    this.showBanNotification(errorData, requestLanguage);
                    throw new Error('USER_BANNED'); // Специальная ошибка, чтобы не показывать alert
                }
                
                // Обычная ошибка - используем error или detail
                const errorMessage = errorData.error || errorData.detail || 'Ошибка создания комментария';
                throw new Error(errorMessage);
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
            
            // Не показываем alert для бана, так как уже показали специальное уведомление
            if (error.message !== 'USER_BANNED') {
                alert(error.message || 'Ошибка отправки комментария');
            }
        } finally {
            submitBtn.disabled = false;
            
            // Определяем язык для перевода текста кнопки (используем тот же язык, что и в начале метода)
            let btnLanguage = this.language;
            if (!btnLanguage || !['en', 'ru'].includes(btnLanguage)) {
                const urlParams = new URLSearchParams(window.location.search);
                btnLanguage = urlParams.get('lang') || urlParams.get('language') || 'en';
            }
            
            // Переводим текст кнопки в зависимости от языка
            const sendText = btnLanguage === 'en' ? 'Send' : 'Отправить';
            submitBtn.textContent = sendText;
        }
    }

    /**
     * Показать форму ответа на комментарий (Instagram-style)
     */
    showReplyForm(commentId) {
        // Удаляем предыдущую форму ответа
        const oldForm = document.querySelector('.reply-form');
        if (oldForm) oldForm.remove();

        const commentElement = document.querySelector(`[data-comment-id="${commentId}"]`);
        if (!commentElement) return;

        const replyPlaceholder = window.translations?.reply_placeholder || 'Напишите ответ...';
        const photoText = window.translations?.photo || 'Фото';
        const replyText = window.translations?.reply || 'Ответить';
        
        const form = document.createElement('div');
        form.className = 'comment-form reply-form';
        form.dataset.replyingTo = commentId;
        form.innerHTML = `
            <button class="comment-close-btn" data-action="close-reply-form" data-translation-id="${this.translationId}">✕</button>
            <textarea placeholder="${replyPlaceholder}"></textarea>
            <div class="comment-form-actions">
                <div class="comment-form-left">
                    <input type="file" class="comment-image-input" accept="image/*" multiple>
                    <button class="comment-image-btn">📷 ${photoText}</button>
                </div>
                <button class="comment-submit-btn">${replyText}</button>
            </div>
        `;

        // Вставляем форму ПОСЛЕ комментария (не внутри)
        commentElement.insertAdjacentElement('afterend', form);
        this.replyingTo = commentId;

        // Скроллим к форме плавно без агрессивного позиционирования
        setTimeout(() => {
            form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);

        // Фокусируем textarea
        const textarea = form.querySelector('textarea');
        setTimeout(() => textarea.focus(), 200);
    }

    /**
     * Удаление комментария
     */
    async deleteComment(commentId) {
        const confirmText = window.translations?.confirm_delete_comment || 'Вы уверены, что хотите удалить комментарий?';
        if (!confirm(confirmText)) {
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
        const t = window.translations || {};
        
        const modal = document.createElement('div');
        modal.className = 'report-modal';
        modal.dataset.commentId = commentId;
        modal.dataset.translationId = this.translationId;
        modal.innerHTML = `
            <div class="report-modal-content">
                <h3>${t.report_comment || 'Пожаловаться на комментарий'}</h3>
                <div class="report-reason-group">
                    <label class="report-reason-label">
                        <input type="radio" name="reason" value="spam" checked>
                        ${t.report_reason_spam || 'Спам'}
                    </label>
                    <label class="report-reason-label">
                        <input type="radio" name="reason" value="offensive">
                        ${t.report_reason_offensive || 'Оскорбительный контент'}
                    </label>
                    <label class="report-reason-label">
                        <input type="radio" name="reason" value="inappropriate">
                        ${t.report_reason_inappropriate || 'Неуместный контент'}
                    </label>
                    <label class="report-reason-label">
                        <input type="radio" name="reason" value="other">
                        ${t.report_reason_other || 'Другое'}
                    </label>
                </div>
                <textarea class="report-description" placeholder="${t.report_description_placeholder || 'Дополнительное описание (необязательно)'}"></textarea>
                <div class="report-modal-actions">
                    <button class="comment-cancel-btn" data-action="close-modal">
                        ${t.cancel || 'Отмена'}
                    </button>
                    <button class="report-submit-btn" data-action="submit-report" data-comment-id="${commentId}" data-translation-id="${this.translationId}" type="button">
                        ${t.send || 'Отправить'}
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Закрытие по клику вне модального окна
        modal.onclick = (e) => {
            if (e.target === modal) modal.remove();
        };
        
        // Прямой обработчик для кнопки Cancel
        const cancelBtn = modal.querySelector('.comment-cancel-btn[data-action="close-modal"]');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('❌ Закрытие модального окна жалобы');
                modal.remove();
            });
        }
        
        // Прямой обработчик для кнопки отправки (на случай если делегирование не сработает)
        const submitBtn = modal.querySelector('.report-submit-btn');
        if (submitBtn) {
            submitBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('📤 Прямой клик на кнопку отправки жалобы:', commentId);
                this.submitReport(commentId, modal);
            });
        }
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
                const errorData = await response.json();
                let errorMessage = 'Ошибка отправки жалобы';
                
                // Извлекаем сообщение об ошибке из разных форматов ответа DRF
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                } else if (errorData.non_field_errors && errorData.non_field_errors.length > 0) {
                    errorMessage = errorData.non_field_errors[0];
                } else if (errorData.error) {
                    errorMessage = errorData.error;
                } else if (typeof errorData === 'string') {
                    errorMessage = errorData;
                } else {
                    // Извлекаем первую ошибку из полей валидации
                    const firstErrorField = Object.keys(errorData)[0];
                    if (firstErrorField && Array.isArray(errorData[firstErrorField])) {
                        errorMessage = errorData[firstErrorField][0];
                    } else if (firstErrorField) {
                        errorMessage = errorData[firstErrorField];
                    }
                }
                
                // Если это ошибка дубликата, показываем специальное сообщение
                if (response.status === 400 && (errorMessage.includes('уже') || errorMessage.includes('already') || errorMessage.includes('существует'))) {
                    const t = window.translations || {};
                    alert(t.report_already_sent || 'Вы уже подали жалобу на этот комментарий');
                    modal.remove();
                    // Перезагружаем комментарии для обновления состояния
                    this.loadComments(1);
                    return;
                }
                
                throw new Error(errorMessage);
            }

            const t = window.translations || {};
            alert(t.report_sent || 'Жалоба отправлена. Спасибо!');
            modal.remove();
            
            // Перезагружаем комментарии для обновления состояния кнопки
            this.loadComments(1);

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

    /**
     * Показать уведомление о бане пользователя
     * @param {Object} banData - Данные о бане из API
     * @param {string} [requestLanguage] - Язык, который был использован в запросе (опционально)
     */
    showBanNotification(banData, requestLanguage = null) {
        // Удаляем предыдущее уведомление, если есть
        const existingNotification = document.querySelector('.ban-notification-overlay');
        if (existingNotification) {
            existingNotification.remove();
        }

        // Получаем язык и переводы - приоритет: переданный язык > this.language > URL > cookie > localizationService
        let lang = requestLanguage;
        if (!lang || !['en', 'ru'].includes(lang)) {
            lang = this.language;
        }
        if (!lang || !['en', 'ru'].includes(lang)) {
            // Пробуем получить из URL
            const urlParams = new URLSearchParams(window.location.search);
            const urlLang = urlParams.get('lang') || urlParams.get('language');
            if (urlLang && ['en', 'ru'].includes(urlLang)) {
                lang = urlLang;
            } else if (window.localizationService) {
                lang = window.localizationService.getCurrentLanguage();
            } else {
                // Пробуем получить из cookie
                const cookies = document.cookie.split(';');
                for (let cookie of cookies) {
                    const [key, value] = cookie.trim().split('=');
                    if (key === 'selected_language' && ['en', 'ru'].includes(value)) {
                        lang = value;
                        break;
                    }
                }
            }
        }
        // Fallback на русский если ничего не найдено
        if (!lang || !['en', 'ru'].includes(lang)) {
            lang = 'ru';
        }
        
        const translations = window.translations || {};
        
        // Функция для получения перевода
        const getText = (key, fallback) => {
            return translations[key] || fallback || key;
        };

        // Определяем локализацию для времени
        const locale = lang === 'en' ? 'en-US' : 'ru-RU';
        const dateFormat = lang === 'en' ? { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' } : { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' };

        // Форматируем время до разбана с учетом языка
        let timeText = '';
        if (banData.banned_until) {
            const bannedUntil = new Date(banData.banned_until);
            const now = new Date();
            const diff = bannedUntil - now;
            
            if (diff > 0) {
                const hours = Math.floor(diff / (1000 * 60 * 60));
                const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                
                if (lang === 'en') {
                    if (hours > 24) {
                        const days = Math.floor(hours / 24);
                        timeText = `until ${bannedUntil.toLocaleString(locale, dateFormat)}<br><small style="opacity: 0.8;">(${days} day${days !== 1 ? 's' : ''} ${hours % 24} hour${(hours % 24) !== 1 ? 's' : ''} remaining)</small>`;
                    } else if (hours > 0) {
                        timeText = `until ${bannedUntil.toLocaleString(locale, dateFormat)}<br><small style="opacity: 0.8;">(${hours} hour${hours !== 1 ? 's' : ''} ${minutes} minute${minutes !== 1 ? 's' : ''} remaining)</small>`;
                    } else {
                        timeText = `until ${bannedUntil.toLocaleString(locale, dateFormat)}<br><small style="opacity: 0.8;">(${minutes} minute${minutes !== 1 ? 's' : ''} remaining)</small>`;
                    }
                } else {
                    // Русский
                    if (hours > 24) {
                        const days = Math.floor(hours / 24);
                        const daysText = days === 1 ? 'день' : (days >= 2 && days <= 4 ? 'дня' : 'дней');
                        const hoursText = (hours % 24) === 1 ? 'час' : ((hours % 24) >= 2 && (hours % 24) <= 4 ? 'часа' : 'часов');
                        timeText = `до ${bannedUntil.toLocaleString(locale, dateFormat)}<br><small style="opacity: 0.8;">(осталось ${days} ${daysText} ${hours % 24} ${hoursText})</small>`;
                    } else if (hours > 0) {
                        const hoursText = hours === 1 ? 'час' : (hours >= 2 && hours <= 4 ? 'часа' : 'часов');
                        const minutesText = minutes === 1 ? 'минута' : (minutes >= 2 && minutes <= 4 ? 'минуты' : 'минут');
                        timeText = `до ${bannedUntil.toLocaleString(locale, dateFormat)}<br><small style="opacity: 0.8;">(осталось ${hours} ${hoursText} ${minutes} ${minutesText})</small>`;
                    } else {
                        const minutesText = minutes === 1 ? 'минута' : (minutes >= 2 && minutes <= 4 ? 'минуты' : 'минут');
                        timeText = `до ${bannedUntil.toLocaleString(locale, dateFormat)}<br><small style="opacity: 0.8;">(осталось ${minutes} ${minutesText})</small>`;
                    }
                }
            }
        } else {
            // Постоянный бан
            timeText = lang === 'en' 
                ? '<strong style="color: #ff4444;">permanently</strong>'
                : '<strong style="color: #ff4444;">навсегда</strong>';
        }

        // Получаем переводы для интерфейсных элементов
        const titleText = lang === 'en' ? 'You are banned' : 'Вы заблокированы';
        const blockedText = lang === 'en' ? 'Blocked:' : 'Заблокировано:';
        const reasonText = lang === 'en' ? 'Reason:' : 'Причина:';
        const buttonText = lang === 'en' ? 'Got it' : 'Понятно';
        
        // Словарь стандартных причин бана с переводами
        const banReasonsTranslations = {
            'ru': {
                'Блокировка на 1 час (действие администратора)': {
                    'en': 'Blocked for 1 hour (administrator action)',
                    'ru': 'Блокировка на 1 час (действие администратора)'
                },
                'Блокировка на 24 часа (действие администратора)': {
                    'en': 'Blocked for 24 hours (administrator action)',
                    'ru': 'Блокировка на 24 часа (действие администратора)'
                },
                'Блокировка на 7 дней (действие администратора)': {
                    'en': 'Blocked for 7 days (administrator action)',
                    'ru': 'Блокировка на 7 дней (действие администратора)'
                },
                'Блокировка на 30 дней (действие администратора)': {
                    'en': 'Blocked for 30 days (administrator action)',
                    'ru': 'Блокировка на 30 дней (действие администратора)'
                },
                'Постоянная блокировка (действие администратора)': {
                    'en': 'Permanent ban (administrator action)',
                    'ru': 'Постоянная блокировка (действие администратора)'
                },
                'Спам': {
                    'en': 'Spam',
                    'ru': 'Спам'
                },
                'Нарушение правил': {
                    'en': 'Rules violation',
                    'ru': 'Нарушение правил'
                },
                'Оскорбления': {
                    'en': 'Insults',
                    'ru': 'Оскорбления'
                },
                'Некорректное поведение': {
                    'en': 'Inappropriate behavior',
                    'ru': 'Некорректное поведение'
                }
            },
            'en': {
                'Blocked for 1 hour (administrator action)': {
                    'en': 'Blocked for 1 hour (administrator action)',
                    'ru': 'Блокировка на 1 час (действие администратора)'
                },
                'Blocked for 24 hours (administrator action)': {
                    'en': 'Blocked for 24 hours (administrator action)',
                    'ru': 'Блокировка на 24 часа (действие администратора)'
                },
                'Blocked for 7 days (administrator action)': {
                    'en': 'Blocked for 7 days (administrator action)',
                    'ru': 'Блокировка на 7 дней (действие администратора)'
                },
                'Blocked for 30 days (administrator action)': {
                    'en': 'Blocked for 30 days (administrator action)',
                    'ru': 'Блокировка на 30 дней (действие администратора)'
                },
                'Permanent ban (administrator action)': {
                    'en': 'Permanent ban (administrator action)',
                    'ru': 'Постоянная блокировка (действие администратора)'
                },
                'Spam': {
                    'en': 'Spam',
                    'ru': 'Спам'
                },
                'Rules violation': {
                    'en': 'Rules violation',
                    'ru': 'Нарушение правил'
                },
                'Insults': {
                    'en': 'Insults',
                    'ru': 'Оскорбления'
                },
                'Inappropriate behavior': {
                    'en': 'Inappropriate behavior',
                    'ru': 'Некорректное поведение'
                }
            }
        };
        
        /**
         * Функция для перевода причины бана
         * @param {string} reason - Причина бана из базы данных
         * @param {string} targetLang - Целевой язык перевода
         * @returns {string} Переведенная причина или исходная, если перевод не найден
         */
        const translateBanReason = (reason, targetLang) => {
            if (!reason) return '';
            
            // Ищем в словарях для обоих языков
            for (const langKey of ['ru', 'en']) {
                const translations = banReasonsTranslations[langKey];
                if (translations && translations[reason]) {
                    return translations[reason][targetLang] || reason;
                }
            }
            
            // Если точного совпадения нет, проверяем частичное совпадение
            const reasonLower = reason.toLowerCase();
            for (const langKey of ['ru', 'en']) {
                const translations = banReasonsTranslations[langKey];
                if (translations) {
                    for (const [key, value] of Object.entries(translations)) {
                        if (reasonLower.includes(key.toLowerCase()) || key.toLowerCase().includes(reasonLower)) {
                            return value[targetLang] || reason;
                        }
                    }
                }
            }
            
            // Если перевод не найден, возвращаем исходную причину
            return reason;
        };
        
        // Используем переведенное сообщение из API, если оно есть
        const banMessage = banData.error || banData.message || '';

        // Создаём overlay
        const overlay = document.createElement('div');
        overlay.className = 'ban-notification-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            padding: 20px;
            animation: fadeIn 0.3s ease;
        `;

        // Создаём модальное окно
        const modal = document.createElement('div');
        modal.className = 'ban-notification-modal';
        modal.style.cssText = `
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 20px;
            padding: 30px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            color: white;
            text-align: center;
            animation: slideUp 0.3s ease;
        `;

        // Формируем содержимое модального окна
        // Используем переведенное сообщение из API напрямую
        if (banMessage) {
            // Парсим сообщение: оно может содержать дату, время и причину
            // Формат: "You are banned until...\n\nReason: причина"
            const messageParts = banMessage.split('\n\n');
            let mainMessage = messageParts[0] || banMessage;
            let reasonPart = messageParts[1] || '';
            
            // Если причина не найдена в сообщении, но есть в banData, добавляем её
            if (!reasonPart && banData.ban_reason) {
                // Переводим причину бана в зависимости от языка приложения
                const translatedReason = translateBanReason(banData.ban_reason, lang);
                reasonPart = `${reasonText} ${translatedReason}`;
            } else if (reasonPart) {
                // Если причина уже есть в сообщении, проверяем, нужно ли её переводить
                // Извлекаем причину из строки "Reason: причина" или "Причина: причина"
                const reasonMatch = reasonPart.match(/^(?:Reason|Причина):\s*(.+)$/i);
                if (reasonMatch && reasonMatch[1]) {
                    const originalReason = reasonMatch[1].trim();
                    const translatedReason = translateBanReason(originalReason, lang);
                    // Если перевод найден, заменяем причину
                    if (translatedReason !== originalReason) {
                        reasonPart = `${reasonText} ${translatedReason}`;
                    }
                }
            }
            
            console.log('🔍 Ban notification debug:', {
                lang: lang,
                banMessage: banMessage,
                mainMessage: mainMessage,
                reasonPart: reasonPart,
                titleText: titleText,
                banData: banData
            });
            
            // Убираем дублирование - если mainMessage уже начинается с "You are banned" или "Вы заблокированы",
            // не показываем заголовок отдельно
            const hasTitleInMessage = mainMessage.toLowerCase().includes('you are banned') || 
                                     mainMessage.toLowerCase().includes('вы заблокированы') ||
                                     mainMessage.toLowerCase().startsWith('you are banned') ||
                                     mainMessage.toLowerCase().startsWith('вы заблокированы');
            
            modal.innerHTML = `
                <div style="font-size: 64px; margin-bottom: 20px;">🚫</div>
                ${!hasTitleInMessage ? `
                    <h2 style="margin: 0 0 15px 0; font-size: 24px; font-weight: bold;">
                        ${titleText}
                    </h2>
                ` : ''}
                <div style="background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 12px; margin: 20px 0;">
                    <div style="font-size: 16px; margin-bottom: ${reasonPart ? '15px' : '0'}; white-space: pre-line; line-height: 1.6;">
                        ${this.escapeHtml(mainMessage).replace(/\n/g, '<br>')}
                    </div>
                    ${reasonPart ? `
                        <div style="font-size: 14px; margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255, 255, 255, 0.2); white-space: pre-line; line-height: 1.5;">
                            ${this.escapeHtml(reasonPart).replace(/\n/g, '<br>')}
                        </div>
                    ` : ''}
                </div>
                <button class="ban-notification-close" style="
                    background: rgba(255, 255, 255, 0.2);
                    border: 2px solid rgba(255, 255, 255, 0.3);
                    color: white;
                    padding: 12px 30px;
                    border-radius: 25px;
                    font-size: 16px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    margin-top: 10px;
                " onmouseover="this.style.background='rgba(255, 255, 255, 0.3)'" onmouseout="this.style.background='rgba(255, 255, 255, 0.2)'">
                    ${buttonText}
                </button>
            `;
        } else {
            // Fallback: используем старое форматирование
            modal.innerHTML = `
                <div style="font-size: 64px; margin-bottom: 20px;">🚫</div>
                <h2 style="margin: 0 0 15px 0; font-size: 24px; font-weight: bold;">
                    ${titleText}
                </h2>
                <div style="background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 12px; margin: 20px 0;">
                    <div style="font-size: 16px; margin-bottom: 10px;">
                        <strong>${blockedText}</strong><br>
                        ${timeText}
                    </div>
                    ${banData.ban_reason ? `
                        <div style="font-size: 14px; margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255, 255, 255, 0.2);">
                            <strong>${reasonText}</strong><br>
                            <span style="opacity: 0.9;">${this.escapeHtml(translateBanReason(banData.ban_reason, lang))}</span>
                        </div>
                    ` : ''}
                </div>
                <p style="margin: 20px 0; opacity: 0.9; font-size: 14px;">
                    ${lang === 'en' ? 'You cannot leave comments until the ban expires.' : 'Вы не можете оставлять комментарии до окончания срока блокировки.'}
                </p>
                <button class="ban-notification-close" style="
                    background: rgba(255, 255, 255, 0.2);
                    border: 2px solid rgba(255, 255, 255, 0.3);
                    color: white;
                    padding: 12px 30px;
                    border-radius: 25px;
                    font-size: 16px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    margin-top: 10px;
                " onmouseover="this.style.background='rgba(255, 255, 255, 0.3)'" onmouseout="this.style.background='rgba(255, 255, 255, 0.2)'">
                    ${buttonText}
                </button>
            `;
        }

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // Добавляем анимации в head
        if (!document.querySelector('#ban-notification-styles')) {
            const style = document.createElement('style');
            style.id = 'ban-notification-styles';
            style.textContent = `
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                @keyframes slideUp {
                    from { 
                        opacity: 0;
                        transform: translateY(30px) scale(0.95);
                    }
                    to { 
                        opacity: 1;
                        transform: translateY(0) scale(1);
                    }
                }
            `;
            document.head.appendChild(style);
        }

        // Обработчик закрытия
        const closeHandler = () => {
            overlay.style.animation = 'fadeOut 0.3s ease';
            modal.style.animation = 'slideDown 0.3s ease';
            setTimeout(() => overlay.remove(), 300);
        };

        // Закрытие по кнопке
        modal.querySelector('.ban-notification-close').addEventListener('click', closeHandler);

        // Закрытие по клику на overlay
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                closeHandler();
            }
        });

        // Анимация закрытия
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeOut {
                from { opacity: 1; }
                to { opacity: 0; }
            }
            @keyframes slideDown {
                from { 
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }
                to { 
                    opacity: 0;
                    transform: translateY(30px) scale(0.95);
                }
            }
        `;
        document.head.appendChild(style);
    }
}

// Глобальная переменная для доступа из HTML
let commentsManager = null;

// Глобальный обработчик событий для кнопок комментариев
document.addEventListener('click', (e) => {
    // Обработка кнопок с data-action (включая модальные окна, которые могут быть вне .comments-section)
    const btn = e.target.closest('[data-action]');
    if (btn) {
        const action = btn.dataset.action;
        
        // Обработка действий которые не требуют секции комментариев (модальные окна)
        if (action === 'close-modal') {
            const modal = btn.closest('.report-modal');
            if (modal) {
                modal.remove();
                e.preventDefault();
                e.stopPropagation();
                return;
            }
        }
    }
    
    // КРИТИЧЕСКИ ВАЖНО: Обрабатываем только элементы внутри .comments-section
    // чтобы не мешать другим компонентам (навигация, feedback и т.д.)
    const commentsSection = e.target.closest('.comments-section');
    if (!commentsSection) {
        // Клик вне секции комментариев - игнорируем
        return;
    }
    
    // Обработка кнопок с data-action внутри секции комментариев
    if (btn) {
        const action = btn.dataset.action;
        const commentId = btn.dataset.commentId ? parseInt(btn.dataset.commentId) : null;
        const translationId = btn.dataset.translationId ? parseInt(btn.dataset.translationId) : null;
        
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
                e.preventDefault();
                e.stopPropagation();
                const modal = btn.closest('.report-modal');
                if (modal && commentId) {
                    console.log('📤 Отправка жалобы для комментария (через делегирование):', commentId);
                    manager.submitReport(commentId, modal);
                } else {
                    console.error('❌ Модальное окно или commentId не найдены:', { modal: !!modal, commentId, btn: btn });
                }
                break;
            case 'remove-image':
                if (manager) {
                    const imageIndex = parseInt(btn.dataset.imageIndex);
                    manager.removeImage(imageIndex);
                }
                break;
            case 'close-reply-form':
                // Закрытие формы ответа через крестик
                const form = btn.closest('.reply-form');
                if (form && manager) {
                    manager.replyingTo = null;
                    form.remove();
                }
                break;
        }
        e.stopPropagation();
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
        e.stopPropagation();
        return;
    }
    
    const submitBtn = e.target.closest('.comment-submit-btn');
    if (submitBtn) {
        // Пропускаем кнопки с data-action (они обрабатываются выше)
        if (submitBtn.hasAttribute('data-action')) {
            return;
        }
        
        console.log('📤 Submit button clicked via delegation');
        const form = submitBtn.closest('.comment-form');
        if (form) {
            const translationId = parseInt(commentsSection.dataset.translationId);
            const manager = window.commentManagers && window.commentManagers[translationId];
            if (manager) {
                // Проверяем, это reply-форма или основная
                const isReplyForm = form.classList.contains('reply-form');
                if (isReplyForm) {
                    // Получаем parentCommentId из data-атрибута формы
                    const parentCommentId = form.dataset.replyingTo ? parseInt(form.dataset.replyingTo) : null;
                    manager.submitComment(form, parentCommentId);
                } else {
                    manager.submitComment(form);
                }
            } else {
                console.error('Manager not found for translation', translationId);
            }
        }
        e.stopPropagation();
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
        e.stopPropagation();
    }
});

// Обработчик для позиционирования формы при появлении клавиатуры
let activeForm = null;
let viewportResizeHandler = null;

document.addEventListener('focusin', (e) => {
    const textarea = e.target.closest('.comment-form textarea');
    if (textarea) {
        console.log('⌨️ Textarea focused');
        
        // Expand Telegram WebApp для полного использования viewport
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.expand();
        }
        
        const form = textarea.closest('.comment-form');
        activeForm = form;
        
        // Подписываемся на изменение viewport (появление клавиатуры)
        if (window.visualViewport) {
            // Удаляем предыдущий обработчик если есть
            if (viewportResizeHandler) {
                window.visualViewport.removeEventListener('resize', viewportResizeHandler);
            }
            
            const initialHeight = window.visualViewport.height;
            
            viewportResizeHandler = () => {
                if (!activeForm) return;
                
                const currentHeight = window.visualViewport.height;
                const keyboardHeight = initialHeight - currentHeight;
                
                console.log('📐 Viewport changed:', { initialHeight, currentHeight, keyboardHeight });
                
                // Если клавиатура появилась (viewport уменьшился > 100px)
                if (keyboardHeight > 100) {
                    // Добавляем padding-bottom к форме чтобы она была видна над клавиатурой
                    const formRect = activeForm.getBoundingClientRect();
                    const viewportBottom = window.visualViewport.height;
                    const formBottom = formRect.bottom;
                    
                    // Если форма ниже видимой области
                    if (formBottom > viewportBottom) {
                        const scrollAmount = formBottom - viewportBottom + 20; // +20px запас
                        window.scrollBy({
                            top: scrollAmount,
                            behavior: 'smooth'
                        });
                    }
                }
            };
            
            window.visualViewport.addEventListener('resize', viewportResizeHandler);
            
            // Вызываем обработчик сразу после небольшой задержки
            setTimeout(viewportResizeHandler, 300);
        }
    }
});

document.addEventListener('focusout', (e) => {
    const textarea = e.target.closest('.comment-form textarea');
    if (textarea) {
        console.log('⌨️ Textarea blurred');
        
        // Отписываемся от событий viewport
        if (window.visualViewport && viewportResizeHandler) {
            window.visualViewport.removeEventListener('resize', viewportResizeHandler);
            viewportResizeHandler = null;
        }
        
        activeForm = null;
    }
});

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // Будет инициализирована для каждой задачи отдельно
});

