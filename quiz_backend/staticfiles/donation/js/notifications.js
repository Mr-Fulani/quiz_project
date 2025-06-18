// Функция уведомлений для всех страниц
function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.padding = '15px 25px';
    notification.style.borderRadius = '8px';
    notification.style.color = 'white';
    notification.style.fontSize = '14px';
    notification.style.zIndex = '1000';
    notification.style.boxShadow = '0 2px 5px rgba(0, 0, 0, 0.2)';
    notification.style.transform = 'translateX(120%)';
    notification.style.transition = 'transform 0.3s ease';

    if (type === 'success') {
        notification.style.backgroundColor = '#4CAF50';
    } else if (type === 'error') {
        notification.style.backgroundColor = '#f44336';
    } else if (type === 'info') {
        notification.style.backgroundColor = '#2196F3';
    }

    document.body.appendChild(notification);

    // Показываем уведомление
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 100);

    // Удаляем уведомление через 3 секунды
    setTimeout(() => {
        notification.style.transform = 'translateX(120%)';
        setTimeout(() => {
            if (notification && notification.parentNode) {
                notification.remove();
            }
        }, 300);
    }, 3000);
} 