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
        
        // Крипто-платежи
        this.paymentMethod = 'card'; // 'card' или 'crypto'
        this.selectedCryptoCurrency = 'USDT';
        this.currentCryptoOrderId = null;
        this.statusCheckInterval = null;
        this.cryptoCurrencies = [];
        
        this.init();
    }
    
    async init() {
        console.log('🔧 DonationSystem: Initializing...');
        
        // Инициализируем Stripe
        await this.initStripe();
        
        // Загружаем криптовалюты
        await this.loadCryptoCurrencies();
        
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
                if (this.paymentMethod === 'crypto') {
                    this.processCryptoPayment();
                } else {
                    this.showPaymentModal();
                }
            }
            
            // Обработчик переключения способа оплаты
            if (e.target.name === 'payment-method') {
                console.log('🔄 Payment method changed:', e.target.value);
                this.switchPaymentMethod(e.target.value);
            }
            
            // Обработчик копирования адреса
            if (e.target.closest('.copy-address-btn')) {
                e.preventDefault();
                this.copyAddressToClipboard();
            }
        });
        
        // Обработчик для поля ввода суммы
        document.addEventListener('input', (e) => {
            if (e.target.classList.contains('amount-input')) {
                console.log('📝 Amount input changed:', e.target.value);
                this.selectedAmount = parseFloat(e.target.value) || 0;
                this.updateAmountSelection();
            }
            
            // Обработчик выбора криптовалюты
            if (e.target.classList.contains('crypto-currency-select')) {
                console.log('🪙 Crypto currency changed:', e.target.value);
                this.selectedCryptoCurrency = e.target.value;
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
            this.showError(window.t('donation_enter_name', 'Пожалуйста, введите ваше имя'));
            return false;
        }
        
        if (amount < 1) {
            this.showError(window.t('donation_min_amount_error', 'Минимальная сумма доната: $1'));
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
                    <h3 data-translate="donation_pay">${window.t ? window.t('donation_pay', 'Оплатить') : 'Оплатить'}</h3>
                    <button class="stripe-modal-close" onclick="donationSystem.closePaymentModal()">&times;</button>
                </div>
                
                <div class="payment-status" id="payment-status-modal" style="display: none;"></div>
                
                <form id="payment-form-modal">
                    <div class="input-group">
                        <label data-translate="donation_card_number">${window.t ? window.t('donation_card_number', 'Номер карты') : 'Номер карты'}</label>
                        <div class="stripe-element" id="card-element-modal"></div>
                    </div>
                    
                                                        <button type="submit" class="donate-btn" id="submit-button-modal" disabled>
                        <span data-translate="donation_processing">${window.t ? window.t('donation_processing', 'Обработка платежа...') : 'Обработка платежа...'}</span>
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
            
            // Создаем Elements с английской локалью
            this.elements = this.stripe.elements({ locale: 'en' });
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
            this.showStatus('processing', window.t('donation_creating_payment', 'Создание платежа...'));
            
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
                this.showStatus('success', window.t('donation_payment_ready', 'Платеж готов к обработке'));
            } else {
                this.showStatus('error', data.message || window.t('donation_creation_error', 'Ошибка создания платежа'));
                console.error('❌ Payment Intent creation failed:', data.message);
            }
        } catch (error) {
            this.showStatus('error', window.t('donation_network_error', 'Ошибка сети'));
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
            this.showStatus('error', window.t('donation_not_initialized', 'Ошибка: платеж не инициализирован'));
            return;
        }
        
        this.isProcessing = true;
        this.showStatus('processing', window.t('donation_processing', 'Обработка платежа...'));
        
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
                    this.showNotification('error', window.t('donation_payment_error', 'Ошибка платежа'), result.error.message);
            } else {
                console.log('✅ Payment intent status:', result.paymentIntent.status);
                if (result.paymentIntent.status === 'succeeded') {
                    this.showStatus('success', window.t('donation_success_processed', 'Платеж успешно обработан!'));
                    console.log('✅ Payment succeeded');
                    
                    // Показываем уведомление об успешном платеже
                    this.showNotification('success', window.t('donation_payment_successful', 'Платеж успешен!'), window.t('donation_payment_processed', 'Ваш платеж был успешно обработан.'));
                    
                    // Уведомляем Django backend об успешном платеже
                    await this.confirmPayment(result.paymentIntent.id);
                    
                    // Закрываем модальное окно через 4 секунды (больше времени для чтения)
                    setTimeout(() => {
                        this.closePaymentModal();
                        this.resetForm();
                    }, 4000);
                } else {
                    this.showStatus('error', `${window.t('donation_status', 'Статус платежа')}: ${result.paymentIntent.status}`);
                    console.log('⚠️ Payment not succeeded, status:', result.paymentIntent.status);
                }
            }
        } catch (error) {
            this.showStatus('error', window.t('donation_processing_error', 'Ошибка обработки платежа'));
            console.error('❌ Error handling payment:', error);
        } finally {
            this.isProcessing = false;
            console.log('🔚 Payment processing finished');
        }
    }
    
    async confirmPayment(paymentIntentId) {
        try {
            console.log('📡 Confirming payment with Django backend...');
            this.showStatus('processing', window.t('donation_saving_data', 'Сохранение данных платежа...'));
            
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
                this.showStatus('success', window.t('donation_saved_email_sent', 'Платеж сохранен! Благодарственное письмо отправлено на ваш email.'));
                
                // Показываем уведомление о благодарственном письме
                this.showNotification('success', window.t('donation_thanks_support', 'Спасибо за поддержку!'), window.t('donation_thanks_email', 'Благодарственное письмо отправлено на ваш email.'));
            } else {
                console.warn('⚠️ Payment confirmation failed:', data.message);
                this.showStatus('warning', window.t('donation_partial_success', 'Платеж обработан, но возникли проблемы с сохранением данных.'));
                this.showNotification('warning', window.t('donation_warning', 'Внимание'), window.t('donation_partial_success', 'Платеж обработан, но возникли проблемы с сохранением данных.'));
            }
        } catch (error) {
            console.error('❌ Error confirming payment with Django backend:', error);
            this.showStatus('warning', window.t('donation_partial_success', 'Платеж обработан, но возникли проблемы с сохранением данных.'));
            this.showNotification('warning', window.t('donation_warning', 'Внимание'), window.t('donation_partial_success', 'Платеж обработан, но возникли проблемы с сохранением данных.'));
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
    
    // ==================== Крипто-платежи ====================
    
    async loadCryptoCurrencies() {
        try {
            console.log('🪙 Loading crypto currencies...');
            const response = await fetch('/api/donation/crypto-currencies');
            const data = await response.json();
            
            if (data.success && data.currencies) {
                this.cryptoCurrencies = data.currencies;
                console.log('✅ Crypto currencies loaded:', this.cryptoCurrencies);
            } else {
                console.warn('⚠️ Failed to load crypto currencies');
            }
        } catch (error) {
            console.error('❌ Error loading crypto currencies:', error);
        }
    }
    
    switchPaymentMethod(method) {
        console.log('🔄 Switching payment method to:', method);
        this.paymentMethod = method;
        
        // Обновляем UI
        const cryptoSelector = document.querySelector('.crypto-currency-selector');
        const cryptoDetails = document.querySelector('.crypto-payment-details');
        
        // Обновляем визуальное выделение радио-кнопок
        document.querySelectorAll('.payment-method-option').forEach(option => {
            const radio = option.querySelector('input[type="radio"]');
            if (radio && radio.value === method) {
                option.classList.add('selected');
            } else {
                option.classList.remove('selected');
            }
        });
        
        if (method === 'crypto') {
            if (cryptoSelector) cryptoSelector.style.display = 'block';
            // Скрываем детали до создания платежа
            if (cryptoDetails) cryptoDetails.style.display = 'none';
        } else {
            if (cryptoSelector) cryptoSelector.style.display = 'none';
            if (cryptoDetails) cryptoDetails.style.display = 'none';
            // Останавливаем polling если был запущен
            this.stopStatusPolling();
        }
        
        console.log('✅ Payment method switched to:', method);
    }
    
    async processCryptoPayment() {
        if (this.isProcessing) return;
        
        // Валидация
        if (!this.validateForm()) {
            return;
        }
        
        this.isProcessing = true;
        console.log('🪙 Processing crypto payment...');
        
        try {
            // Показываем статус создания
            this.showNotification('info', 
                window.t('donation_processing', 'Обработка...'),
                window.t('donation_creating_payment', 'Создание платежа...')
            );
            
            // Получаем данные формы
            const formData = {
                amount: this.selectedAmount,
                crypto_currency: this.selectedCryptoCurrency,
                name: document.querySelector('.donation-name').value.trim(),
                email: document.querySelector('.donation-email').value.trim(),
                initData: window.Telegram?.WebApp?.initData || ''
            };
            
            console.log('📡 Creating crypto payment with data:', formData);
            
            // Создаем крипто-платеж
            const response = await fetch('/api/donation/crypto/create-payment/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });
            
            const data = await response.json();
            console.log('📊 Crypto payment response:', data);
            
            if (data.success) {
                this.currentCryptoOrderId = data.order_id;
                
                // Показываем детали платежа
                this.displayCryptoPaymentDetails(data);
                
                // Запускаем проверку статуса
                this.startStatusPolling();
                
                this.showNotification('success',
                    window.t('crypto_donation_created', 'Крипто-платеж создан'),
                    window.t('send_crypto_to_address', 'Отправьте криптовалюту на указанный адрес')
                );
            } else {
                throw new Error(data.message || 'Failed to create crypto payment');
            }
        } catch (error) {
            console.error('❌ Error processing crypto payment:', error);
            this.showNotification('error',
                window.t('donation_payment_error', 'Ошибка платежа'),
                error.message || window.t('donation_network_error', 'Ошибка сети')
            );
        } finally {
            this.isProcessing = false;
        }
    }
    
    displayCryptoPaymentDetails(data) {
        console.log('📊 Displaying crypto payment details:', data);
        
        const detailsContainer = document.querySelector('.crypto-payment-details');
        if (!detailsContainer) {
            console.error('❌ Crypto payment details container not found');
            return;
        }
        
        // Показываем контейнер
        detailsContainer.style.display = 'block';
        
        // Обновляем сумму
        const amountValue = detailsContainer.querySelector('.crypto-amount-value');
        if (amountValue) {
            amountValue.textContent = `${data.crypto_amount} ${data.crypto_currency}`;
        }
        
        // Обновляем адрес
        const addressInput = detailsContainer.querySelector('.crypto-address-input');
        if (addressInput) {
            addressInput.value = data.payment_address;
        }
        
        // Генерируем QR-код
        this.generateQRCode(data.payment_address);
        
        // Устанавливаем начальный статус
        this.updateCryptoStatus('waiting', window.t('waiting_for_payment', 'Ожидание оплаты...'));
        
        // Прокручиваем к деталям
        detailsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        console.log('✅ Crypto payment details displayed');
    }
    
    generateQRCode(address) {
        console.log('📱 Generating QR code for address:', address);
        
        const canvas = document.querySelector('.qr-code-canvas');
        if (!canvas) {
            console.error('❌ QR code canvas not found');
            return;
        }
        
        // Проверяем наличие библиотеки QRCode
        if (typeof QRCode === 'undefined') {
            console.error('❌ QRCode library not loaded');
            // Скрываем контейнер QR-кода если библиотека не загружена
            const qrContainer = document.querySelector('.qr-code-container');
            if (qrContainer) qrContainer.style.display = 'none';
            return;
        }
        
        try {
            // Очищаем canvas
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Генерируем QR-код
            QRCode.toCanvas(canvas, address, {
                width: 200,
                margin: 2,
                color: {
                    dark: '#000000',
                    light: '#ffffff'
                }
            }, (error) => {
                if (error) {
                    console.error('❌ Error generating QR code:', error);
                } else {
                    console.log('✅ QR code generated successfully');
                }
            });
        } catch (error) {
            console.error('❌ Error in QR code generation:', error);
        }
    }
    
    copyAddressToClipboard() {
        const addressInput = document.querySelector('.crypto-address-input');
        if (!addressInput) {
            console.error('❌ Address input not found');
            return;
        }
        
        const address = addressInput.value;
        console.log('📋 Copying address to clipboard:', address);
        
        // Копируем в буфер обмена
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(address)
                .then(() => {
                    console.log('✅ Address copied to clipboard');
                    this.showNotification('success',
                        window.t('address_copied', 'Адрес скопирован!'),
                        window.t('address_copied', 'Адрес скопирован в буфер обмена')
                    );
                })
                .catch(err => {
                    console.error('❌ Failed to copy address:', err);
                    // Fallback: выделяем текст
                    addressInput.select();
                    document.execCommand('copy');
                });
        } else {
            // Fallback для старых браузеров
            addressInput.select();
            addressInput.setSelectionRange(0, 99999); // Для мобильных
            document.execCommand('copy');
            console.log('✅ Address copied using fallback method');
            this.showNotification('success',
                window.t('address_copied', 'Адрес скопирован!'),
                ''
            );
        }
    }
    
    startStatusPolling() {
        console.log('🔄 Starting status polling for order:', this.currentCryptoOrderId);
        
        // Останавливаем предыдущий polling если был
        this.stopStatusPolling();
        
        // Проверяем статус каждые 15 секунд
        this.statusCheckInterval = setInterval(() => {
            this.checkCryptoPaymentStatus();
        }, 15000);
        
        // Первая проверка сразу
        this.checkCryptoPaymentStatus();
    }
    
    stopStatusPolling() {
        if (this.statusCheckInterval) {
            console.log('⏹️ Stopping status polling');
            clearInterval(this.statusCheckInterval);
            this.statusCheckInterval = null;
        }
    }
    
    async checkCryptoPaymentStatus() {
        if (!this.currentCryptoOrderId) {
            console.warn('⚠️ No crypto order ID to check');
            return;
        }
        
        try {
            console.log('🔍 Checking crypto payment status for:', this.currentCryptoOrderId);
            
            const response = await fetch(`/api/donation/crypto/status/${this.currentCryptoOrderId}/`);
            const data = await response.json();
            
            console.log('📊 Status check response:', data);
            
            if (data.success) {
                const status = data.status;
                const coingateStatus = data.coingate_status;
                
                console.log(`📊 Payment status: ${status}, CoinGate status: ${coingateStatus}`);
                
                // Обновляем UI в зависимости от статуса
                if (status === 'completed') {
                    this.updateCryptoStatus('completed', window.t('payment_confirmed', 'Оплата подтверждена!'));
                    this.stopStatusPolling();
                    
                    // Показываем уведомление об успехе
                    this.showNotification('success',
                        window.t('donation_payment_successful', 'Платеж успешен!'),
                        window.t('donation_thanks_support', 'Спасибо за поддержку!')
                    );
                    
                    // Сбрасываем форму через 3 секунды
                    setTimeout(() => {
                        this.resetCryptoPayment();
                        this.resetForm();
                    }, 3000);
                    
                } else if (status === 'failed' || coingateStatus === 'invalid' || coingateStatus === 'expired') {
                    this.updateCryptoStatus('failed', window.t('payment_failed', 'Платеж не выполнен'));
                    this.stopStatusPolling();
                    
                    this.showNotification('error',
                        window.t('donation_payment_error', 'Ошибка платежа'),
                        window.t('payment_expired', 'Платеж истек или недействителен')
                    );
                    
                } else if (coingateStatus === 'pending' || coingateStatus === 'confirming') {
                    this.updateCryptoStatus('confirming', window.t('payment_pending', 'Ожидание подтверждения в блокчейне...'));
                }
            }
        } catch (error) {
            console.error('❌ Error checking crypto payment status:', error);
        }
    }
    
    updateCryptoStatus(status, text) {
        console.log(`📊 Updating crypto status: ${status} - ${text}`);
        
        const statusIndicator = document.querySelector('.status-indicator');
        const statusText = document.querySelector('.status-text');
        
        if (statusIndicator) {
            // Удаляем все классы статуса
            statusIndicator.classList.remove('waiting', 'confirming', 'completed', 'failed');
            // Добавляем новый класс
            statusIndicator.classList.add(status);
        }
        
        if (statusText) {
            statusText.textContent = text;
        }
        
        console.log('✅ Crypto status updated');
    }
    
    resetCryptoPayment() {
        console.log('🔄 Resetting crypto payment');
        
        // Останавливаем polling
        this.stopStatusPolling();
        
        // Скрываем детали платежа
        const detailsContainer = document.querySelector('.crypto-payment-details');
        if (detailsContainer) {
            detailsContainer.style.display = 'none';
        }
        
        // Очищаем данные
        this.currentCryptoOrderId = null;
        
        // Очищаем QR-код
        const canvas = document.querySelector('.qr-code-canvas');
        if (canvas) {
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
        
        console.log('✅ Crypto payment reset');
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