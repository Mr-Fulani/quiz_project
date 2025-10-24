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
        // Получаем текущий язык из window.currentLanguage или используем переданный
        const currentLang = window.currentLanguage || lang || 'en';
        
        // Ссылка на страницу превью с языком (показывает картинку и заголовок темы + кнопки соцсетей)
        const previewUrl = `${window.location.origin}/share/topic/${topicId}?lang=${currentLang}`;
        
        const texts = this._t[currentLang] || this._t['en'];

        // Открываем страницу превью с кнопками соцсетей
        if (window.Telegram && window.Telegram.WebApp) {
            // Пробуем открыть через Telegram WebApp API
            try {
                if (window.Telegram.WebApp.openLink) {
                    window.Telegram.WebApp.openLink(previewUrl);
                    return;
                }
            } catch (e) {
                console.warn('openLink failed', e);
            }

            try {
                if (window.Telegram.WebApp.openTelegramLink) {
                    window.Telegram.WebApp.openTelegramLink(previewUrl);
                    return;
                }
            } catch (e) {
                console.warn('openTelegramLink failed', e);
            }
        }

        // Fallback: открываем страницу превью в новом окне/вкладке
        try {
            window.open(previewUrl, '_blank');
            return;
        } catch (e) {
            console.warn('window.open failed', e);
        }

        // В крайнем случае открываем в текущем окне
        window.location.href = previewUrl;
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
