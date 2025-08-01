/**
 * Сервис локализации для клиентской части
 */
class LocalizationService {
    constructor() {
        this.currentLanguage = window.currentLanguage || 'en';
        this.translations = window.translations || {};
        this.supportedLanguages = window.supportedLanguages || ['en', 'ru'];
        
        // Инициализация
        this.init();
    }
    
    init() {
        // Загружаем сохраненный язык из localStorage
        const savedLanguage = localStorage.getItem('selectedLanguage');
        if (savedLanguage && this.supportedLanguages.includes(savedLanguage)) {
            this.currentLanguage = savedLanguage;
        }
        
        // Обновляем глобальные переменные
        window.currentLanguage = this.currentLanguage;
        
        // Принудительно обновляем интерфейс при инициализации
        setTimeout(() => {
            this.updateInterface();
        }, 100);
    }
    
    /**
     * Получает перевод по ключу
     */
    getText(key, fallback = null) {
        const translation = this.translations[key];
        if (translation) {
            return translation;
        }
        
        // Если перевод не найден, возвращаем fallback или ключ
        return fallback || key;
    }
    
    /**
     * Переключает язык
     */
    async changeLanguage(language) {
        if (!this.supportedLanguages.includes(language)) {
            console.error(`Unsupported language: ${language}`);
            return false;
        }
        
        try {
            // Отправляем запрос на сервер
            const response = await fetch('/api/change-language', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ language: language })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                // Обновляем локальные данные
                this.currentLanguage = language;
                this.translations = data.translations;
                
                // Обновляем глобальные переменные
                window.currentLanguage = this.currentLanguage;
                window.translations = this.translations;
                
                // Сохраняем в localStorage
                localStorage.setItem('selectedLanguage', language);
                
                // Обновляем интерфейс
                this.updateInterface();
                
                return true;
            } else {
                console.error('Failed to change language:', data.error);
                return false;
            }
            
        } catch (error) {
            console.error('Error changing language:', error);
            return false;
        }
    }
    
    /**
     * Обновляет интерфейс с новыми переводами
     */
    updateInterface() {
        let updatedCount = 0;
        
        // Обновляем все элементы с data-translate атрибутом
        const translateElements = document.querySelectorAll('[data-translate]');
        translateElements.forEach(element => {
            const key = element.getAttribute('data-translate');
            const translation = this.getText(key);
            if (translation && element.textContent !== translation) {
                element.textContent = translation;
                updatedCount++;
            }
        });
        
        // Обновляем placeholder'ы
        const placeholderElements = document.querySelectorAll('[data-translate-placeholder]');
        placeholderElements.forEach(element => {
            const key = element.getAttribute('data-translate-placeholder');
            const translation = this.getText(key);
            if (translation && element.placeholder !== translation) {
                element.placeholder = translation;
                updatedCount++;
            }
        });
        
        // Обновляем title атрибуты
        const titleElements = document.querySelectorAll('[data-translate-title]');
        titleElements.forEach(element => {
            const key = element.getAttribute('data-translate-title');
            const translation = this.getText(key);
            if (translation && element.title !== translation) {
                element.title = translation;
                updatedCount++;
            }
        });
        
        // Обновляем alt атрибуты изображений
        const altElements = document.querySelectorAll('[data-translate-alt]');
        altElements.forEach(element => {
            const key = element.getAttribute('data-translate-alt');
            const translation = this.getText(key);
            if (translation && element.alt !== translation) {
                element.alt = translation;
                updatedCount++;
            }
        });
        
        // Обновляем язык документа
        if (document.documentElement.lang !== this.currentLanguage) {
            document.documentElement.lang = this.currentLanguage;
            updatedCount++;
        }
        
        // Вызываем кастомные обработчики обновления
        if (window.onLanguageChanged) {
            window.onLanguageChanged(this.currentLanguage, this.translations);
        }
        
        // Если ничего не обновилось, возможно нужно принудительно обновить
        if (updatedCount === 0) {
            setTimeout(() => {
                this.updateInterface();
            }, 50);
        }
    }
    
    /**
     * Получает текущий язык
     */
    getCurrentLanguage() {
        return this.currentLanguage;
    }
    
    /**
     * Получает все переводы
     */
    getAllTranslations() {
        return this.translations;
    }
    
    /**
     * Получает поддерживаемые языки
     */
    getSupportedLanguages() {
        return this.supportedLanguages;
    }
}

// Создаем глобальный экземпляр
window.localizationService = new LocalizationService();

// Экспортируем для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LocalizationService;
} 