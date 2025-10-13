/**
 * Platform Detector для Telegram Mini App
 * Определяет платформу и адаптирует интерфейс
 */

(function(window) {
    'use strict';
    
    // Определение платформы
    const platform = {
        isTelegramWebApp: false,
        isMobile: false,
        isDesktop: false,
        isBrowser: false,
        hasInitData: false,
        viewportHeight: 0,
        viewportWidth: 0,
        safeArea: { top: 0, bottom: 0, left: 0, right: 0 },
        theme: 'light',
        colorScheme: 'light'
    };
    
    function detectPlatform() {
        console.log('🔍 Определяем платформу...');
        
        // Проверяем наличие Telegram WebApp API
        if (window.Telegram && window.Telegram.WebApp) {
            platform.isTelegramWebApp = true;
            const tg = window.Telegram.WebApp;
            
            console.log('✅ Telegram WebApp API доступен');
            
            // Определяем платформу по User Agent
            const userAgent = navigator.userAgent.toLowerCase();
            platform.isMobile = /android|iphone|ipad|ipod|blackberry|windows phone/.test(userAgent);
            platform.isDesktop = !platform.isMobile;
            
            // Проверяем наличие initData
            platform.hasInitData = !!(tg.initData && tg.initData.length > 0);
            
            // Получаем размеры viewport
            platform.viewportHeight = tg.viewportHeight || window.innerHeight;
            platform.viewportWidth = tg.viewportWidth || window.innerWidth;
            
            // Получаем safe area (важно для устройств с "чёлкой")
            if (tg.safeArea) {
                platform.safeArea = {
                    top: tg.safeArea.top || 0,
                    bottom: tg.safeArea.bottom || 0,
                    left: tg.safeArea.left || 0,
                    right: tg.safeArea.right || 0
                };
            }
            
            // Определяем тему
            platform.theme = tg.themeParams?.bg_color ? 'dark' : 'light';
            platform.colorScheme = tg.colorScheme || 'light';
            
            console.log('📱 Платформа определена:', {
                isMobile: platform.isMobile,
                isDesktop: platform.isDesktop,
                hasInitData: platform.hasInitData,
                viewport: `${platform.viewportWidth}x${platform.viewportHeight}`,
                safeArea: platform.safeArea,
                theme: platform.theme
            });
            
        } else {
            // Браузер или другой контекст
            platform.isBrowser = true;
            platform.isMobile = /android|iphone|ipad|ipod|blackberry|windows phone/.test(navigator.userAgent.toLowerCase());
            platform.isDesktop = !platform.isMobile;
            platform.viewportHeight = window.innerHeight;
            platform.viewportWidth = window.innerWidth;
            
            console.log('🌐 Браузерный контекст:', {
                isMobile: platform.isMobile,
                isDesktop: platform.isDesktop,
                viewport: `${platform.viewportWidth}x${platform.viewportHeight}`
            });
        }
        
        return platform;
    }
    
    function applyPlatformAdaptations() {
        console.log('🎨 Применяем адаптации для платформы...');
        
        const body = document.body;
        
        // Добавляем классы для платформы
        if (platform.isTelegramWebApp) {
            body.classList.add('telegram-webapp');
        }
        if (platform.isMobile) {
            body.classList.add('mobile-platform');
        }
        if (platform.isDesktop) {
            body.classList.add('desktop-platform');
        }
        if (platform.isBrowser) {
            body.classList.add('browser-platform');
        }
        if (platform.hasInitData) {
            body.classList.add('has-init-data');
        } else {
            body.classList.add('no-init-data');
        }
        
        // Применяем safe area
        if (platform.safeArea.top > 0 || platform.safeArea.bottom > 0) {
            document.documentElement.style.setProperty('--safe-area-top', `${platform.safeArea.top}px`);
            document.documentElement.style.setProperty('--safe-area-bottom', `${platform.safeArea.bottom}px`);
            document.documentElement.style.setProperty('--safe-area-left', `${platform.safeArea.left}px`);
            document.documentElement.style.setProperty('--safe-area-right', `${platform.safeArea.right}px`);
            
            // Также устанавливаем Telegram-специфичные переменные для совместимости
            document.documentElement.style.setProperty('--tg-safe-area-inset-top', `${platform.safeArea.top}px`);
            document.documentElement.style.setProperty('--tg-safe-area-inset-bottom', `${platform.safeArea.bottom}px`);
            document.documentElement.style.setProperty('--tg-safe-area-inset-left', `${platform.safeArea.left}px`);
            document.documentElement.style.setProperty('--tg-safe-area-inset-right', `${platform.safeArea.right}px`);
        }
        
        // Адаптируем высоту для мобильных устройств
        if (platform.isMobile) {
            const vh = platform.viewportHeight * 0.01;
            document.documentElement.style.setProperty('--vh', `${vh}px`);
            
            // Используем --vh вместо vh для корректной высоты на мобильных
            body.style.height = 'calc(var(--vh, 1vh) * 100)';
        }
        
        console.log('✅ Адаптации применены');
    }
    
    function handleViewportChanges() {
        // Обработка изменений viewport (поворот экрана, изменение размера окна)
        function updateViewport() {
            if (platform.isTelegramWebApp && window.Telegram?.WebApp) {
                const tg = window.Telegram.WebApp;
                platform.viewportHeight = tg.viewportHeight || window.innerHeight;
                platform.viewportWidth = tg.viewportWidth || window.innerWidth;
                
                if (platform.isMobile) {
                    const vh = platform.viewportHeight * 0.01;
                    document.documentElement.style.setProperty('--vh', `${vh}px`);
                }
                
                console.log('📐 Viewport обновлен:', `${platform.viewportWidth}x${platform.viewportHeight}`);
            }
        }
        
        // Слушаем изменения размера окна
        window.addEventListener('resize', updateViewport);
        
        // Для Telegram WebApp слушаем события изменения viewport
        if (platform.isTelegramWebApp && window.Telegram?.WebApp) {
            window.Telegram.WebApp.onEvent('viewportChanged', updateViewport);
        }
    }
    
    function handleKeyboardEvents() {
        // Обработка событий клавиатуры на мобильных устройствах
        if (platform.isMobile) {
            let initialViewportHeight = platform.viewportHeight;
            
            window.addEventListener('resize', () => {
                const currentHeight = window.innerHeight;
                const heightDifference = initialViewportHeight - currentHeight;
                
                if (heightDifference > 150) {
                    // Клавиатура открылась
                    document.body.classList.add('keyboard-open');
                    console.log('⌨️ Клавиатура открылась');
                } else if (heightDifference < 50) {
                    // Клавиатура закрылась
                    document.body.classList.remove('keyboard-open');
                    console.log('⌨️ Клавиатура закрылась');
                }
            });
        }
    }
    
    // Инициализация
    function init() {
        console.log('🚀 Инициализация Platform Detector...');
        
        detectPlatform();
        applyPlatformAdaptations();
        handleViewportChanges();
        handleKeyboardEvents();
        
        console.log('✅ Platform Detector инициализирован');
    }
    
    // Экспортируем в глобальную область
    window.platformDetector = {
        platform: platform,
        detect: detectPlatform,
        applyAdaptations: applyPlatformAdaptations,
        init: init
    };
    
    // Автоматическая инициализация при загрузке DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})(window); 