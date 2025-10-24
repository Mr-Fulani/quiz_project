class ShareTopic {
    constructor() {
        this.botUsername = 'mr_proger_bot'; // Имя вашего бота
        this.appName = 'quiz'; // Название вашего Mini App
        // Простая статическая локализация
        this._t = {
            en: {
                share_text: 'Check out this topic: {name}',
                copied: 'Link copied to clipboard'
            },
            ru: {
                share_text: 'Посмотрите тему: {name}',
                copied: 'Ссылка скопирована в буфер обмена'
            }
        };
        this.init();
    }

    init() {
        // Используем document и capture phase (true), чтобы перехватить событие раньше всех
        document.addEventListener('click', (event) => {
            const shareButton = event.target.closest('.share-topic-btn');
            if (shareButton) {
                // Останавливаем дальнейшее распространение, чтобы другие обработчики не сработали
                event.preventDefault();
                event.stopPropagation();

                const topicId = shareButton.dataset.topicId;
                const topicName = shareButton.dataset.topicName;
                const lang = (shareButton.dataset.lang || 'en').toLowerCase();
                this.shareTopic(topicId, topicName, lang, shareButton);
            }
        }, true); // true - использовать capture phase
    }

    shareTopic(topicId, topicName, lang = 'en', buttonEl = null) {
        // Формируем ссылку на страницу с превью
        const previewUrl = `${window.location.origin}/share/topic/${topicId}`;

        const texts = this._t[lang] || this._t['en'];
        const shareText = texts.share_text.replace('{name}', topicName || '');

        // Если Telegram WebApp доступен, пробуем разные API
        if (window.Telegram && window.Telegram.WebApp) {
            // Try openTelegramLink (trusted) -> openUrl -> fallback to share via t.me/share/url
            try {
                if (window.Telegram.WebApp.openTelegramLink) {
                    const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(previewUrl)}&text=${encodeURIComponent(shareText)}`;
                    window.Telegram.WebApp.openTelegramLink(shareUrl);
                    return;
                }
            } catch (e) {
                console.warn('openTelegramLink failed', e);
            }

            try {
                if (window.Telegram.WebApp.openUrl) {
                    window.Telegram.WebApp.openUrl(previewUrl);
                    return;
                }
            } catch (e) {
                console.warn('openUrl failed', e);
            }
        }

        // Попытка использовать Web Share API (мобильные браузеры)
        if (navigator.share) {
            navigator.share({
                title: topicName,
                text: shareText,
                url: previewUrl
            }).catch(err => {
                console.warn('navigator.share failed', err);
                // fallback to t.me/share/url
                const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(previewUrl)}&text=${encodeURIComponent(shareText)}`;
                window.open(shareUrl, '_blank');
            });
            return;
        }

        // Открываем t.me/share/url в новой вкладке как fallback
        try {
            const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(previewUrl)}&text=${encodeURIComponent(shareText)}`;
            window.open(shareUrl, '_blank');
            return;
        } catch (e) {
            console.warn('window.open shareUrl failed', e);
        }

        // В крайнем случае копируем в буфер
        this.copyToClipboard(previewUrl, texts.copied);
    }

    copyToClipboard(text, successMessage) {
        navigator.clipboard.writeText(text).then(() => {
            // Показываем уведомление об успешном копировании
            if (window.showNotification) {
                window.showNotification('share_link_copied', 'success', null, successMessage || 'Ссылка скопирована!');
            } else {
                alert(successMessage || 'Ссылка скопирована!');
            }
        }).catch(err => {
            console.error('Could not copy text: ', err);
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.shareTopicHandler = new ShareTopic();
});
