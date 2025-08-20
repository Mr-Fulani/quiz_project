/**
 * Система донатов для мини-приложения
 * Интегрируется с Django API и Stripe для обработки платежей
 */

class DonationSystem {
    constructor() {
        this.stripe = null;
        this.elements = null;
        this.cardElement = null;
        this.currentPaymentIntent = null;
        this.selectedAmount = 5;
        this.selectedCurrency = 'usd';
        this.isProcessing = false;
        
        this.init();
    }
    
    async init() {
        console.log('🔧 DonationSystem: Initializing...');
        
        // Инициализируем Stripe
        await this.initStripe();
        
        // Привязываем события
        this.bindEvents();
        
        // Устанавливаем начальные значения
        this.setInitialValues();
        
        console.log('✅ DonationSystem: Initialized successfully');
    }
    
    async initStripe() {
        try {
            // Получаем публичный ключ Stripe с сервера через мини-апп API
            const response = await fetch('/api/stripe-publishable-key');
            const data = await response.json();
            
            if (data.publishable_key) {
                this.stripe = Stripe(data.publishable_key);
                console.log('✅ Stripe initialized with key:', data.publishable_key.substring(0, 20) + '...');
            } else {
                console.warn('⚠️ Stripe publishable key not available');
            }
        } catch (error) {
            console.error('❌ Error initializing Stripe:', error);
        }
    }
    
    bindEvents() {
        console.log('🔧 DonationSystem: Binding events...');
        
        // Используем делегирование событий для динамически созданных элементов
        document.addEventListener('click', (e) => {
            // Обработчики для выбора суммы
            if (e.target.classList.contains('amount-option')) {
                console.log('💰 Amount option clicked:', e.target.dataset.amount);
                this.selectAmount(parseFloat(e.target.dataset.amount));
            }
            
            // Обработчики для выбора валюты
            if (e.target.classList.contains('currency-option')) {
                console.log('💱 Currency option clicked:', e.target.dataset.currency);
                this.selectCurrency(e.target.dataset.currency);
            }
            
            // Обработчик для кнопки доната
            if (e.target.closest('.donate-btn')) {
                console.log('💳 Donate button clicked');
                e.preventDefault();
                this.showPaymentModal();
            }
        });
        
        // Обработчик для поля ввода суммы
        document.addEventListener('input', (e) => {
            if (e.target.classList.contains('amount-input')) {
                console.log('📝 Amount input changed:', e.target.value);
                this.selectedAmount = parseFloat(e.target.value) || 0;
                this.updateAmountSelection();
            }
        });
        
        console.log('✅ DonationSystem: Events bound successfully');
    }
    
    setInitialValues() {
        console.log('🔧 DonationSystem: Setting initial values...');
        
        // Устанавливаем начальную сумму
        this.selectAmount(this.selectedAmount);
        
        // Устанавливаем начальную валюту
        this.selectCurrency(this.selectedCurrency);
        
        // Устанавливаем начальное значение в поле ввода
        const amountInput = document.querySelector('.amount-input');
        if (amountInput) {
            amountInput.value = this.selectedAmount;
            console.log('✅ Set initial input value:', this.selectedAmount);
        } else {
            console.warn('⚠️ Amount input not found during initialization');
        }
        
        console.log('✅ DonationSystem: Initial values set');
    }
    
    selectAmount(amount) {
        console.log('🔧 DonationSystem: Selecting amount:', amount);
        this.selectedAmount = amount;
        
        // Обновляем визуальное выделение
        const options = document.querySelectorAll('.amount-option');
        console.log('🔧 Found amount options:', options.length);
        
        options.forEach(option => {
            option.classList.remove('selected');
            if (parseFloat(option.dataset.amount) === amount) {
                option.classList.add('selected');
                console.log('✅ Selected option:', option.textContent);
            }
        });
        
        // Обновляем поле ввода
        const amountInput = document.querySelector('.amount-input');
        if (amountInput) {
            amountInput.value = amount;
            console.log('✅ Updated input value:', amount);
        } else {
            console.warn('⚠️ Amount input not found');
        }
        
        console.log('💰 Selected amount:', amount);
    }
    
    selectCurrency(currency) {
        console.log('🔧 DonationSystem: Selecting currency:', currency);
        this.selectedCurrency = currency;
        
        // Обновляем визуальное выделение
        const options = document.querySelectorAll('.currency-option');
        console.log('🔧 Found currency options:', options.length);
        
        options.forEach(option => {
            option.classList.remove('selected');
            if (option.dataset.currency === currency) {
                option.classList.add('selected');
                console.log('✅ Selected currency option:', option.textContent);
            }
        });
        
        console.log('💱 Selected currency:', currency);
    }
    
    updateAmountSelection() {
        // Убираем выделение со всех опций
        document.querySelectorAll('.amount-option').forEach(option => {
            option.classList.remove('selected');
        });
    }
    
    async showPaymentModal() {
        if (this.isProcessing) return;
        
        // Валидация
        if (!this.validateForm()) {
            return;
        }
        
        console.log('💳 Showing payment modal...');
        
        // Создаем модальное окно
        this.createPaymentModal();
        
        // Показываем модальное окно в DOM
        document.body.appendChild(this.modal);
        
        // Ждем немного, чтобы DOM обновился
        await new Promise(resolve => setTimeout(resolve, 50));
        
        // Инициализируем Stripe Elements
        await this.initStripeElements();
        
        // Создаем Payment Intent
        await this.createPaymentIntent();
    }
    
    validateForm() {
        const name = document.querySelector('.donation-name').value.trim();
        const amount = this.selectedAmount;
        
        if (!name) {
            this.showError('Пожалуйста, введите ваше имя');
            return false;
        }
        
        if (amount < 1) {
            this.showError('Минимальная сумма доната: $1');
            return false;
        }
        
        return true;
    }
    
    createPaymentModal() {
        this.modal = document.createElement('div');
        this.modal.className = 'stripe-modal';
        this.modal.innerHTML = `
            <div class="stripe-modal-content">
                <div class="stripe-modal-header">
                    <h3 data-translate="donation_pay">Оплатить</h3>
                    <button class="stripe-modal-close" onclick="donationSystem.closePaymentModal()">&times;</button>
                </div>
                
                <div class="payment-status" id="payment-status-modal" style="display: none;"></div>
                
                <form id="payment-form-modal">
                    <div class="input-group">
                        <label data-translate="donation_card_number">Номер карты</label>
                        <div class="stripe-element" id="card-element-modal"></div>
                    </div>
                    
                                                        <button type="submit" class="donate-btn" id="submit-button-modal" disabled>
                        <span data-translate="donation_processing">Обработка платежа...</span>
                    </button>
                </form>
            </div>
        `;
        
        // Привязываем обработчик формы
        const form = this.modal.querySelector('#payment-form-modal');
        console.log('🔧 Found payment form:', form);
        
        if (form) {
            form.addEventListener('submit', (e) => {
                console.log('📝 Form submit event triggered');
                e.preventDefault();
                this.handlePayment();
            });
            console.log('✅ Form submit handler attached');
        } else {
            console.error('❌ Payment form not found');
        }
        
        // Привязываем обработчик клика на кнопку
        const submitButton = this.modal.querySelector('#submit-button-modal');
        console.log('🔧 Found submit button:', submitButton);
        
        if (submitButton) {
            submitButton.addEventListener('click', (e) => {
                console.log('🔘 Submit button clicked');
                e.preventDefault();
                this.handlePayment();
            });
            console.log('✅ Submit button click handler attached');
        } else {
            console.error('❌ Submit button not found');
        }
    }
    
    async initStripeElements() {
        if (!this.stripe) {
            console.error('❌ Stripe not initialized');
            return;
        }
        
        try {
            console.log('🔧 Initializing Stripe Elements...');
            
            // Проверяем, существует ли элемент
            const cardElement = document.getElementById('card-element-modal');
            if (!cardElement) {
                console.error('❌ Card element not found in DOM');
                return;
            }
            console.log('✅ Card element found:', cardElement);
            
            this.elements = this.stripe.elements();
            this.cardElement = this.elements.create('card', {
                style: {
                    base: {
                        fontSize: '16px',
                        color: '#424770',
                        '::placeholder': {
                            color: '#aab7c4',
                        },
                    },
                    invalid: {
                        color: '#9e2146',
                    },
                },
            });
            
            this.cardElement.mount('#card-element-modal');
            
            // Обработчик изменений
            this.cardElement.on('change', (event) => {
                const submitButton = document.getElementById('submit-button-modal');
                if (submitButton) {
                    submitButton.disabled = event.error || !event.complete;
                }
            });
            
            console.log('✅ Stripe Elements initialized successfully');
        } catch (error) {
            console.error('❌ Error initializing Stripe Elements:', error);
        }
    }
    
    async createPaymentIntent() {
        try {
            this.showStatus('processing', 'Создание платежа...');
            
            const formData = {
                amount: this.selectedAmount,
                currency: this.selectedCurrency,
                name: document.querySelector('.donation-name').value.trim(),
                email: document.querySelector('.donation-email').value.trim()
            };
            
            const response = await fetch('/api/create-payment-intent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });
            
            const data = await response.json();
            
            console.log('📊 Payment Intent response:', data);
            
            if (data.success) {
                this.currentPaymentIntent = data.client_secret;
                console.log('✅ Payment Intent created with secret:', data.client_secret);
                this.showStatus('success', 'Платеж готов к обработке');
            } else {
                this.showStatus('error', data.message || 'Ошибка создания платежа');
                console.error('❌ Payment Intent creation failed:', data.message);
            }
        } catch (error) {
            this.showStatus('error', 'Ошибка сети');
            console.error('❌ Error creating Payment Intent:', error);
        }
    }
    
    async handlePayment() {
        console.log('💳 Starting payment processing...');
        
        if (this.isProcessing) {
            console.log('⚠️ Payment already processing');
            return;
        }
        
        if (!this.currentPaymentIntent) {
            console.error('❌ No payment intent available');
            this.showStatus('error', 'Ошибка: платеж не инициализирован');
            return;
        }
        
        this.isProcessing = true;
        this.showStatus('processing', 'Обработка платежа...');
        
        try {
            console.log('🔧 Confirming card payment with Stripe...');
            const result = await this.stripe.confirmCardPayment(this.currentPaymentIntent, {
                payment_method: {
                    card: this.cardElement,
                    billing_details: {
                        name: document.querySelector('.donation-name').value.trim(),
                        email: document.querySelector('.donation-email').value.trim()
                    }
                }
            });
            
            console.log('📊 Payment result:', result);
            
            if (result.error) {
                this.showStatus('error', result.error.message);
                console.error('❌ Payment failed:', result.error);
                this.showNotification('error', 'Ошибка платежа', result.error.message);
            } else {
                console.log('✅ Payment intent status:', result.paymentIntent.status);
                if (result.paymentIntent.status === 'succeeded') {
                    this.showStatus('success', 'Платеж успешно обработан!');
                    console.log('✅ Payment succeeded');
                    
                    // Показываем уведомление об успешном платеже
                    this.showNotification('success', 'Платеж успешен!', 'Ваш платеж был успешно обработан.');
                    
                    // Уведомляем Django backend об успешном платеже
                    await this.confirmPayment(result.paymentIntent.id);
                    
                    // Закрываем модальное окно через 4 секунды (больше времени для чтения)
                    setTimeout(() => {
                        this.closePaymentModal();
                        this.resetForm();
                    }, 4000);
                } else {
                    this.showStatus('error', `Статус платежа: ${result.paymentIntent.status}`);
                    console.log('⚠️ Payment not succeeded, status:', result.paymentIntent.status);
                }
            }
        } catch (error) {
            this.showStatus('error', 'Ошибка обработки платежа');
            console.error('❌ Error handling payment:', error);
        } finally {
            this.isProcessing = false;
            console.log('🔚 Payment processing finished');
        }
    }
    
    async confirmPayment(paymentIntentId) {
        try {
            console.log('📡 Confirming payment with Django backend...');
            this.showStatus('processing', 'Сохранение данных платежа...');
            
            const response = await fetch('/api/confirm-payment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    payment_intent_id: paymentIntentId
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log('✅ Payment confirmed with Django backend');
                this.showStatus('success', 'Платеж сохранен! Благодарственное письмо отправлено на ваш email.');
                
                // Показываем уведомление о благодарственном письме
                this.showNotification('success', 'Спасибо за поддержку!', 'Благодарственное письмо отправлено на ваш email.');
            } else {
                console.warn('⚠️ Payment confirmation failed:', data.message);
                this.showStatus('warning', 'Платеж обработан, но возникли проблемы с сохранением данных.');
                this.showNotification('warning', 'Внимание', 'Платеж обработан, но возникли проблемы с сохранением данных.');
            }
        } catch (error) {
            console.error('❌ Error confirming payment with Django backend:', error);
            this.showStatus('warning', 'Платеж обработан, но возникли проблемы с сохранением данных.');
            this.showNotification('warning', 'Внимание', 'Платеж обработан, но возникли проблемы с сохранением данных.');
        }
    }
    
    showStatus(type, message) {
        console.log(`📊 Showing status: ${type} - ${message}`);
        const statusElement = document.getElementById('payment-status-modal');
        if (statusElement) {
            statusElement.className = `payment-status ${type}`;
            statusElement.textContent = message;
            statusElement.style.display = 'block';
            console.log('✅ Status updated in modal');
        } else {
            console.warn('⚠️ Status element not found');
        }
    }
    
    showError(message) {
        // Простое уведомление об ошибке
        alert(message);
    }
    
    showNotification(type, title, message) {
        // Создаем красивое уведомление
        const notification = document.createElement('div');
        notification.className = `donation-notification ${type}`;
        notification.innerHTML = `
            <div class="notification-header">
                <span class="notification-title">${title}</span>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">&times;</button>
            </div>
            <div class="notification-message">${message}</div>
        `;
        
        // Добавляем в body
        document.body.appendChild(notification);
        
        // Автоматически удаляем через 5 секунд
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
        
        console.log(`📢 Notification shown: ${type} - ${title}: ${message}`);
    }
    
    closePaymentModal() {
        if (this.modal && this.modal.parentNode) {
            this.modal.parentNode.removeChild(this.modal);
        }
        
        if (this.cardElement) {
            this.cardElement.destroy();
            this.cardElement = null;
        }
        
        this.currentPaymentIntent = null;
        this.isProcessing = false;
    }
    
    resetForm() {
        // Сбрасываем форму
        document.querySelector('.donation-name').value = '';
        document.querySelector('.donation-email').value = '';
        this.selectAmount(5);
    }
    
    getCSRFToken() {
        const token = document.querySelector('meta[name="csrf-token"]');
        return token ? token.getAttribute('content') : '';
    }
    
    // Метод для обновления переводов
    updateTranslations() {
        if (window.localizationService) {
            const elements = this.modal?.querySelectorAll('[data-translate]');
            if (elements) {
                elements.forEach(element => {
                    const key = element.getAttribute('data-translate');
                    const translation = window.localizationService.getText(key);
                    if (translation) {
                        element.textContent = translation;
                    }
                });
            }
        }
    }
}

// Глобальная переменная для доступа к системе донатов
let donationSystem;

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔧 DonationSystem: DOM loaded, initializing...');
    donationSystem = new DonationSystem();
});

// Интеграция с системой локализации
if (window.onLanguageChanged) {
    const originalOnLanguageChanged = window.onLanguageChanged;
    window.onLanguageChanged = function() {
        originalOnLanguageChanged();
        if (donationSystem) {
            donationSystem.updateTranslations();
        }
    };
} 