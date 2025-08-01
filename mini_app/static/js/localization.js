/**
 * Сервис локализации для клиентской части
 */
class LocalizationService {
    constructor() {
        console.log('🔧 LocalizationService constructor called');
        console.log('🔧 window.currentLanguage:', window.currentLanguage);
        console.log('🔧 window.translations:', window.translations);
        console.log('🔧 window.supportedLanguages:', window.supportedLanguages);
        
        this.currentLanguage = window.currentLanguage || 'en';
        this.translations = window.translations || {};
        this.supportedLanguages = window.supportedLanguages || ['en', 'ru'];
        
        // Инициализация
        this.init();
    }
    
               init() {
               console.log('🌐 LocalizationService initialized with language:', this.currentLanguage);
               
               // Загружаем сохраненный язык из localStorage
               const savedLanguage = localStorage.getItem('selectedLanguage');
               if (savedLanguage && this.supportedLanguages.includes(savedLanguage)) {
                   this.currentLanguage = savedLanguage;
                   console.log('🌐 Restored saved language:', savedLanguage);
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
        console.warn(`Translation not found for key: ${key}`);
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
            console.log(`🔄 Changing language to: ${language}`);
            
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
                
                console.log(`✅ Language changed to: ${language}`);
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
        console.log('🎨 Updating interface with new translations');
        console.log('🎨 Current language:', this.currentLanguage);
        console.log('🎨 Available translations:', Object.keys(this.translations));
        
        let updatedCount = 0;
        
        // Обновляем все элементы с data-translate атрибутом
        const translateElements = document.querySelectorAll('[data-translate]');
        console.log('🎨 Found translate elements:', translateElements.length);
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
        console.log('🎨 Found placeholder elements:', placeholderElements.length);
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
        console.log('🎨 Found title elements:', titleElements.length);
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
        console.log('🎨 Found alt elements:', altElements.length);
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
        
        console.log(`✅ Interface updated: ${updatedCount} elements changed`);
        
        // Если ничего не обновилось, возможно нужно принудительно обновить
        if (updatedCount === 0) {
            console.log('⚠️ No elements were updated, forcing refresh...');
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
console.log('🚀 Creating global LocalizationService instance...');
window.localizationService = new LocalizationService();
console.log('✅ LocalizationService instance created:', window.localizationService);

// Экспортируем для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LocalizationService;
} 