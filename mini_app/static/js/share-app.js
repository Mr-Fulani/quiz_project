/**
 * Функциональность "Поделиться приложением"
 * Включает генерацию QR-кода и копирование ссылки
 * Ссылка ведет на Telegram бота @mr_proger_bot
 */

class ShareApp {
    constructor() {
        // Используем ссылку на Telegram бота вместо браузерной версии
        this.appUrl = 'https://t.me/mr_proger_bot';
        this.qrCodeContainer = null;
        this.modal = null;
        this.socialModal = null; // Модальное окно с соцсетями
        this.init();
    }

    init() {
        this.createModal();
        this.bindEvents();
    }

    createModal() {
        // Создаем модальное окно для QR-кода
        this.modal = document.createElement('div');
        this.modal.className = 'share-modal';
        this.modal.innerHTML = `
            <div class="share-modal-content">
                <div class="share-modal-header">
                    <h3 data-translate="share_app">Поделиться приложением</h3>
                    <button class="share-modal-close" onclick="shareApp.closeModal()">&times;</button>
                </div>
                <div class="share-modal-body">
                    <!-- Превью приложения -->
                    <div class="app-preview">
                        <div class="app-preview-image">
                            <img src="/static/images/logo.png" alt="Quiz App Logo" class="app-logo">
                        </div>
                        <div class="app-preview-info">
                            <h4 class="app-name" data-translate="app_name">Quiz Mini App</h4>
                            <p class="app-description" data-translate="app_description">Educational quiz app for learning various topics</p>
                            <div class="app-features">
                                <span class="feature-tag" data-translate="app_features_learning">📚 Learning</span>
                                <span class="feature-tag" data-translate="app_features_quizzes">🎯 Quizzes</span>
                                <span class="feature-tag" data-translate="app_features_achievements">🏆 Achievements</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- QR-код -->
                    <div class="qr-section">
                        <h4 data-translate="qr_code">QR-код для быстрого доступа</h4>
                        <div id="qr-code-container"></div>
                    </div>
                    
                    <!-- Действия -->
                    <div class="share-actions">
                        <button class="share-btn copy-link-btn" onclick="shareApp.copyLink()">
                            <svg viewBox="0 0 24 24" fill="currentColor" class="btn-icon">
                                <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                            </svg>
                            <span data-translate="copy_link">Копировать ссылку</span>
                        </button>
                        <button class="share-btn share-social-btn" onclick="shareApp.shareToSocial()">
                            <svg viewBox="0 0 24 24" fill="currentColor" class="btn-icon">
                                <path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/>
                            </svg>
                            <span data-translate="share_social">Поделиться в соцсетях</span>
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(this.modal);
    }

    bindEvents() {
        // Находим кнопку "Поделиться приложением" и добавляем обработчик
        const shareButton = document.querySelector('.share-app-btn');
        console.log('🔍 ShareApp: Looking for share button...', shareButton);
        
        if (shareButton) {
            console.log('✅ ShareApp: Share button found, adding event listener');
            shareButton.addEventListener('click', () => {
                console.log('🎯 ShareApp: Button clicked!');
                this.showQRCode();
            });
        } else {
            console.warn('⚠️ ShareApp: Share button not found!');
        }

        // Добавляем обработчик для обновления переводов и закрытия модального окна при переключении языка
        if (window.onLanguageChanged) {
            const originalHandler = window.onLanguageChanged;
            window.onLanguageChanged = (language, translations) => {
                console.log('🔄 ShareApp: Language changed, updating translations');
                
                // Закрываем модальное окно при изменении языка
                if (this.modal && this.modal.style.display === 'flex') {
                    console.log('🔄 ShareApp: Language changed, closing modal');
                    this.closeModal();
                }
                
                // Обновляем переводы
                this.refreshTranslations();
                
                // Вызываем оригинальный обработчик, если он есть
                if (originalHandler) {
                    originalHandler(language, translations);
                }
            };
        } else {
            window.onLanguageChanged = (language, translations) => {
                console.log('🔄 ShareApp: Language changed, updating translations');
                
                // Закрываем модальное окно при изменении языка
                if (this.modal && this.modal.style.display === 'flex') {
                    console.log('🔄 ShareApp: Language changed, closing modal');
                    this.closeModal();
                }
                
                // Обновляем переводы
                this.refreshTranslations();
            };
        }

        // Добавляем глобальные обработчики для автоматического закрытия модального окна
        this.addGlobalEventListeners();
    }

    async showQRCode() {
        console.log('🚀 ShareApp: Showing QR code modal...');
        try {
            // Показываем модальное окно
            this.modal.style.display = 'flex';
            console.log('✅ ShareApp: Modal displayed');
            
            // Добавляем обработчики для модального окна
            this.addModalEventListeners();
            
            // Генерируем QR-код
            await this.generateQRCode();
            console.log('✅ ShareApp: QR code generated');
            
            // Обновляем переводы в модальном окне
            this.updateTranslations();
            console.log('✅ ShareApp: Translations updated');
            
            // Принудительно обновляем переводы еще раз через небольшую задержку
            setTimeout(() => {
                this.updateTranslations();
                console.log('✅ ShareApp: Translations updated again');
            }, 100);
        } catch (error) {
            console.error('❌ ShareApp: Error showing QR code:', error);
        }
    }

    async generateQRCode() {
        const container = document.getElementById('qr-code-container');
        if (!container) return;

        // Очищаем контейнер
        container.innerHTML = '';

        try {
            // Используем библиотеку qrcode.js для генерации QR-кода
            if (typeof QRCode !== 'undefined') {
                // Создаем canvas элемент
                const canvas = document.createElement('canvas');
                container.appendChild(canvas);
                
                QRCode.toCanvas(canvas, this.appUrl, {
                    width: 200,
                    margin: 2,
                    color: {
                        dark: '#000000',
                        light: '#ffffff'
                    }
                }, function (error) {
                    if (error) {
                        console.error('Ошибка генерации QR-кода:', error);
                        container.innerHTML = '<p>Ошибка генерации QR-кода</p>';
                    }
                });
            } else {
                // Fallback: создаем простой QR-код через API
                await this.generateQRCodeViaAPI(container);
            }
        } catch (error) {
            console.error('Ошибка генерации QR-кода:', error);
            container.innerHTML = '<p>Ошибка генерации QR-кода</p>';
        }
    }

    async generateQRCodeViaAPI(container) {
        // Используем бесплатный API для генерации QR-кода
        const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(this.appUrl)}`;
        
        const img = document.createElement('img');
        img.src = qrApiUrl;
        img.alt = 'QR Code';
        img.style.width = '200px';
        img.style.height = '200px';
        img.style.border = '1px solid #ddd';
        img.style.borderRadius = '8px';
        
        container.appendChild(img);
    }

    async copyLink() {
        try {
            await navigator.clipboard.writeText(this.appUrl);
            this.showCopySuccess();
        } catch (error) {
            console.error('Ошибка копирования ссылки:', error);
            // Fallback для старых браузеров
            this.fallbackCopyLink();
        }
    }

    fallbackCopyLink() {
        const textArea = document.createElement('textarea');
        textArea.value = this.appUrl;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        this.showCopySuccess();
    }

    showCopySuccess() {
        const button = document.querySelector('.copy-link-btn');
        if (button) {
            const originalText = button.innerHTML;
            button.innerHTML = '<span data-translate="link_copied">Ссылка скопирована!</span>';
            button.style.backgroundColor = '#28a745';
            
            setTimeout(() => {
                button.innerHTML = originalText;
                button.style.backgroundColor = '';
            }, 2000);
        }
    }

    async copyLinkForInstagram(event) {
        event.preventDefault();
        
        try {
            await navigator.clipboard.writeText(this.appUrl);
            
            // Показываем уведомление
            this.showInstagramCopyNotification();
            
            // Открываем Instagram (если возможно)
            setTimeout(() => {
                window.open('https://www.instagram.com/', '_blank');
            }, 500);
        } catch (error) {
            console.error('Ошибка копирования ссылки для Instagram:', error);
            // Fallback
            this.fallbackCopyLink();
            this.showInstagramCopyNotification();
        }
    }

    showInstagramCopyNotification() {
        // Создаем временное уведомление
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 255, 0, 0.95);
            color: #000;
            padding: 20px 30px;
            border-radius: 10px;
            z-index: 10000;
            font-weight: 600;
            box-shadow: 0 10px 40px rgba(0, 255, 0, 0.5);
            animation: fadeInScale 0.3s ease;
        `;
        notification.textContent = '✅ Ссылка скопирована! Вставьте её в Instagram';
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translate(-50%, -50%) scale(0.8)';
            notification.style.transition = 'all 0.3s ease';
            
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 2500);
    }

    shareToSocial() {
        const shareText = '🎓 Quiz Mini App - Telegram бот для изучения различных тем через квизы! Проходите тесты и получайте достижения. Попробуйте прямо сейчас!';
        const shareUrl = this.appUrl;
        
        // Проверяем поддержку Web Share API
        if (navigator.share) {
            navigator.share({
                title: 'Quiz Mini App',
                text: shareText,
                url: shareUrl
            }).catch(error => {
                console.log('Ошибка шаринга:', error);
                this.fallbackShare();
            });
        } else {
            this.fallbackShare();
        }
    }

    fallbackShare() {
        // Fallback для браузеров без Web Share API
        const shareText = encodeURIComponent('🎓 Quiz Mini App - Telegram бот для изучения различных тем через квизы!');
        const shareUrl = encodeURIComponent(this.appUrl);
        
        // Создаем модальное окно с кнопками соцсетей
        this.socialModal = document.createElement('div');
        this.socialModal.className = 'social-share-modal';
        this.socialModal.innerHTML = `
            <div class="social-share-content">
                <div class="social-share-header">
                    <h4>Поделиться в социальных сетях</h4>
                    <button class="social-share-close" onclick="shareApp.closeSocialModal()">&times;</button>
                </div>
                <div class="social-share-buttons">
                    <a href="https://t.me/share/url?url=${shareUrl}&text=${shareText}" target="_blank" class="social-btn telegram-btn">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.05-.2-.06-.06-.14-.04-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
                        </svg>
                        Telegram
                    </a>
                    <a href="https://wa.me/?text=${shareText}%20${shareUrl}" target="_blank" class="social-btn whatsapp-btn">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                        </svg>
                        WhatsApp
                    </a>
                    <a href="https://www.instagram.com/" target="_blank" class="social-btn instagram-btn" onclick="shareApp.copyLinkForInstagram(event)">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
                        </svg>
                        Instagram
                    </a>
                    <a href="https://twitter.com/intent/tweet?text=${shareText}&url=${shareUrl}" target="_blank" class="social-btn twitter-btn">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/>
                        </svg>
                        Twitter
                    </a>
                    <a href="https://www.facebook.com/sharer/sharer.php?u=${shareUrl}" target="_blank" class="social-btn facebook-btn">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                        </svg>
                        Facebook
                    </a>
                </div>
            </div>
        `;
        
        // Добавляем модальное окно в DOM
        document.body.appendChild(this.socialModal);
        
        // Добавляем обработчики для модального окна с соцсетями
        this.addSocialModalEventListeners();
    }

    closeModal() {
        this.modal.style.display = 'none';
        // Удаляем обработчики модального окна при закрытии
        this.removeModalEventListeners();
    }

    /**
     * Закрывает модальное окно с соцсетями
     */
    closeSocialModal() {
        if (this.socialModal) {
            this.socialModal.remove();
            this.socialModal = null;
            // Удаляем обработчики модального окна с соцсетями
            this.removeSocialModalEventListeners();
        }
    }

    /**
     * Добавляет глобальные обработчики событий для автоматического закрытия модального окна
     * Включает: переключение вкладок, навигацию, изменение URL, AJAX навигацию
     */
    addGlobalEventListeners() {
        // Обработчик для переключения вкладок
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                if (this.modal && this.modal.style.display === 'flex') {
                    console.log('🔄 ShareApp: Tab switched, closing modal');
                    this.closeModal();
                }
                if (this.socialModal) {
                    console.log('🔄 ShareApp: Tab switched, closing social modal');
                    this.closeSocialModal();
                }
            }
        });

        // Обработчик для изменения URL (навигация)
        window.addEventListener('popstate', () => {
            if (this.modal && this.modal.style.display === 'flex') {
                console.log('🔄 ShareApp: Navigation occurred, closing modal');
                this.closeModal();
            }
            if (this.socialModal) {
                console.log('🔄 ShareApp: Navigation occurred, closing social modal');
                this.closeSocialModal();
            }
        });

        // Перехватываем pushState для AJAX навигации
        this.interceptPushState();

        // Обработчик для изменения хэша URL
        window.addEventListener('hashchange', () => {
            if (this.modal && this.modal.style.display === 'flex') {
                console.log('🔄 ShareApp: Hash changed, closing modal');
                this.closeModal();
            }
            if (this.socialModal) {
                console.log('🔄 ShareApp: Hash changed, closing social modal');
                this.closeSocialModal();
            }
        });

        // Обработчик для кликов по навигационным элементам
        this.addNavigationEventListeners();

        // Обработчик для отслеживания изменений контента (AJAX навигация)
        this.addContentChangeListener();

        console.log('✅ ShareApp: Global event listeners added');
    }

    /**
     * Добавляет обработчики событий для модального окна с соцсетями
     */
    addSocialModalEventListeners() {
        // Обработчик клика вне модального окна с соцсетями
        const handleOutsideClick = (event) => {
            if (this.socialModal && !this.socialModal.contains(event.target) && !event.target.closest('.share-social-btn')) {
                console.log('🔄 ShareApp: Click outside social modal, closing');
                this.closeSocialModal();
            }
        };

        // Обработчик нажатия клавиши Escape для модального окна с соцсетями
        const handleEscapeKey = (event) => {
            if (event.key === 'Escape' && this.socialModal) {
                console.log('🔄 ShareApp: Escape key pressed, closing social modal');
                this.closeSocialModal();
            }
        };

        // Добавляем обработчики
        document.addEventListener('click', handleOutsideClick);
        document.addEventListener('keydown', handleEscapeKey);

        // Сохраняем ссылки на обработчики для последующего удаления
        this.socialModalEventListeners = {
            outsideClick: handleOutsideClick,
            escapeKey: handleEscapeKey
        };

        console.log('✅ ShareApp: Social modal event listeners added');
    }

    /**
     * Удаляет обработчики событий модального окна с соцсетями
     */
    removeSocialModalEventListeners() {
        if (this.socialModalEventListeners) {
            document.removeEventListener('click', this.socialModalEventListeners.outsideClick);
            document.removeEventListener('keydown', this.socialModalEventListeners.escapeKey);
            this.socialModalEventListeners = null;
            console.log('✅ ShareApp: Social modal event listeners removed');
        }
    }

    /**
     * Добавляет обработчики событий для навигационных элементов
     */
    addNavigationEventListeners() {
        // Обработчик для кликов по навигационным ссылкам
        const handleNavigationClick = (event) => {
            // Проверяем, является ли кликнутый элемент навигационной ссылкой
            const isNavigationLink = event.target.closest('.navigation a') || 
                                   event.target.closest('.navigation .list') ||
                                   event.target.closest('.navigation ul li');
            
            if (isNavigationLink) {
                if (this.modal && this.modal.style.display === 'flex') {
                    console.log('🔄 ShareApp: Navigation link clicked, closing modal');
                    this.closeModal();
                }
                if (this.socialModal) {
                    console.log('🔄 ShareApp: Navigation link clicked, closing social modal');
                    this.closeSocialModal();
                }
            }
        };

        // Добавляем обработчик для кликов по навигации
        document.addEventListener('click', handleNavigationClick);

        // Сохраняем ссылку на обработчик для последующего удаления
        this.navigationEventListener = handleNavigationClick;

        console.log('✅ ShareApp: Navigation event listeners added');
    }

    /**
     * Добавляет обработчик для отслеживания изменений контента (AJAX навигация)
     */
    addContentChangeListener() {
        // Создаем наблюдатель за изменениями в DOM
        this.contentObserver = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                // Проверяем, изменился ли контент страницы
                if (mutation.type === 'childList' && 
                    mutation.target.classList && 
                    mutation.target.classList.contains('content')) {
                    
                    if (this.modal && this.modal.style.display === 'flex') {
                        console.log('🔄 ShareApp: Content changed, closing modal');
                        this.closeModal();
                    }
                    if (this.socialModal) {
                        console.log('🔄 ShareApp: Content changed, closing social modal');
                        this.closeSocialModal();
                    }
                }
            });
        });

        // Начинаем наблюдение за контейнером контента
        const contentContainer = document.querySelector('.content');
        if (contentContainer) {
            this.contentObserver.observe(contentContainer, {
                childList: true,
                subtree: true
            });
            console.log('✅ ShareApp: Content change observer started');
        } else {
            console.log('⚠️ ShareApp: Content container not found for observer');
        }
    }

    /**
     * Перехватывает pushState для отслеживания AJAX навигации
     */
    interceptPushState() {
        // Сохраняем оригинальный pushState
        this.originalPushState = window.history.pushState;
        
        // Переопределяем pushState
        window.history.pushState = (...args) => {
            // Вызываем оригинальный метод
            const result = this.originalPushState.apply(window.history, args);
            
            // Закрываем модальное окно при изменении URL
            if (this.modal && this.modal.style.display === 'flex') {
                console.log('🔄 ShareApp: pushState called, closing modal');
                this.closeModal();
            }
            
            // Закрываем модальное окно с соцсетями при изменении URL
            if (this.socialModal) {
                console.log('🔄 ShareApp: pushState called, closing social modal');
                this.closeSocialModal();
            }
            
            return result;
        };

        console.log('✅ ShareApp: pushState intercepted');
    }

    /**
     * Добавляет обработчики событий для модального окна
     */
    addModalEventListeners() {
        // Обработчик клика вне модального окна
        const handleOutsideClick = (event) => {
            if (this.modal && !this.modal.contains(event.target) && !event.target.closest('.share-app-btn')) {
                console.log('🔄 ShareApp: Click outside modal, closing');
                this.closeModal();
            }
        };

        // Обработчик нажатия клавиши Escape
        const handleEscapeKey = (event) => {
            if (event.key === 'Escape' && this.modal && this.modal.style.display === 'flex') {
                console.log('🔄 ShareApp: Escape key pressed, closing modal');
                this.closeModal();
            }
        };

        // Добавляем обработчики
        document.addEventListener('click', handleOutsideClick);
        document.addEventListener('keydown', handleEscapeKey);

        // Сохраняем ссылки на обработчики для последующего удаления
        this.modalEventListeners = {
            outsideClick: handleOutsideClick,
            escapeKey: handleEscapeKey
        };

        console.log('✅ ShareApp: Modal event listeners added');
    }

    /**
     * Удаляет обработчики событий модального окна
     */
    removeModalEventListeners() {
        if (this.modalEventListeners) {
            document.removeEventListener('click', this.modalEventListeners.outsideClick);
            document.removeEventListener('keydown', this.modalEventListeners.escapeKey);
            this.modalEventListeners = null;
            console.log('✅ ShareApp: Modal event listeners removed');
        }
    }

    /**
     * Уничтожает объект и очищает все обработчики событий
     */
    destroy() {
        // Удаляем обработчики модального окна
        this.removeModalEventListeners();

        // Удаляем обработчик навигации
        if (this.navigationEventListener) {
            document.removeEventListener('click', this.navigationEventListener);
            this.navigationEventListener = null;
        }

        // Останавливаем наблюдатель за изменениями контента
        if (this.contentObserver) {
            this.contentObserver.disconnect();
            this.contentObserver = null;
        }

        // Восстанавливаем оригинальный pushState
        if (this.originalPushState) {
            window.history.pushState = this.originalPushState;
            this.originalPushState = null;
        }

        // Удаляем модальное окно из DOM
        if (this.modal && this.modal.parentNode) {
            this.modal.parentNode.removeChild(this.modal);
        }

        // Удаляем модальное окно с соцсетями
        if (this.socialModal) {
            this.socialModal.remove();
            this.socialModal = null;
        }

        console.log('✅ ShareApp: Destroyed and cleaned up all event listeners');
    }

    updateTranslations() {
        console.log('🔄 ShareApp: Updating translations in modal');
        
        // Проверяем доступность сервиса локализации
        console.log('🔍 ShareApp: localizationService available:', !!window.localizationService);
        console.log('🔍 ShareApp: translations available:', !!window.translations);
        console.log('🔍 ShareApp: current language:', window.currentLanguage);
        
        // Обновляем переводы в модальном окне
        if (window.localizationService && window.localizationService.getText) {
            const elements = this.modal.querySelectorAll('[data-translate]');
            console.log(`🔍 ShareApp: Found ${elements.length} elements with data-translate`);
            
            elements.forEach(element => {
                const key = element.getAttribute('data-translate');
                const translation = window.localizationService.getText(key);
                console.log(`🔍 ShareApp: Key "${key}", translation: "${translation}"`);
                
                if (translation) {
                    console.log(`🔄 ShareApp: Updating ${key} to "${translation}"`);
                    element.textContent = translation;
                }
            });
        } else if (window.translations) {
            // Fallback: используем глобальные переводы
            const elements = this.modal.querySelectorAll('[data-translate]');
            console.log(`🔍 ShareApp: Found ${elements.length} elements with data-translate (fallback)`);
            
            elements.forEach(element => {
                const key = element.getAttribute('data-translate');
                const translation = window.translations[key];
                console.log(`🔍 ShareApp: Key "${key}", translation: "${translation}" (fallback)`);
                
                if (translation) {
                    console.log(`🔄 ShareApp: Updating ${key} to "${translation}"`);
                    element.textContent = translation;
                }
            });
        }
        
        console.log('✅ ShareApp: Translations updated');
    }

    // Метод для обновления переводов при переключении языка
    refreshTranslations() {
        if (this.modal && this.modal.style.display === 'flex') {
            console.log('🔄 ShareApp: Refreshing translations for visible modal');
            this.updateTranslations();
            
            // Принудительно обновляем еще раз через небольшую задержку
            setTimeout(() => {
                this.updateTranslations();
                console.log('🔄 ShareApp: Translations refreshed again');
            }, 50);
        }
    }
}

// Инициализируем функциональность при загрузке страницы
let shareApp;

document.addEventListener('DOMContentLoaded', function() {
    console.log('🔧 ShareApp: DOM loaded, initializing...');
    shareApp = new ShareApp();
    window.shareApp = shareApp;
    console.log('✅ ShareApp: Initialized successfully');
});

// Глобальная функция для доступа из HTML (будет доступна после DOMContentLoaded)
window.shareApp = null; 