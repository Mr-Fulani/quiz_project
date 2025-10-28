/**
 * Система донатов для мини-приложения
 * Интегрируется с Django API и Stripe для обработки платежей
 */

// Создаем глобальный объект-контейнер для всей логики, чтобы избежать конфликтов и повторных объявлений.
// Этот блок выполнится только один раз, даже если скрипт будет загружен на страницу несколько раз.
if (!window.donationSystemGlobal) {
    window.donationSystemGlobal = {};

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
        this.paymentMethod = 'card'; // 'card' | 'crypto' | 'wallet'
        this.selectedCryptoCurrency = 'USDT';
        this.selectedWalletCurrency = 'USDT';
        this.currentCryptoOrderId = null;
        this.statusCheckInterval = null;
        this.cryptoCurrencies = [];
        
        this.init();
    }
    
    async init() {
        console.log('🔧 DonationSystem: Initializing...');
        
            // 1. Fetch all data in parallel to avoid race conditions
            const [stripeKeyData, appConfig, cryptoCurrencies] = await Promise.all([
                this.fetchStripeKey(),
                this.fetchAppConfig(),
                this.fetchCryptoCurrencies()
            ]);

            // 2. Initialize services and set properties
            this.initializeStripe(stripeKeyData);
            this.walletPayEnabled = !!(appConfig && appConfig.wallet_pay_enabled);
            this.cryptoCurrencies = cryptoCurrencies || [];
            
            // 3. Build the UI with all data available
            this.buildInitialUI();
            
            // 4. Bind events and set initial values
            this.bindEvents();
            this.setInitialValues();
            
            // Final UI translation update, as localization might load asynchronously
            this.updateTranslations();
            this.localizeCurrencyOptions(document.querySelector('.unified-currency-select'));

            console.log('✅ DonationSystem: Initialized successfully');
        }

        buildInitialUI() {
            console.log('🎨 Building initial UI...');
            if (this.walletPayEnabled) {
                this.ensureWalletPayUI();
            }
            this.ensureUnifiedCurrencySelector();
        this.removeLegacyCurrencySelectors();
            console.log('✅ Initial UI built.');
        }

        async fetchStripeKey() {
            try {
                const response = await fetch('/api/stripe-publishable-key');
                return await response.json();
            } catch (error) {
                console.error('❌ Error fetching Stripe key:', error);
                return null;
            }
        }

        initializeStripe(keyData) {
            if (keyData && keyData.publishable_key) {
                this.stripe = Stripe(keyData.publishable_key);
                console.log('✅ Stripe initialized with key:', keyData.publishable_key.substring(0, 20) + '...');
            } else {
                console.warn('⚠️ Stripe publishable key not available');
            }
        }

        async fetchAppConfig() {
            try {
                const res = await fetch('/api/get-config/');
                const cfg = await res.json();
                console.log('⚙️ App config loaded:', cfg);
                return cfg;
            } catch (e) {
                console.warn('⚠️ Failed to load app config:', e);
                return { wallet_pay_enabled: false };
            }
        }
        
        async fetchCryptoCurrencies() {
            try {
                console.log('🪙 Loading crypto currencies...');
                const response = await fetch('/api/donation/crypto-currencies');
                const data = await response.json();
                if (data.success && data.currencies) {
                    console.log('✅ Crypto currencies loaded:', data.currencies);
                    return data.currencies;
                }
                console.warn('⚠️ Failed to load crypto currencies');
                return [];
            } catch (error) {
                console.error('❌ Error loading crypto currencies:', error);
                return [];
            }
    }

    ensureUnifiedCurrencySelector() {
        // Используем контейнер из шаблона
        const container = document.getElementById('unified-currency-container');
        if (!container) return;
        const selectEl = container.querySelector('.unified-currency-select');
        if (!selectEl) return;

        // Назначаем обработчик один раз
        if (!selectEl.dataset.bound) {
            selectEl.addEventListener('change', (ev) => {
                this.selectedCryptoCurrency = ev.target.value;
                this.selectedWalletCurrency = ev.target.value;
                console.log('💱 Unified currency selected (ensure):', ev.target.value);
            });
            selectEl.dataset.bound = '1';
        }

        // Наполним опциями исходя из текущего состояния
        this.updateUnifiedCurrencyOptions();

        // Обновляем переводы (если есть) для label unified селектора
        this.updateTranslations();

        // Если на странице есть legacy h3 (например в шаблоне), скрываем его — используем unified label
        const legacyCrypto = document.querySelector('.crypto-currency-selector');
        if (legacyCrypto) {
            const legacyH3 = legacyCrypto.querySelector('h3');
            if (legacyH3) {
                legacyH3.style.display = 'none';
            }
        }
    }

    updateUnifiedCurrencyOptions() {
        const container = document.getElementById('unified-currency-container');
        if (!container) return;
        const selectEl = container.querySelector('.unified-currency-select');
        if (!selectEl) return;

        // Составляем список доступных валют: из загруженных crypto + дефолт
        const fallback = ['USDT', 'TON', 'BTC', 'DAI'];
        const available = (this.cryptoCurrencies && this.cryptoCurrencies.length)
            ? Array.from(new Set([...this.cryptoCurrencies.map(c => c.code), ...fallback]))
            : fallback;

        // Очистим и добавим
        selectEl.innerHTML = '';
        available.forEach(code => {
            const opt = document.createElement('option');
            opt.value = code;
            opt.textContent = code;
            selectEl.appendChild(opt);
        });

        // Если есть ранее выбранная валюта — установим её
        const preferred = this.selectedCryptoCurrency || this.selectedWalletCurrency;
        if (preferred) selectEl.value = preferred;

        // Попытка локализовать опции (ключи: usdt, usdc, busd, dai и т.д.)
        try {
            this.localizeCurrencyOptions(selectEl);
        } catch (err) {
            console.warn('⚠️ localizeCurrencyOptions failed:', err);
        }

        // Показываем контейнер, когда есть что выбирать
        container.style.display = 'block';
    }

    localizeCurrencyOptions(selectEl) {
        if (!selectEl) return;
        const options = Array.from(selectEl.options);
        options.forEach(opt => {
            const code = opt.value && opt.value.toLowerCase();
            if (!code) return;
            
            // Ключи переводов: usdt, usdc, busd, dai, ton, btc и т.д.
            const key = code;
            let text = null;
            
            // Пытаемся получить перевод
            if (window.t && typeof window.t === 'function') {
                try { text = window.t(key); } catch (e) { /* ignore */ }
            }
            if (!text && window.localizationService && typeof window.localizationService.getText === 'function') {
                text = window.localizationService.getText(key);
            }
            
            // Проверяем, что у нас есть перевод и он не совпадает с кодом
            if (text && text.toLowerCase() !== code && text !== opt.value) {
                // Если перевод уже содержит код в начале (например "USDT (Tether)"), используем его как есть
                if (text.toUpperCase().startsWith(opt.value.toUpperCase())) {
                    opt.textContent = text;
                } else {
                    // Иначе добавляем код в начало
                    opt.textContent = `${opt.value} (${text})`;
                }
            } else {
                // Если перевода нет или он совпадает с кодом - показываем только код
                opt.textContent = opt.value;
            }
        });
    }

    removeLegacyCurrencySelectors() {
        // Удаляем или скрываем старые селекторы, чтобы не было двух полей выбора валюты
        const legacy1 = document.querySelector('.crypto-currency-selector');
        if (legacy1 && legacy1.parentElement) {
            legacy1.parentElement.removeChild(legacy1);
            console.log('🧹 Removed legacy crypto-currency-selector');
        }

        const legacy2 = document.querySelector('.telegram-wallet-form .wallet-currency');
        if (legacy2 && legacy2.parentElement) {
            const parent = legacy2.parentElement;
            parent.removeChild(legacy2);
            // если контейнер currency-selector остался пустым — удалим и его label
            const currencyContainer = document.querySelector('.telegram-wallet-form .currency-selector');
            if (currencyContainer && currencyContainer.parentElement) {
                currencyContainer.parentElement.removeChild(currencyContainer);
                console.log('🧹 Removed legacy currency-selector container inside wallet form');
            }
            console.log('🧹 Removed legacy wallet-currency select inside wallet form');
        }
    }

    ensureWalletPayUI() {
        // Добавляем опцию метода оплаты "Telegram Wallet", если её ещё нет в DOM
        const methodsContainer = document.querySelector('.payment-methods');
            
        // Если контейнера ещё нет (динамический рендер), ждём его появление через MutationObserver
        if (!methodsContainer) {
            const observer = new MutationObserver((mutations, obs) => {
                const container = document.querySelector('.payment-methods');
                if (container) {
                    obs.disconnect();
                    // Немного даём времени на завершение рендера и затем повторяем установку UI
                    setTimeout(() => this.ensureWalletPayUI(), 50);
                }
            });
            observer.observe(document.body, { childList: true, subtree: true });
            return;
        }
            
            // Добавляем радиокнопку для Telegram Wallet
        const exists = methodsContainer.querySelector('input[name="payment-method"][value="wallet"]');
        if (!exists) {
            const label = document.createElement('label');
            label.className = 'payment-method-option';
            label.innerHTML = `
                <input type="radio" name="payment-method" value="wallet">
                <span>💎 Telegram Wallet</span>
            `;
            methodsContainer.appendChild(label);
                console.log('✅ Telegram Wallet payment option added');
            }
            
            // ВАЖНО: Больше не создаём отдельную .telegram-wallet-form
            // Wallet и Crypto используют один и тот же unified-currency-container
    }
    
    bindEvents() {
        console.log('🔧 DonationSystem: Binding events...');
        
        // Используем делегирование событий для динамически созданных элементов
        document.addEventListener('click', (e) => {
            // Явный делегированный обработчик для кнопки Wallet (на случай, если локальный обработчик не сработал)
            if (e.target.closest('[data-wallet-btn]')) {
                e.preventDefault();
                console.log('💎 Wallet button (delegated) clicked');
                this.paymentMethod = 'wallet';
                this.switchPaymentMethod('wallet');
                this.processTelegramWalletPayment();
                return;
            }
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
            
            // Обработчик для единственной primary кнопки доната
            if (e.target.closest('.donate-btn')) {
                console.log('💳 Primary donate button clicked');
                e.preventDefault();
                // Визуально скрываем/прячем дополнительные кнопки при обработке
                const walletForm = document.querySelector('.telegram-wallet-form');
                if (this.paymentMethod === 'crypto') {
                    this.processCryptoPayment();
                } else if (this.paymentMethod === 'wallet') {
                    // Если Wallet выбран — используем основной donate-btn как триггер
                    this.processTelegramWalletPayment();
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
            // показываем сообщение один раз
            if (!document.querySelector('.donation-name-error')) {
                this.showError(window.t('donation_enter_name', 'Пожалуйста, введите ваше имя'));
                // пометка, чтобы не дублировать alert при повторных вызовах
                const marker = document.createElement('div');
                marker.className = 'donation-name-error';
                marker.style.display = 'none';
                document.body.appendChild(marker);
                // удалим маркер через 3 секунды
                setTimeout(() => {
                    const m = document.querySelector('.donation-name-error');
                    if (m) m.remove();
                }, 3000);
            }
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
        // Дедупликация одинаковых ошибок в течение 2 секунд и отображение через красивый нотификатор
        try {
            const now = Date.now();
            if (!this._lastErrorMessage) this._lastErrorMessage = '';
            if (!this._lastErrorTime) this._lastErrorTime = 0;
            if (this._lastErrorMessage === message && (now - this._lastErrorTime) < 2000) {
                console.log('⚠️ Duplicate error suppressed:', message);
                return;
            }
            this._lastErrorMessage = message;
            this._lastErrorTime = now;
        } catch (err) {
            // ignore
        }

        // Показываем нотификацию вместо alert — не блокирует поток и меньше шансов на дубли
        this.showNotification('error', window.t ? window.t('donation_error', 'Ошибка') : 'Ошибка', message);
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
        // Обновляем переводы у всех динамически созданных элементов на странице
        try {
            const elements = document.querySelectorAll('[data-translate]');
            elements.forEach(element => {
                const key = element.getAttribute('data-translate');
                if (!key) return;
                // Сначала пытаемся использовать window.t (если подключена функция), затем localizationService
                if (window.t && typeof window.t === 'function') {
                    try {
                        const translated = window.t(key);
                        if (translated) element.textContent = translated;
                        return;
                    } catch (e) {
                        // ignore
                    }
                }

                if (window.localizationService && typeof window.localizationService.getText === 'function') {
                    const translation = window.localizationService.getText(key);
                    if (translation) element.textContent = translation;
                }
            });
        } catch (err) {
            console.warn('⚠️ updateTranslations failed:', err);
        }
    }
    
    // ==================== Крипто-платежи ====================
    
    switchPaymentMethod(method) {
        console.log('🔄 Switching payment method to:', method);
        this.paymentMethod = method;
        
        // Обновляем UI
        const unifiedContainer = document.getElementById('unified-currency-container');
        const cryptoDetails = document.querySelector('.crypto-payment-details');
        const walletForm = document.querySelector('.telegram-wallet-form');
        
        // Обновляем визуальное выделение радио-кнопок
        document.querySelectorAll('.payment-method-option').forEach(option => {
            const radio = option.querySelector('input[type="radio"]');
            if (radio && radio.value === method) {
                option.classList.add('selected');
            } else {
                option.classList.remove('selected');
            }
        });
        
            // Для crypto и wallet показываем ТОЛЬКО unified-currency-container
            // Разница только в том, какая кнопка будет обрабатывать платёж
            if (method === 'crypto' || method === 'wallet') {
                // Показываем селектор валюты для обоих методов
            if (unifiedContainer) unifiedContainer.style.display = 'block';
                // Скрываем детали платежа до его создания
            if (cryptoDetails) cryptoDetails.style.display = 'none';
                // Telegram Wallet форма не нужна - используем unified контейнер
            if (walletForm) walletForm.style.display = 'none';
        } else {
                // Card payment - прячем всё крипто-специфичное
            if (unifiedContainer) unifiedContainer.style.display = 'none';
            if (cryptoDetails) cryptoDetails.style.display = 'none';
            if (walletForm) walletForm.style.display = 'none';
            // Останавливаем polling если был запущен
            this.stopStatusPolling();
        }
        
        console.log('✅ Payment method switched to:', method);
    }

    async processTelegramWalletPayment() {
        if (this.isProcessing) return;
        if (!this.validateForm()) return;
        this.isProcessing = true;
        try {
            const formData = {
                amount: this.selectedAmount,
                currency: 'USDT',
                name: document.querySelector('.donation-name').value.trim(),
                telegram_id: window.currentUser?.telegram_id,
                source: 'mini_app'
            };

            const response = await fetch('/api/donation/wallet-pay/create-payment/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            const data = await response.json();
            if (data.success) {
                if (window.Telegram?.WebApp && data.direct_pay_link) {
                    window.Telegram.WebApp.openTelegramLink(data.direct_pay_link);
                } else if (data.pay_link) {
                    window.open(data.pay_link, '_blank');
                }
                this.showNotification('info', 'Ожидание оплаты', 'Завершите оплату в Telegram Wallet');
            } else {
                throw new Error(data.message || 'Failed to create Wallet Pay payment');
            }
        } catch (e) {
            console.error('❌ Wallet Pay error:', e);
            this.showNotification('error', 'Ошибка', e.message || 'Wallet Pay недоступен');
        } finally {
            this.isProcessing = false;
        }
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

    // Функция-инициализатор, которую можно безопасно вызывать многократно.
    // Она будет создавать новый экземпляр DonationSystem при каждой загрузке страницы.
    window.donationSystemGlobal.initialize = function() {
        // Проверяем, что мы на странице с донатами, прежде чем что-либо делать.
        if (document.querySelector('.donation-container')) {
            console.log('🔧 DonationSystem: DOM loaded or changed, initializing new instance...');
            // Создаем новый экземпляр, который проведет всю необходимую настройку.
            window.donationSystemGlobal.instance = new DonationSystem();
        } else {
            console.log('🧐 Donation container not found, skipping initialization.');
        }
    };

    // --- НАСТРОЙКА ГЛОБАЛЬНЫХ ОБРАБОТЧИКОВ (выполняется один раз) ---
    
    // 1. Инициализация при первой загрузке страницы.
    document.addEventListener('DOMContentLoaded', () => {
        console.log("🚀 DOMContentLoaded -> Initializing Donation System");
        window.donationSystemGlobal.initialize();
    });

    // 2. Отслеживание изменений DOM для SPA-навигации.
    // Перехватываем момент после замены контента в loadPage().
    // Это более надежный подход, чем MutationObserver.
    
    // Сохраняем оригинальный loadPage
    if (window.loadPage) {
        const originalLoadPage = window.loadPage;
        window.loadPage = function(...args) {
            console.log('🔄 [DonationSystem] loadPage intercepted, will re-init after completion');
            
            // Вызываем оригинальную функцию
            const result = originalLoadPage.apply(this, args);
            
            // После loadPage проверяем, нужно ли переинициализировать donation system
            // Используем Promise.resolve для обработки как синхронных, так и асинхронных результатов
            Promise.resolve(result).then(() => {
                // Даем время на полную загрузку и рендеринг
                setTimeout(() => {
                    if (document.querySelector('.donation-container')) {
                        console.log('✅ [DonationSystem] Donation container found after page load, re-initializing...');
                        window.donationSystemGlobal.initialize();
                    }
                }, 300);
            });
            
            return result;
        };
        console.log('✅ loadPage intercepted for donation system re-initialization');
    }

    // 3. Интеграция с системой локализации (перехват смены языка).
    // Это запасной вариант, если loadPage не сработает
if (window.onLanguageChanged) {
    const originalOnLanguageChanged = window.onLanguageChanged;
    window.onLanguageChanged = function() {
            console.log('🌐 [DonationSystem] Language change detected');
        originalOnLanguageChanged();
            
            // Переинициализируем через небольшую задержку
            setTimeout(() => {
                if (document.querySelector('.donation-container')) {
                    console.log('✅ [DonationSystem] Re-initializing after language change');
                    window.donationSystemGlobal.initialize();
                }
            }, 400);
        };
    }

    console.log('✅ DonationSystemGlobal setup complete. Listeners are active.');
} 