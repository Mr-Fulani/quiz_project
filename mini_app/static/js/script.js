document.addEventListener('DOMContentLoaded', function() {
    const launchBtn = document.getElementById('launch-btn');
    const modalOverlay = document.getElementById('modal-overlay');
    const appMenu = document.getElementById('app-menu');

    if (launchBtn) {
        launchBtn.addEventListener('click', function() {
            modalOverlay.style.display = 'none';
            appMenu.style.display = 'block';
        });
    }
});

function handleMenu(buttonText) {
    console.log(`Нажата кнопка: ${buttonText}`);
    // Здесь можно добавить дополнительную логику
}

// Если приложение запущено внутри Telegram
if (window.Telegram && Telegram.WebApp) {
    Telegram.WebApp.ready();
    
    // Настраиваем тему
    const isDarkTheme = window.Telegram.WebApp.colorScheme === 'dark';
    if (isDarkTheme) {
        document.body.classList.add('dark-theme');
    }
} 