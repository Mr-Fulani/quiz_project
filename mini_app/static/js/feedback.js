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
        
        console.log('✅ FeedbackSystem: Event listeners set up');
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
            this.showStatus('error', window.t('feedback_error_category', 'Пожалуйста, выберите категорию'));
            return;
        }
        
        const messageTextarea = document.querySelector('.feedback-message');
        const message = messageTextarea ? messageTextarea.value.trim() : '';
        
        // Валидация
        if (!message || message.length < 3) {
            this.showStatus('error', window.t('feedback_error_short', 'Сообщение должно содержать минимум 3 символа'));
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
        
        this.showStatus('info', window.t('feedback_sending', 'Отправка...'));
        
        try {
            const response = await fetch('/api/feedback/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    telegram_id: user.id,
                    username: user.username || `${user.first_name || ''} ${user.last_name || ''}`.trim(),
                    message: message,
                    category: this.selectedCategory
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.showStatus('success', window.t('feedback_success', 'Спасибо! Ваше сообщение отправлено'));
                
                // Очищаем форму
                if (messageTextarea) {
                    messageTextarea.value = '';
                }
                
                // Сбрасываем категорию (ничего не выбрано)
                document.querySelectorAll('.category-option').forEach(option => {
                    option.classList.remove('selected');
                });
                this.selectedCategory = null;
                
                console.log('✅ Feedback submitted successfully');
            } else {
                this.showStatus('error', data.error || window.t('feedback_error', 'Ошибка отправки'));
                console.error('❌ Feedback submission failed:', data);
            }
        } catch (error) {
            this.showStatus('error', window.t('feedback_network_error', 'Ошибка сети'));
            console.error('❌ Error submitting feedback:', error);
        } finally {
            this.isSubmitting = false;
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.style.opacity = '1';
            }
        }
    }
    
    contactAdmin() {
        console.log('📧 Opening admin contact...');
        console.log('📧 window.ADMIN_TELEGRAM_ID:', window.ADMIN_TELEGRAM_ID);
        console.log('📧 typeof window.ADMIN_TELEGRAM_ID:', typeof window.ADMIN_TELEGRAM_ID);
        
        // Получаем Telegram ID админа из переменных окружения или конфигурации
        const adminTelegramId = (window.ADMIN_TELEGRAM_ID || '').trim();
        console.log('📧 adminTelegramId after trim:', `[${adminTelegramId}]`);
        console.log('📧 adminTelegramId length:', adminTelegramId.length);
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
            this.showStatus('error', window.t('admin_contact_unavailable', 'Контакт админа недоступен'));
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

