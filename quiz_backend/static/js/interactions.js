/**
 * Обработка взаимодействий пользователей с постами и проектами
 * Включает лайки, репосты и просмотры
 */

class ContentInteractions {
    constructor() {
        this.baseUrl = '/api';
        this.csrfToken = this.getCsrfToken();
        this.init();
    }

    init() {
        this.bindEvents();
        this.trackViews();
    }

    getCsrfToken() {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || '';
    }

    bindEvents() {
        // Обработка лайков
        document.addEventListener('click', (e) => {
            if (e.target.matches('.like-btn, .like-btn *')) {
                e.preventDefault();
                const btn = e.target.closest('.like-btn');
                this.toggleLike(btn);
            }
        });

        // Обработка репостов
        document.addEventListener('click', (e) => {
            if (e.target.matches('.share-btn, .share-btn *')) {
                e.preventDefault();
                const btn = e.target.closest('.share-btn');
                this.showShareModal(btn);
            }
        });
    }

    async toggleLike(button) {
        const contentType = button.dataset.contentType; // 'post' или 'project'
        const slug = button.dataset.slug;
        const iconElement = button.querySelector('.like-icon');
        const countElement = button.querySelector('.like-count');

        // Проверяем авторизацию
        if (!await this.isUserAuthenticated()) {
            this.showAuthModal();
            return;
        }

        try {
            button.disabled = true;
            
            const response = await fetch(`${this.baseUrl}/${contentType}s/${slug}/toggle_like/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Обновляем UI
            this.updateLikeButton(button, data.liked, data.likes_count);
            
            // Анимация
            this.animateLike(iconElement, data.liked);

        } catch (error) {
            console.error('Ошибка при лайке:', error);
            this.showError('Не удалось поставить лайк. Попробуйте снова.');
        } finally {
            button.disabled = false;
        }
    }

    updateLikeButton(button, isLiked, count) {
        const iconElement = button.querySelector('.like-icon');
        const countElement = button.querySelector('.like-count');
        
        if (isLiked) {
            button.classList.add('liked');
            iconElement.classList.remove('far');
            iconElement.classList.add('fas');
            iconElement.style.color = '#e91e63';
        } else {
            button.classList.remove('liked');
            iconElement.classList.remove('fas');
            iconElement.classList.add('far');
            iconElement.style.color = '';
        }
        
        if (countElement) {
            countElement.textContent = count;
        }
    }

    animateLike(iconElement, isLiked) {
        if (isLiked) {
            iconElement.style.transform = 'scale(1.3)';
            setTimeout(() => {
                iconElement.style.transform = 'scale(1)';
            }, 200);
        }
    }

    showShareModal(button) {
        const contentType = button.dataset.contentType;
        const slug = button.dataset.slug;
        const title = button.dataset.title;
        const url = button.dataset.url;

        const modal = this.createShareModal(contentType, slug, title, url);
        document.body.appendChild(modal);
        
        // Показываем модальное окно
        setTimeout(() => modal.classList.add('show'), 10);
    }

    createShareModal(contentType, slug, title, url) {
        const modal = document.createElement('div');
        modal.className = 'share-modal';
        modal.innerHTML = `
            <div class="share-modal-content">
                <div class="share-modal-header">
                    <h3>Поделиться</h3>
                    <button class="close-modal">&times;</button>
                </div>
                <div class="share-modal-body">
                    <div class="share-platforms">
                        <button class="share-platform-btn" data-platform="telegram">
                            <i class="fab fa-telegram"></i>
                            Telegram
                        </button>
                        <button class="share-platform-btn" data-platform="vk">
                            <i class="fab fa-vk"></i>
                            VKontakte
                        </button>
                        <button class="share-platform-btn" data-platform="facebook">
                            <i class="fab fa-facebook"></i>
                            Facebook
                        </button>
                        <button class="share-platform-btn" data-platform="twitter">
                            <i class="fab fa-twitter"></i>
                            Twitter
                        </button>
                        <button class="share-platform-btn" data-platform="instagram">
                            <i class="fab fa-instagram"></i>
                            Instagram
                        </button>
                        <button class="share-platform-btn" data-platform="tiktok">
                            <i class="fab fa-tiktok"></i>
                            TikTok
                        </button>
                        <button class="share-platform-btn" data-platform="pinterest">
                            <i class="fab fa-pinterest"></i>
                            Pinterest
                        </button>
                        <button class="share-platform-btn" data-platform="whatsapp">
                            <i class="fab fa-whatsapp"></i>
                            WhatsApp
                        </button>
                    </div>
                    <div class="share-url">
                        <input type="text" value="${url}" readonly>
                        <button class="copy-url-btn">Копировать</button>
                    </div>
                </div>
            </div>
        `;

        // Обработчики событий для модального окна
        modal.addEventListener('click', (e) => {
            if (e.target === modal || e.target.matches('.close-modal')) {
                this.closeModal(modal);
            }
            
            if (e.target.matches('.share-platform-btn, .share-platform-btn *')) {
                const btn = e.target.closest('.share-platform-btn');
                const platform = btn.dataset.platform;
                this.shareContent(contentType, slug, platform, title, url);
                this.closeModal(modal);
            }
            
            if (e.target.matches('.copy-url-btn')) {
                this.copyToClipboard(url);
            }
        });

        return modal;
    }

    async shareContent(contentType, slug, platform, title, url) {
        try {
            // Отправляем запрос на бэкенд
            const response = await fetch(`${this.baseUrl}/${contentType}s/${slug}/share/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify({
                    platform: platform,
                    shared_url: this.generateShareUrl(platform, title, url)
                }),
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Обновляем счетчик репостов
            this.updateShareCount(slug, data.shares_count);
            
            // Открываем окно для репоста
            this.openShareWindow(platform, title, url);

        } catch (error) {
            console.error('Ошибка при репосте:', error);
            this.showError('Не удалось поделиться. Попробуйте снова.');
        }
    }

    generateShareUrl(platform, title, url) {
        const text = encodeURIComponent(title);
        const encodedUrl = encodeURIComponent(url);
        
        const shareUrls = {
            telegram: `https://t.me/share/url?url=${encodedUrl}&text=${text}`,
            vk: `https://vk.com/share.php?url=${encodedUrl}&title=${text}`,
            facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`,
            twitter: `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${text}`,
            instagram: `https://www.instagram.com/`,
            tiktok: `https://www.tiktok.com/`,
            pinterest: `https://pinterest.com/pin/create/button/?url=${encodedUrl}&description=${text}`,
            whatsapp: `https://wa.me/?text=${text}%20${encodedUrl}`
        };
        
        return shareUrls[platform] || url;
    }

    openShareWindow(platform, title, url) {
        const shareUrl = this.generateShareUrl(platform, title, url);
        window.open(shareUrl, '_blank', 'width=600,height=400');
    }

    updateShareCount(slug, count) {
        const shareElements = document.querySelectorAll(`[data-slug="${slug}"] .share-count`);
        shareElements.forEach(el => {
            el.textContent = count;
        });
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showSuccess('Ссылка скопирована!');
        }).catch(() => {
            // Fallback для старых браузеров
            const input = document.createElement('input');
            input.value = text;
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
            this.showSuccess('Ссылка скопирована!');
        });
    }

    closeModal(modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            if (modal.parentNode) {
                modal.parentNode.removeChild(modal);
            }
        }, 300);
    }

    async trackViews() {
        // Отслеживание просмотров для детальных страниц
        const postSlug = this.extractSlugFromUrl('post');
        const projectSlug = this.extractSlugFromUrl('project');

        if (postSlug) {
            await this.incrementViews('post', postSlug);
        } else if (projectSlug) {
            await this.incrementViews('project', projectSlug);
        }
    }

    extractSlugFromUrl(contentType) {
        const path = window.location.pathname;
        const pattern = new RegExp(`/${contentType}/([^/]+)/`);
        const match = path.match(pattern);
        return match ? match[1] : null;
    }

    async incrementViews(contentType, slug) {
        try {
            await fetch(`${this.baseUrl}/${contentType}s/${slug}/increment_views/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                },
                credentials: 'same-origin'
            });
        } catch (error) {
            console.error('Ошибка при отслеживании просмотров:', error);
        }
    }

    async isUserAuthenticated() {
        try {
            const response = await fetch('/api/check-auth/', {
                credentials: 'same-origin'
            });
            const data = await response.json();
            return data.is_authenticated;
        } catch (error) {
            console.error('Ошибка проверки авторизации:', error);
            return false;
        }
    }

    showAuthModal() {
        this.showError('Войдите в систему, чтобы ставить лайки и делиться контентом.');
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => notification.classList.add('show'), 10);
        
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    new ContentInteractions();
}); 