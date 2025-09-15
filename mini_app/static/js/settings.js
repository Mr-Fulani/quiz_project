/**
 * settings.js
 * Инициализация логики для страницы настроек.
 */

(function(window) {
    console.log('🔧 Settings page DOM loaded');

    const localizationService = window.localizationService;
    console.log('🔧 window.localizationService:', localizationService);

    // Функция для инициализации страницы настроек
    function initSettingsPage() {
        console.log('🚀 DOMContentLoaded: Инициализация приложения...');
        // Здесь можно добавить специфическую логику для страницы настроек
        // Например, загрузка данных пользователя, обработка форм и т.д.

        // Пример: Обновление текста на странице с учетом локализации
        // const greetingElement = document.getElementById('settings-greeting');
        // if (greetingElement) {
        //     greetingElement.textContent = localizationService.getText('settings_greeting_key', 'Привет на странице настроек!');
        // }

        // Все остальные вызовы глобальных функций (initializeUser, updateLocalizationFromPage, etc.)
        // будут управляться из base.html, чтобы избежать дублирования и ошибок.
    }

    // Ожидаем полной загрузки DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSettingsPage);
    } else {
        initSettingsPage();
    }

})(window);
