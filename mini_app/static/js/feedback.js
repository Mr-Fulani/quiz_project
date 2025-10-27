/**
 * Система обратной связи для мини-приложения
 * Интегрируется с Django API для отправки сообщений
 */

console.log('🟢 feedback.js LOADED!');

// Предотвращаем повторное объявление класса при SPA-навигации
if (typeof FeedbackSystem === 'undefined') {
    window.FeedbackSystem = class FeedbackSystem {
    constructor() {
        this.selectedCategory = null;  // Не выбрана по умолчанию - пользователь должен выбрать сам
        this.isSubmitting = false;
        this.eventHandlers = []; // Для отслеживания обработчиков
        this.selectedImages = []; // Массив выбранных изображений
        
        this.init();
    }
    
    init() {
        console.log('🔧 FeedbackSystem: Initializing...');
        
        // Очищаем старые обработчики если они есть
        this.cleanup();
        
        // Немедленно настраиваем обработчики (DOM уже загружен, т.к. скрипт в конце)
        this.setupEventListeners();
    }
    
    cleanup() {
        // Удаляем все старые обработчики событий
        this.eventHandlers.forEach(({element, event, handler}) => {
            if (element) {
                element.removeEventListener(event, handler);
            }
        });
        this.eventHandlers = [];
    }
    
    setupEventListeners() {
        console.log('🔧 FeedbackSystem: Setting up event listeners...');
        
        // Обработчики для выбора категории
        const categoryOptions = document.querySelectorAll('.category-option');
        console.log(`Found ${categoryOptions.length} category options`);
        categoryOptions.forEach(option => {
            const handler = (e) => {
                console.log('Category clicked:', e.target.dataset.category);
                this.selectCategory(e.target);
            };
            option.addEventListener('click', handler);
            this.eventHandlers.push({element: option, event: 'click', handler});
        });
        
        // Обработчик для кнопки отправки
        const sendBtn = document.querySelector('.send-feedback-btn');
        console.log('Send feedback button:', sendBtn);
        if (sendBtn) {
            const handler = () => {
                console.log('Send feedback button clicked');
                this.submitFeedback();
            };
            sendBtn.addEventListener('click', handler);
            this.eventHandlers.push({element: sendBtn, event: 'click', handler});
        } else {
            console.warn('⚠️ Send feedback button not found');
        }
        
        // Обработчик для кнопки "Написать админу"
        const contactBtn = document.querySelector('.contact-admin-btn');
        console.log('Contact admin button:', contactBtn);
        if (contactBtn) {
            const handler = () => {
                console.log('Contact admin button clicked');
                this.contactAdmin();
            };
            contactBtn.addEventListener('click', handler);
            this.eventHandlers.push({element: contactBtn, event: 'click', handler});
        } else {
            console.warn('⚠️ Contact admin button not found');
        }
        
        // Обработчик для кнопки прикрепления изображений
        const imageBtn = document.querySelector('.feedback-image-btn');
        console.log('Image button:', imageBtn);
        if (imageBtn) {
            const handler = () => {
                console.log('Image button clicked');
                const imageInput = document.querySelector('.feedback-image-input');
                if (imageInput) imageInput.click();
            };
            imageBtn.addEventListener('click', handler);
            this.eventHandlers.push({element: imageBtn, event: 'click', handler});
        }
        
        // Обработчик для выбора файлов
        const imageInput = document.querySelector('.feedback-image-input');
        console.log('Image input:', imageInput);
        if (imageInput) {
            const handler = (e) => {
                console.log('Image input changed');
                this.previewImages(e.target.files);
            };
            imageInput.addEventListener('change', handler);
            this.eventHandlers.push({element: imageInput, event: 'change', handler});
        }
        
        console.log('✅ FeedbackSystem: Event listeners set up');
    }
    
    /**
     * Превью выбранных изображений
     */
    previewImages(files) {
        const filesArray = Array.from(files);
        
        // Валидация количества
        if (filesArray.length > 3) {
            const maxImagesError = window.translations?.max_images_error || 'Максимум 3 изображения';
            alert(maxImagesError);
            const imageInput = document.querySelector('.feedback-image-input');
            if (imageInput) imageInput.value = '';
            return;
        }

        // Валидация размера и типа файлов
        const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
        const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
        
        for (let i = 0; i < filesArray.length; i++) {
            const file = filesArray[i];
            
            // Проверка размера
            if (file.size > MAX_FILE_SIZE) {
                const tooLargeText = window.translations?.image_too_large || 'Изображение слишком большое! Максимум: 5 MB. Текущий размер:';
                alert(`${tooLargeText} ${(file.size / (1024 * 1024)).toFixed(2)} MB\n"${file.name}"`);
                const imageInput = document.querySelector('.feedback-image-input');
                if (imageInput) imageInput.value = '';
                return;
            }
            
            // Проверка типа
            if (!ALLOWED_TYPES.includes(file.type)) {
                const invalidFormatText = window.translations?.invalid_format || 'Недопустимый формат. Разрешены: JPEG, PNG, GIF, WebP';
                alert(`"${file.name}": ${file.type}\n\n${invalidFormatText}`);
                const imageInput = document.querySelector('.feedback-image-input');
                if (imageInput) imageInput.value = '';
                return;
            }
        }

        this.selectedImages = filesArray;
        
        // Удаляем старый превью
        let previewContainer = document.querySelector('.feedback-images-preview');
        if (previewContainer) {
            previewContainer.innerHTML = '';
        }

        if (filesArray.length === 0) return;

        filesArray.forEach((file, index) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const preview = document.createElement('div');
                preview.className = 'feedback-image-preview';
                
                // Форматируем размер файла
                const sizeKB = (file.size / 1024).toFixed(1);
                const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
                const sizeText = file.size < 1024 * 1024 ? `${sizeKB} KB` : `${sizeMB} MB`;
                
                preview.innerHTML = `
                    <img src="${e.target.result}" alt="Preview">
                    <div style="position: absolute; bottom: 25px; left: 5px; background: rgba(0,0,0,0.7); color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">
                        📦 ${sizeText}
                    </div>
                    <button class="feedback-image-remove" data-image-index="${index}">×</button>
                `;
                previewContainer.appendChild(preview);
                
                // Обработчик удаления
                const removeBtn = preview.querySelector('.feedback-image-remove');
                removeBtn.addEventListener('click', () => this.removeImage(index));
            };
            reader.readAsDataURL(file);
        });
    }
    
    /**
     * Удаление изображения из превью
     */
    removeImage(index) {
        const imageInput = document.querySelector('.feedback-image-input');
        if (!imageInput) return;

        const dt = new DataTransfer();
        const files = Array.from(imageInput.files);
        
        files.forEach((file, i) => {
            if (i !== index) dt.items.add(file);
        });

        imageInput.files = dt.files;
        
        // Обновляем превью
        this.previewImages(imageInput.files);
    }
    
    selectCategory(element) {
        // Убираем выделение со всех категорий
        document.querySelectorAll('.category-option').forEach(option => {
            option.classList.remove('selected');
        });
        
        // Выделяем выбранную категорию
        element.classList.add('selected');
        this.selectedCategory = element.dataset.category;
        
        console.log(`📋 Selected category: ${this.selectedCategory}`);
    }
    
    async submitFeedback() {
        if (this.isSubmitting) {
            console.log('⏳ Already submitting...');
            return;
        }
        
        // Проверяем, что категория выбрана
        if (!this.selectedCategory) {
            const errorMsg = window.translations?.feedback_error_category || 'Пожалуйста, выберите категорию';
            this.showStatus('error', errorMsg);
            return;
        }
        
        const messageTextarea = document.querySelector('.feedback-message');
        const message = messageTextarea ? messageTextarea.value.trim() : '';
        
        // Валидация
        if (!message || message.length < 3) {
            const errorMsg = window.translations?.feedback_error_short || 'Сообщение должно содержать минимум 3 символа';
            this.showStatus('error', errorMsg);
            return;
        }
        
        // Проверяем наличие Telegram WebApp
        if (!window.Telegram || !window.Telegram.WebApp) {
            this.showStatus('error', 'Telegram WebApp не доступен');
            return;
        }
        
        const tg = window.Telegram.WebApp;
        const user = tg.initDataUnsafe.user;
        
        if (!user || !user.id) {
            this.showStatus('error', 'Не удалось получить данные пользователя');
            return;
        }
        
        this.isSubmitting = true;
        const sendBtn = document.querySelector('.send-feedback-btn');
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.style.opacity = '0.5';
        }
        
        const sendingMsg = window.translations?.feedback_sending || 'Отправка...';
        this.showStatus('info', sendingMsg);
        
        try {
            // Используем FormData для отправки с изображениями
            const formData = new FormData();
            formData.append('telegram_id', user.id);
            formData.append('username', user.username || `${user.first_name || ''} ${user.last_name || ''}`.trim());
            formData.append('message', message);
            formData.append('category', this.selectedCategory);
            formData.append('source', 'mini_app');
            
            // Добавляем изображения
            const imageInput = document.querySelector('.feedback-image-input');
            if (imageInput && imageInput.files.length > 0) {
                Array.from(imageInput.files).forEach(file => {
                    formData.append('images', file);
                });
                console.log(`📷 Прикреплено ${imageInput.files.length} изображений`);
            }
            
            const response = await fetch('/api/feedback/', {
                method: 'POST',
                body: formData
                // НЕ указываем Content-Type - браузер сам установит multipart/form-data с boundary
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                const successMsg = window.translations?.feedback_success || 'Спасибо! Ваше сообщение отправлено';
                this.showStatus('success', successMsg);
                
                // Очищаем форму
                if (messageTextarea) {
                    messageTextarea.value = '';
                }
                
                // Сбрасываем категорию (ничего не выбрано)
                document.querySelectorAll('.category-option').forEach(option => {
                    option.classList.remove('selected');
                });
                this.selectedCategory = null;
                
                // Очищаем изображения
                const imageInput = document.querySelector('.feedback-image-input');
                if (imageInput) {
                    imageInput.value = '';
                }
                const previewContainer = document.querySelector('.feedback-images-preview');
                if (previewContainer) {
                    previewContainer.innerHTML = '';
                }
                this.selectedImages = [];
                
                console.log('✅ Feedback submitted successfully');
            } else {
                const errorMsg = data.error || window.translations?.feedback_error || 'Ошибка отправки';
                this.showStatus('error', errorMsg);
                console.error('❌ Feedback submission failed:', data);
            }
        } catch (error) {
            const networkErrorMsg = window.translations?.feedback_network_error || 'Ошибка сети';
            this.showStatus('error', networkErrorMsg);
            console.error('❌ Error submitting feedback:', error);
        } finally {
            this.isSubmitting = false;
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.style.opacity = '1';
            }
        }
    }
    
    async contactAdmin() {
        console.log('📧 Opening admin contact...');
        console.log('📧 window.ADMIN_TELEGRAM_ID:', window.ADMIN_TELEGRAM_ID);
        console.log('📧 typeof window.ADMIN_TELEGRAM_ID:', typeof window.ADMIN_TELEGRAM_ID);
        
        // Получаем Telegram ID админа из переменных окружения или конфигурации
        let adminTelegramId = (window.ADMIN_TELEGRAM_ID || '').trim();
        console.log('📧 adminTelegramId after trim:', `[${adminTelegramId}]`);
        console.log('📧 adminTelegramId length:', adminTelegramId.length);
        
        // Если ID не загружен, пытаемся загрузить его из API
        if (!adminTelegramId || adminTelegramId.length === 0) {
            console.log('⏳ Admin ID not loaded yet, fetching from API...');
            try {
                const response = await fetch('/api/get-config/');
                if (response.ok) {
                    const config = await response.json();
                    adminTelegramId = (config.admin_telegram_id || '').trim();
                    window.ADMIN_TELEGRAM_ID = adminTelegramId;
                    console.log('✅ Admin ID loaded from API:', adminTelegramId);
                } else {
                    console.error('❌ Failed to load config from API:', response.status);
                }
            } catch (error) {
                console.error('❌ Error loading config:', error);
            }
        }
        
        console.log('📧 Final adminTelegramId:', `[${adminTelegramId}]`);
        console.log('📧 Boolean check:', !!adminTelegramId);
        
        if (adminTelegramId && adminTelegramId.length > 0) {
            // Открываем чат с админом через Telegram
            const telegramUrl = `https://t.me/${adminTelegramId}`;
            console.log('✅ Opening Telegram URL:', telegramUrl);
            
            // Используем Telegram.WebApp.openTelegramLink если доступно
            if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.openTelegramLink) {
                console.log('✅ Using Telegram.WebApp.openTelegramLink');
                window.Telegram.WebApp.openTelegramLink(telegramUrl);
            } else {
                console.log('✅ Using window.open as fallback');
                window.open(telegramUrl, '_blank');
            }
        } else {
            // Если ID не задан, показываем сообщение
            console.warn('⚠️ Admin Telegram ID not configured or empty');
            const unavailableMsg = window.translations?.admin_contact_unavailable || 'Контакт админа недоступен';
            this.showStatus('error', unavailableMsg);
        }
    }
    
    showStatus(type, message) {
        const statusDiv = document.querySelector('.feedback-status');
        if (!statusDiv) return;
        
        statusDiv.style.display = 'block';
        statusDiv.className = 'feedback-status';
        
        if (type === 'success') {
            statusDiv.classList.add('success');
        } else if (type === 'error') {
            statusDiv.classList.add('error');
        }
        
        statusDiv.textContent = message;
        
        // Автоматически скрываем через 2 секунды для всех типов сообщений
        setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 2000);
    }
};
} else {
    console.log('⚠️ FeedbackSystem class already defined, skipping redefinition');
}

// Глобальная переменная для доступа к системе обратной связи
if (typeof feedbackSystem === 'undefined') {
    var feedbackSystem;
}

// Надежная инициализация при загрузке DOM
function initFeedbackSystem() {
    console.log('🔧 FeedbackSystem: Starting initialization...');
    console.log('🔧 Document readyState:', document.readyState);
    
    // Проверяем, есть ли форма feedback на странице
    const feedbackForm = document.querySelector('.feedback-container');
    if (!feedbackForm) {
        console.log('⚠️ FeedbackSystem: No feedback form found on this page, skipping initialization');
        return;
    }
    
    console.log('✅ FeedbackSystem: Feedback form found, initializing...');
    
    // Если система уже инициализирована, очищаем старый экземпляр
    if (feedbackSystem) {
        console.log('🧹 FeedbackSystem: Cleaning up old instance...');
        feedbackSystem.cleanup();
    }
    
    // Создаем новый экземпляр используя глобальный класс
    feedbackSystem = new window.FeedbackSystem();
}

// Проверяем состояние документа и инициализируем
if (document.readyState === 'loading') {
    // DOM еще загружается
    console.log('🔧 FeedbackSystem: DOM loading, adding DOMContentLoaded listener');
    document.addEventListener('DOMContentLoaded', initFeedbackSystem);
} else {
    // DOM уже загружен (SPA-навигация или обычная загрузка)
    console.log('🔧 FeedbackSystem: DOM already loaded, initializing immediately');
    // Для SPA нужна задержка, чтобы элементы успели вставиться в DOM
    setTimeout(initFeedbackSystem, 200);
}

