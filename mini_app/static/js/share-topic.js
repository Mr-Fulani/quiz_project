class ShareTopic {
    constructor() {
        this.botUsername = 'mr_proger_bot'; // Имя вашего бота
        this.appName = 'quiz'; // Название вашего Mini App
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
                this.shareTopic(topicId, topicName);
            }
        }, true); // true - использовать capture phase
    }

    shareTopic(topicId, topicName) {
        // Формируем ссылку на страницу с превью
        const previewUrl = `${window.location.origin}/share/topic/${topicId}`;
        
        if (window.Telegram && window.Telegram.WebApp) {
            // Используем нативный шаринг Telegram
            const shareText = `Check out this topic: ${topicName}`;
            // Делимся ссылкой на превью
            const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(previewUrl)}&text=${encodeURIComponent(shareText)}`;
            window.Telegram.WebApp.openTelegramLink(shareUrl);
        } else {
            // Fallback для браузера
            this.copyToClipboard(previewUrl);
        }
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            // Показываем уведомление об успешном копировании
            if (window.showNotification) {
                window.showNotification('share_link_copied', 'success', null, 'Ссылка скопирована!');
            } else {
                alert('Ссылка скопирована!');
            }
        }).catch(err => {
            console.error('Could not copy text: ', err);
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.shareTopicHandler = new ShareTopic();
});
