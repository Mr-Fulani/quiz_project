/**
 * Функциональность "Поделиться приложением"
 * Включает генерацию QR-кода и копирование ссылки
 */

class ShareApp {
    constructor() {
        this.appUrl = window.location.origin;
        this.qrCodeContainer = null;
        this.modal = null;
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

        // Добавляем обработчик для обновления переводов при переключении языка
        if (window.onLanguageChanged) {
            const originalHandler = window.onLanguageChanged;
            window.onLanguageChanged = (language, translations) => {
                console.log('🔄 ShareApp: Language changed, updating translations');
                this.refreshTranslations();
                // Вызываем оригинальный обработчик, если он есть
                if (originalHandler) {
                    originalHandler(language, translations);
                }
            };
        } else {
            window.onLanguageChanged = (language, translations) => {
                console.log('🔄 ShareApp: Language changed, updating translations');
                this.refreshTranslations();
            };
        }
    }

    async showQRCode() {
        console.log('🚀 ShareApp: Showing QR code modal...');
        try {
            // Показываем модальное окно
            this.modal.style.display = 'flex';
            console.log('✅ ShareApp: Modal displayed');
            
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

    shareToSocial() {
        const shareText = '🎓 Quiz Mini App - Образовательное приложение с квизами! Изучайте различные темы, проходите тесты и получайте достижения. Попробуйте прямо сейчас!';
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
        const shareText = encodeURIComponent('🎓 Quiz Mini App - Образовательное приложение с квизами!');
        const shareUrl = encodeURIComponent(this.appUrl);
        
        // Создаем модальное окно с кнопками соцсетей
        const socialModal = document.createElement('div');
        socialModal.className = 'social-share-modal';
        socialModal.innerHTML = `
            <div class="social-share-content">
                <div class="social-share-header">
                    <h4>Поделиться в социальных сетях</h4>
                    <button class="social-share-close" onclick="this.parentElement.parentElement.parentElement.remove()">&times;</button>
                </div>
                <div class="social-share-buttons">
                    <a href="https://t.me/share/url?url=${shareUrl}&text=${shareText}" target="_blank" class="social-btn telegram-btn">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.05-.2-.06-.06-.14-.04-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
                        </svg>
                        Telegram
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
        document.body.appendChild(socialModal);
    }

    closeModal() {
        this.modal.style.display = 'none';
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