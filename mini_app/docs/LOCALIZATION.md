# Система локализации Quiz Mini App

## Обзор

Система локализации обеспечивает поддержку множественных языков в приложении. Она состоит из серверной и клиентской частей, которые работают синхронно.

## Архитектура

### Серверная часть

1. **LocalizationService** (`services/localization.py`)
   - Центральный сервис для управления переводами
   - Содержит словари переводов для всех поддерживаемых языков
   - Методы для получения переводов и управления языками

2. **LanguageMiddleware** (`middleware/language_middleware.py`)
   - Автоматически определяет язык пользователя
   - Приоритеты определения языка:
     1. Query параметр `lang`
     2. Заголовок `Accept-Language`
     3. Cookie `selected_language`
     4. Язык по умолчанию

3. **API Endpoint** (`routers/api.py`)
   - `/api/change-language` - для динамического переключения языка
   - Возвращает обновленные переводы

### Клиентская часть

1. **LocalizationService** (`static/js/localization.js`)
   - JavaScript сервис для управления локализацией
   - Автоматическое обновление интерфейса при смене языка
   - Синхронизация с сервером

## Поддерживаемые языки

- `en` - Английский (по умолчанию)
- `ru` - Русский

## Использование

### В шаблонах (Jinja2)

```html
<!-- Простой перевод -->
<h1>{{ translations.get('home', 'Главная') }}</h1>

<!-- С data-атрибутом для динамического обновления -->
<span data-translate="home">{{ translations.get('home', 'Главная') }}</span>

<!-- Placeholder -->
<input data-translate-placeholder="search_placeholder" placeholder="{{ translations.get('search_placeholder', 'Поиск...') }}">

<!-- Title атрибут -->
<button data-translate-title="help" title="{{ translations.get('help', 'Помощь') }}">

<!-- Alt атрибут -->
<img data-translate-alt="logo" alt="{{ translations.get('logo', 'Логотип') }}">
```

### В JavaScript

```javascript
// Получение перевода
const text = window.localizationService.getText('home');

// Переключение языка
await window.localizationService.changeLanguage('ru');

// Получение текущего языка
const currentLang = window.localizationService.getCurrentLanguage();

// Получение всех переводов
const translations = window.localizationService.getAllTranslations();
```

### Добавление новых переводов

1. Добавьте ключи в `services/localization.py`:

```python
TRANSLATIONS = {
    "en": {
        "new_key": "English text",
        # ...
    },
    "ru": {
        "new_key": "Русский текст",
        # ...
    }
}
```

2. Используйте в шаблонах:

```html
<span data-translate="new_key">{{ translations.get('new_key', 'Fallback') }}</span>
```

## Правила разработки

### 1. Всегда используйте data-атрибуты для динамического контента

```html
<!-- ✅ Правильно -->
<span data-translate="welcome_message">{{ translations.get('welcome_message', 'Добро пожаловать') }}</span>

<!-- ❌ Неправильно -->
<span>{{ translations.get('welcome_message', 'Добро пожаловать') }}</span>
```

### 2. Используйте fallback значения

```html
<!-- ✅ Правильно -->
<span data-translate="welcome_message">{{ translations.get('welcome_message', 'Добро пожаловать') }}</span>

<!-- ❌ Неправильно -->
<span data-translate="welcome_message">{{ translations.get('welcome_message') }}</span>
```

### 3. Группируйте переводы по функциональности

```python
TRANSLATIONS = {
    "en": {
        # Навигация
        "home": "Home",
        "profile": "Profile",
        
        # Главная страница
        "search_placeholder": "Search...",
        "start_button": "Start",
        
        # Профиль
        "edit_profile": "Edit Profile",
        "save_changes": "Save Changes",
    }
}
```

### 4. Используйте описательные ключи

```python
# ✅ Правильно
"search_placeholder": "Search topics..."
"start_quiz_button": "Start Quiz"
"profile_edit_button": "Edit Profile"

# ❌ Неправильно
"search": "Search topics..."
"start": "Start Quiz"
"edit": "Edit Profile"
```

## API Endpoints

### POST /api/change-language

Переключает язык и возвращает обновленные переводы.

**Request:**
```json
{
    "language": "ru"
}
```

**Response:**
```json
{
    "success": true,
    "language": "ru",
    "translations": {
        "home": "Главная",
        "profile": "Профиль",
        // ...
    },
    "supported_languages": ["en", "ru"]
}
```

## Отладка

### Логирование

Система ведет подробные логи:

```javascript
// Клиентская часть
console.log('🌐 LocalizationService initialized with language:', language);
console.log('🔄 Changing language to:', language);
console.log('✅ Language changed successfully');
console.log('🎨 Updating interface with new translations');
```

```python
# Серверная часть
logger.debug(f"Language detected: {language} for {request.url.path}")
logger.info(f"Rendering page with language: {language}")
```

### Проверка работы

1. Откройте консоль браузера
2. Переключите язык в настройках
3. Проверьте логи на наличие ошибок
4. Убедитесь, что интерфейс обновился

## Расширение системы

### Добавление нового языка

1. Добавьте код языка в `core/config.py`:
```python
SUPPORTED_LANGUAGES: list = ["en", "ru", "es"]
```

2. Добавьте переводы в `services/localization.py`:
```python
TRANSLATIONS = {
    "en": { ... },
    "ru": { ... },
    "es": {
        "home": "Inicio",
        "profile": "Perfil",
        # ...
    }
}
```

3. Обновите шаблоны для поддержки нового языка:
```html
{% if lang == 'es' %}🇪🇸 Español{% endif %}
```

### Добавление новых типов переводов

1. Расширьте `updateInterface()` в `localization.js`:
```javascript
// Обновляем новые атрибуты
document.querySelectorAll('[data-translate-custom]').forEach(element => {
    const key = element.getAttribute('data-translate-custom');
    const translation = this.getText(key);
    if (translation) {
        element.setAttribute('data-custom', translation);
    }
});
```

2. Используйте в шаблонах:
```html
<div data-translate-custom="custom_attribute" data-custom="{{ translations.get('custom_attribute', 'Default') }}">
```

## Тестирование

### Автоматические тесты

Создайте тесты для проверки:

1. Определения языка middleware
2. Переключения языка через API
3. Обновления интерфейса на клиенте
4. Сохранения языка в localStorage

### Ручное тестирование

1. Проверьте переключение языка в настройках
2. Убедитесь, что язык сохраняется при перезагрузке
3. Проверьте работу с разными браузерами
4. Протестируйте в Telegram Web App

## Производительность

### Оптимизации

1. **Кэширование переводов** - переводы загружаются один раз и кэшируются
2. **Ленивая загрузка** - переводы загружаются только при необходимости
3. **Минимизация DOM-операций** - обновляются только измененные элементы

### Мониторинг

Следите за:
- Временем загрузки переводов
- Размером словарей переводов
- Количеством DOM-операций при смене языка 