# Анализ проблемы с Telegram Login Widget

## Описание проблемы

**Текущая ситуация:**
- Telegram Login Widget загружается на странице `quiz-code.com`
- Виджет находится внутри модального окна (возможно, внутри iframe или overlay)
- При клике по виджету ничего не происходит - callback функция не вызывается
- В логах сервера нет запросов к `/api/social-auth/telegram/auth/`
- Виджет загружается успешно (видны события `ready` и `resize` от `oauth.telegram.org`)

## Официальная документация Telegram

Согласно официальной документации Telegram (https://core.telegram.org/widgets/login):

### Два метода работы виджета:

1. **Редирект (`data-auth-url`):**
   - Виджет делает редирект на указанный URL с параметрами авторизации
   - Не работает в iframe из-за ограничений безопасности браузеров
   - Требует абсолютный URL

2. **Callback (`data-onauth`):**
   - Вызывает JavaScript функцию с данными пользователя
   - Рекомендуется для использования в iframe
   - Функция должна быть определена глобально ДО загрузки виджета

### Текущая конфигурация:

```html
<script async src="https://telegram.org/js/telegram-widget.js?22"
        data-telegram-login="{{ TELEGRAM_BOT_USERNAME }}"
        data-size="large"
        data-userpic="true"
        data-request-access="write"
        data-lang="ru"
        data-onauth="handleTelegramAuth(user)">
</script>
```

Функция определена ДО виджета:
```javascript
window.handleTelegramAuth = function(user) { ... }
```

## Возможные причины проблемы

### 1. Виджет загружается в iframe от oauth.telegram.org

**Проблема:** Когда виджет загружается, он создает iframe с `oauth.telegram.org`. Если callback функция определена на родительской странице, виджет в iframe может не иметь доступа к ней из-за CORS/Same-Origin Policy.

**Решение:** Функция должна быть доступна в глобальном контексте `window`, что у нас есть. Но возможно виджет пытается вызвать функцию внутри iframe, а не на родительской странице.

### 2. Асинхронная загрузка виджета

**Проблема:** Атрибут `async` означает, что скрипт загружается асинхронно. К моменту, когда виджет готов, функция может быть недоступна (маловероятно, так как функция определена синхронно).

**Решение:** Убедиться, что функция определена синхронно ДО загрузки виджета (это уже сделано).

### 3. Версия виджета

**Проблема:** Используется версия `?22`, но в документации часто упоминаются версии `?15` или `?2`. Возможно, новая версия имеет баги или изменился API.

**Решение:** Попробовать другую версию виджета.

### 4. Виджет не может вызвать функцию из-за CSP или других ограничений

**Проблема:** Content Security Policy или другие настройки безопасности могут блокировать выполнение функции.

**Решение:** Проверить CSP настройки и разрешить `unsafe-inline` для скриптов или использовать nonce.

### 5. Виджет не видит функцию в глобальном контексте

**Проблема:** Виджет может пытаться вызвать функцию через `eval()` или `new Function()`, что может быть заблокировано CSP.

**Решение:** Проверить, доступна ли функция через `window.handleTelegramAuth` в момент загрузки виджета.

## Решения для тестирования

### Решение 1: Использовать более старую версию виджета

```html
<script async src="https://telegram.org/js/telegram-widget.js?15"
        data-telegram-login="{{ TELEGRAM_BOT_USERNAME }}"
        data-size="large"
        data-userpic="true"
        data-request-access="write"
        data-lang="ru"
        data-onauth="handleTelegramAuth(user)">
</script>
```

### Решение 2: Убедиться, что функция доступна глобально

```javascript
// Явно устанавливаем функцию в window
window.handleTelegramAuth = function(user) { ... };

// Также пробуем без префикса window (если виджет ищет в глобальном scope)
handleTelegramAuth = function(user) { ... };
```

### Решение 3: Использовать postMessage для обхода iframe ограничений

Если виджет действительно не может вызвать функцию из-за iframe, можно использовать `postMessage`:

```javascript
window.addEventListener('message', function(event) {
    if (event.origin === 'https://oauth.telegram.org') {
        if (event.data && event.data.id) {
            // Это данные от Telegram виджета
            handleTelegramAuth(event.data);
        }
    }
});
```

### Решение 4: Вынести виджет из модального окна

Если виджет находится в модальном окне, которое может быть iframe, попробовать вынести виджет на основную страницу для тестирования.

### Решение 5: Использовать альтернативный подход - открыть Telegram OAuth в новом окне

```javascript
function openTelegramAuth() {
    const botUsername = '{{ TELEGRAM_BOT_USERNAME }}';
    const authUrl = 'https://oauth.telegram.org/auth?bot_id=' + botUsername + '&origin=' + encodeURIComponent(window.location.origin) + '&request_access=write&return_to=' + encodeURIComponent(window.location.href);
    window.open(authUrl, 'Telegram Auth', 'width=600,height=500');
}
```

## Рекомендации для диагностики

1. **Проверить, вызывается ли функция вообще:**
   - Добавить `console.log` в самое начало функции
   - Добавить `debugger;` для остановки на брейкпоинте

2. **Проверить, загружается ли виджет:**
   - В DevTools → Network найти запрос к `telegram-widget.js`
   - Проверить, что скрипт загружается без ошибок

3. **Проверить события клика:**
   - В DevTools → Elements найти iframe виджета
   - Проверить, есть ли обработчики событий клика

4. **Проверить сообщения postMessage:**
   - В DevTools → Console добавить:
     ```javascript
     window.addEventListener('message', function(e) { console.log('Message:', e); });
     ```

5. **Проверить версию виджета:**
   - Попробовать разные версии: `?2`, `?15`, `?22`

## Текущий статус

- ✅ Домен настроен в BotFather: `quiz-code.com`
- ✅ Виджет загружается успешно
- ✅ Функция определена глобально ДО загрузки виджета
- ✅ Используется callback метод (`data-onauth`)
- ❌ Callback функция не вызывается при клике
- ❌ Нет запросов на сервер

## Следующие шаги

1. Попробовать версию виджета `?15` вместо `?22`
2. Добавить обработчик `postMessage` на случай, если виджет использует его вместо прямого вызова
3. Проверить, не блокирует ли CSP выполнение функции
4. Вынести виджет из модального окна для тестирования

