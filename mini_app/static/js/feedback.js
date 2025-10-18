/**
 * Система обратной связи для мини-приложения
 * Интегрируется с Django API для отправки сообщений
 */

class FeedbackSystem {
    constructor() {
        this.selectedCategory = 'bug';  // По умолчанию
        this.isSubmitting = false;
        
        this.init();
    }
    
    init() {
        console.log('🔧 FeedbackSystem: Initializing...');
        
        // Ожидаем загрузки DOM
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupEventListeners());
        } else {
            this.setupEventListeners();
        }
    }
    
    setupEventListeners() {
        console.log('🔧 FeedbackSystem: Setting up event listeners...');
        
        // Обработчики для выбора категории
        const categoryOptions = document.querySelectorAll('.category-option');
        categoryOptions.forEach(option => {
            option.addEventListener('click', (e) => {
                this.selectCategory(e.target);
            });
        });
        
        // Обработчик для кнопки отправки
        const sendBtn = document.querySelector('.send-feedback-btn');
        if (sendBtn) {
            sendBtn.addEventListener('click', () => {
                this.submitFeedback();
            });
        }
        
        // Обработчик для кнопки "Написать админу"
        const contactBtn = document.querySelector('.contact-admin-btn');
        if (contactBtn) {
            contactBtn.addEventListener('click', () => {
                this.contactAdmin();
            });
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
                
                // Сбрасываем категорию на "bug"
                document.querySelectorAll('.category-option').forEach(option => {
                    option.classList.remove('selected');
                    if (option.dataset.category === 'bug') {
                        option.classList.add('selected');
                    }
                });
                this.selectedCategory = 'bug';
                
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
        
        // Получаем Telegram ID админа из переменных окружения или конфигурации
        // Пока используем placeholder - нужно будет добавить в конфиг
        const adminTelegramId = window.ADMIN_TELEGRAM_ID || '';
        
        if (adminTelegramId) {
            // Открываем чат с админом через Telegram
            const telegramUrl = `https://t.me/${adminTelegramId}`;
            window.open(telegramUrl, '_blank');
        } else {
            // Если ID не задан, показываем сообщение
            this.showStatus('error', window.t('admin_contact_unavailable', 'Контакт админа недоступен'));
            console.warn('⚠️ Admin Telegram ID not configured');
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
        
        // Автоматически скрываем через 5 секунд для успеха
        if (type === 'success') {
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, 5000);
        }
    }
}

// Глобальная переменная для доступа к системе обратной связи
let feedbackSystem;

// Инициализация при загрузке DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        console.log('🔧 FeedbackSystem: DOM loaded, initializing...');
        feedbackSystem = new FeedbackSystem();
    });
} else {
    console.log('🔧 FeedbackSystem: DOM already loaded, initializing...');
    feedbackSystem = new FeedbackSystem();
}

