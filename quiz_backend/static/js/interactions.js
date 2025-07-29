/**
 * Обработка взаимодействий пользователей с постами и проектами
 * Включает лайки, репосты и просмотры
 */

class ContentInteractions {
    constructor() {
        this.baseUrl = '/api';
        this.csrfToken = this.getCsrfToken();
        this.currentTooltip = null;
        this.tooltipTimeout = null;
        this.isMouseOverTooltip = false;
        this.usersCache = {}; // Кэш для пользователей
        this.translations = this.initTranslations();
        this.init();
    }

    initTranslations() {
        // Получаем язык из HTML lang атрибута или используем русский по умолчанию
        const lang = document.documentElement.lang || 'ru';
        
        const translations = {
            'ru': {
                'liked_by': 'Лайкнули',
                'shared_by': 'Поделились',
                'and_more': 'и еще',
                'view_profile': 'Перейти к профилю',
                'share_title': 'Поделиться',
                'login_required_likes': 'Войдите в систему, чтобы ставить лайки.',
                'login_required_shares': 'Войдите в систему, чтобы делиться контентом.',
                'like_error': 'Не удалось поставить лайк. Попробуйте снова.',
                'share_error': 'Не удалось поделиться. Попробуйте снова.',
                'link_copied': 'Ссылка скопирована!'
            },
            'en': {
                'liked_by': 'Liked by',
                'shared_by': 'Shared by', 
                'and_more': 'and',
                'view_profile': 'View profile',
                'share_title': 'Share',
                'login_required_likes': 'Please log in to like content.',
                'login_required_shares': 'Please log in to share content.',
                'like_error': 'Failed to like. Please try again.',
                'share_error': 'Failed to share. Please try again.',
                'link_copied': 'Link copied!'
            }
        };
        
        return translations[lang] || translations['ru'];
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

        // Тултипы для лайков и репостов с улучшенной логикой
        document.addEventListener('mouseenter', (e) => {
            if (!e.target || typeof e.target.closest !== 'function') return;
            
            const likeBtn = e.target.closest('.like-btn');
            const shareBtn = e.target.closest('.share-btn');
            
            if (likeBtn) {
                const count = likeBtn.querySelector('.like-count');
                if (count && parseInt(count.textContent) > 0) {
                    this.scheduleTooltipShow(likeBtn, 'likes', 150); // Ускоренная задержка 150ms
                }
            } else if (shareBtn) {
                const count = shareBtn.querySelector('.share-count');
                if (count && parseInt(count.textContent) > 0) {
                    this.scheduleTooltipShow(shareBtn, 'shares', 150); // Ускоренная задержка 150ms
                }
            }
        }, true);

        document.addEventListener('mouseleave', (e) => {
            if (!e.target || typeof e.target.closest !== 'function') return;
            
            const btn = e.target.closest('.like-btn, .share-btn');
            if (btn) {
                this.scheduleTooltipHide(200); // Ускоренная задержка 200ms перед скрытием
            }
        }, true);

        // Поддержка мобильных устройств (touch события)
        document.addEventListener('touchstart', (e) => {
            if (!e.target || typeof e.target.closest !== 'function') return;
            
            const likeBtn = e.target.closest('.like-btn');
            const shareBtn = e.target.closest('.share-btn');
            
            if (likeBtn) {
                const count = likeBtn.querySelector('.like-count');
                if (count && parseInt(count.textContent) > 0) {
                    this.scheduleTooltipShow(likeBtn, 'likes', 100); // Быстрее на мобильных
                }
            } else if (shareBtn) {
                const count = shareBtn.querySelector('.share-count');
                if (count && parseInt(count.textContent) > 0) {
                    this.scheduleTooltipShow(shareBtn, 'shares', 100); // Быстрее на мобильных
                }
            }
        }, true);

        // Скрытие тултипа при touch вне его области
        document.addEventListener('touchstart', (e) => {
            if (!e.target || typeof e.target.closest !== 'function') return;
            
            if (this.currentTooltip && !e.target.closest('.users-tooltip') && !e.target.closest('.like-btn, .share-btn')) {
                this.hideUsersTooltip();
            }
        }, true);
    }

    async toggleLike(button) {
        const contentType = button.dataset.contentType; // 'post' или 'project'
        const slug = button.dataset.slug;
        const iconElement = button.querySelector('.like-icon');
        const countElement = button.querySelector('.like-count');

        // Проверяем авторизацию
        if (!await this.isUserAuthenticated()) {
            this.showAuthModal('likes');
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
            this.showError(this.translations.like_error);
        } finally {
            button.disabled = false;
        }
    }

    updateLikeButton(button, isLiked, count) {
        const iconElement = button.querySelector('.like-icon');
        const countElement = button.querySelector('.like-count');
        const slug = button.dataset.slug;
        
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
        
        // Очищаем кэш для этого поста
        this.clearUsersCache(slug);
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
        let url = button.dataset.url;

        // Убеждаемся, что URL абсолютный
        if (url && !url.startsWith('http')) {
            url = window.location.origin + url;
        }

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
                    <h3>${this.translations.share_title}</h3>
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
        // Проверяем авторизацию для шаринга
        if (!await this.isUserAuthenticated()) {
            this.showAuthModal('shares');
            return;
        }

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
            
            // Открываем окно для репоста с правильным URL
            this.openShareWindow(platform, title, url);

        } catch (error) {
            console.error('Ошибка при репосте:', error);
            this.showError(this.translations.share_error);
        }
    }

    generateShareUrl(platform, title, url) {
        // Генерируем специальный share URL для лучших превью
        let shareUrl;
        
        if (platform === 'vk') {
            // Для VK используем URL без языкового префикса
            shareUrl = this.getVkShareUrl(url);
        } else {
            shareUrl = this.getShareUrl(url);
        }
        
        const text = encodeURIComponent(title);
        const encodedUrl = encodeURIComponent(shareUrl);
        
        console.log('Generating share URL:', { platform, title, url, shareUrl, text, encodedUrl });
        
        const shareUrls = {
            telegram: `https://t.me/share/url?url=${encodedUrl}&text=${text}`,
            vk: `https://vk.com/share.php?url=${encodedUrl}&title=${text}`,
            facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`,
            twitter: `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${text}`,
            instagram: `https://www.instagram.com/`,
            tiktok: `https://www.tiktok.com/`,  
            pinterest: `https://pinterest.com/pin/create/button/?url=${encodedUrl}&description=${text}`,
            whatsapp: `https://wa.me/?text=${text}%0A${encodedUrl}`
        };
        
        const result = shareUrls[platform] || shareUrl;
        console.log('Generated share URL:', result);
        return result;
    }

    getShareUrl(originalUrl) {
        // Преобразуем обычный URL в share URL для лучших превью
        // Избегаем двойного преобразования
        if (originalUrl.includes('/share/')) {
            return originalUrl; // Уже share URL
        }
        
        try {
            // Получаем базовый URL без параметров
            const urlObj = new URL(originalUrl);
            let path = urlObj.pathname;
            
            // Преобразуем путь для share URL
            if (path.includes('/post/')) {
                path = path.replace('/post/', '/share/post/');
            } else if (path.includes('/project/')) {
                path = path.replace('/project/', '/share/project/');
            }
            
            // Собираем новый URL с абсолютным путем
            urlObj.pathname = path;
            
            return urlObj.toString();
        } catch (error) {
            console.error('Ошибка при создании share URL:', error, 'originalUrl:', originalUrl);
            // Возвращаем оригинальный URL если не удалось создать share URL
            return originalUrl;
        }
    }

    getVkShareUrl(originalUrl) {
        // Специальный метод для VK - убираем языковой префикс
        try {
            const urlObj = new URL(originalUrl);
            let path = urlObj.pathname;
            
            // Убираем языковой префикс для VK
            path = path.replace(/^\/[a-z]{2}\//, '/');
            
            // Преобразуем путь для share URL
            if (path.includes('/post/')) {
                path = path.replace('/post/', '/share/post/');
            } else if (path.includes('/project/')) {
                path = path.replace('/project/', '/share/project/');
            }
            
            // Собираем новый URL с абсолютным путем
            urlObj.pathname = path;
            
            return urlObj.toString();
        } catch (error) {
            console.error('Ошибка при создании VK share URL:', error, 'originalUrl:', originalUrl);
            return originalUrl;
        }
    }

    openShareWindow(platform, title, url) {
        const shareUrl = this.generateShareUrl(platform, title, url);
        console.log('Opening share window:', { platform, title, url, shareUrl });
        window.open(shareUrl, '_blank', 'width=600,height=400');
    }

    updateShareCount(slug, count) {
        const shareElements = document.querySelectorAll(`[data-slug="${slug}"] .share-count`);
        shareElements.forEach(el => {
            el.textContent = count;
        });
        
        // Очищаем кэш для этого поста
        this.clearUsersCache(slug);
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showSuccess(this.translations.link_copied);
        }).catch(() => {
            // Fallback для старых браузеров
            const input = document.createElement('input');
            input.value = text;
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
            this.showSuccess(this.translations.link_copied);
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

    showAuthModal(type = 'likes') {
        const message = type === 'shares' 
            ? this.translations.login_required_shares 
            : this.translations.login_required_likes;
        this.showError(message);
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

    async showUsersTooltip(button, type) {
        // Удаляем существующий тултип
        this.hideUsersTooltip();

        const contentType = button.dataset.contentType;
        const slug = button.dataset.slug;
        
        // Проверяем кэш
        const cacheKey = `${contentType}_${slug}_${type}_users`;
        if (this.usersCache && this.usersCache[cacheKey] && 
            Date.now() - this.usersCache[cacheKey].timestamp < 30000) { // 30 секунд кэш
            this.createUsersTooltip(button, this.usersCache[cacheKey].data, type);
            return;
        }

        const url = `${this.baseUrl}/${contentType}s/${slug}/${type}_users/`;

        try {
            const response = await fetch(url, {
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                console.warn(`Failed to load ${type} users: ${response.status}`);
                return;
            }

            const data = await response.json();
            
            if (data.users.length === 0) {
                return;
            }

            // Кэшируем результат
            if (!this.usersCache) this.usersCache = {};
            this.usersCache[cacheKey] = {
                data: data,
                timestamp: Date.now()
            };

            this.createUsersTooltip(button, data, type);

        } catch (error) {
            console.error('Ошибка при загрузке пользователей:', error);
        }
    }

    createUsersTooltip(button, data, type) {
        const tooltip = document.createElement('div');
        tooltip.className = 'users-tooltip';
        tooltip.id = 'users-tooltip';

        const title = type === 'likes' ? this.translations.liked_by : this.translations.shared_by;
        
        let content = `<div class="tooltip-header">${title}</div>`;
        content += '<div class="users-grid">';

        data.users.forEach(user => {
            const profileUrl = this.getUserProfileUrl(user.username);
            content += `
                <div class="user-avatar-item" data-username="${user.username}" title="${user.full_name} - ${this.translations.view_profile}">
                    <img src="${user.avatar}" alt="${user.full_name}" class="user-avatar" data-profile-url="${profileUrl}">
                    ${type === 'shares' ? `<span class="platform-badge">${this.getPlatformIcon(user.platform)}</span>` : ''}
                </div>
            `;
        });

        content += '</div>';

        if (data.total_count > data.users.length) {
            const moreCount = data.total_count - data.users.length;
            content += `<div class="tooltip-footer">${this.translations.and_more} ${moreCount}</div>`;
        }

        tooltip.innerHTML = content;

        // Добавляем обработчики событий мыши для тултипа
        tooltip.addEventListener('mouseenter', () => {
            this.isMouseOverTooltip = true;
            this.clearTooltipTimeouts(); // Отменяем скрытие
        });

        tooltip.addEventListener('mouseleave', () => {
            this.isMouseOverTooltip = false;
            this.scheduleTooltipHide(100); // Очень быстро скрываем после ухода с тултипа
        });

        // Добавляем обработчики кликов по аватаркам
        tooltip.addEventListener('click', (e) => {
            const avatarItem = e.target.closest('.user-avatar-item');
            if (avatarItem) {
                const username = avatarItem.dataset.username;
                const profileUrl = this.getUserProfileUrl(username);
                window.location.href = profileUrl; // Переходим в той же вкладке
            }
        });

        // Позиционирование
        document.body.appendChild(tooltip);
        this.currentTooltip = tooltip;
        
        this.positionTooltip(tooltip, button);

        // Плавная анимация появления
        requestAnimationFrame(() => {
            tooltip.classList.add('show');
        });
    }

    positionTooltip(tooltip, button) {
        const buttonRect = button.getBoundingClientRect();
        
        // Сначала показываем тултип чтобы получить его размеры
        tooltip.style.visibility = 'hidden';
        tooltip.style.opacity = '1';
        
        const tooltipRect = tooltip.getBoundingClientRect();
        
        let top = buttonRect.top - tooltipRect.height - 10;
        let left = buttonRect.left + (buttonRect.width / 2) - (tooltipRect.width / 2);

        // Проверяем, помещается ли тултип сверху
        if (top < 10) {
            top = buttonRect.bottom + 10;
            tooltip.classList.add('below');
        }

        // Проверяем границы экрана
        if (left < 10) {
            left = 10;
        } else if (left + tooltipRect.width > window.innerWidth - 10) {
            left = window.innerWidth - tooltipRect.width - 10;
        }

        // Используем fixed позиционирование
        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
        
        // Возвращаем в исходное состояние для анимации
        tooltip.style.opacity = '0';
        tooltip.style.visibility = 'visible';
    }

    hideUsersTooltip() {
        this.clearTooltipTimeouts();
        
        if (this.currentTooltip) {
            this.currentTooltip.classList.remove('show');
            
            // Плавно удаляем тултип после анимации
            setTimeout(() => {
                if (this.currentTooltip && this.currentTooltip.parentNode) {
                    this.currentTooltip.parentNode.removeChild(this.currentTooltip);
                }
                this.currentTooltip = null;
                this.isMouseOverTooltip = false;
            }, 150); // Ускоренная анимация
        }
    }

    getPlatformIcon(platform) {
        const icons = {
            telegram: '📱',
            vk: '🌐',
            facebook: '📘',
            twitter: '🐦',
            instagram: '📷',
            tiktok: '🎵',
            pinterest: '📌',
            whatsapp: '💬',
            other: '🔗'
        };
        return icons[platform] || icons.other;
    }

    scheduleTooltipShow(button, type, delay = 300) {
        // Отменяем любые существующие таймауты
        this.clearTooltipTimeouts();
        
        // Если тултип уже показан, не показываем новый
        if (this.currentTooltip) {
            return;
        }
        
        this.tooltipTimeout = setTimeout(() => {
            this.showUsersTooltip(button, type);
        }, delay);
    }

    scheduleTooltipHide(delay = 500) {
        // Отменяем показ если он еще не произошел
        if (this.tooltipTimeout) {
            clearTimeout(this.tooltipTimeout);
            this.tooltipTimeout = null;
        }
        
        // Планируем скрытие с задержкой
        this.tooltipTimeout = setTimeout(() => {
            if (!this.isMouseOverTooltip) {
                this.hideUsersTooltip();
            }
        }, delay);
    }

    clearTooltipTimeouts() {
        if (this.tooltipTimeout) {
            clearTimeout(this.tooltipTimeout);
            this.tooltipTimeout = null;
        }
    }

    clearUsersCache(slug) {
        // Очищаем кэш для конкретного поста/проекта
        if (this.usersCache) {
            Object.keys(this.usersCache).forEach(key => {
                if (key.includes(slug)) {
                    delete this.usersCache[key];
                }
            });
        }
    }

    getUserProfileUrl(username) {
        // Генерируем URL профиля пользователя с учетом языкового префикса
        const currentPath = window.location.pathname;
        let languagePrefix = '';
        
        // Проверяем, есть ли языковой префикс в текущем URL
        const pathParts = currentPath.split('/').filter(part => part);
        if (pathParts.length > 0 && (pathParts[0] === 'ru' || pathParts[0] === 'en')) {
            languagePrefix = `/${pathParts[0]}`;
        }
        
        return `${languagePrefix}/accounts/user/${username}/`;
    }

}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    new ContentInteractions();
}); 