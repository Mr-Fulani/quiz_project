# Обновление: Поддержка Safe Areas Telegram

## Описание проблемы

Модальные окна в mini app не учитывали safe areas (безопасные зоны) Telegram, из-за чего контент мог перекрываться системными элементами интерфейса (шапка Telegram, панель навигации и т.д.).

## Внесенные изменения

### 1. Обновление CSS переменных

#### Файлы обновлены:
- `mini_app/static/css/share-app.css` - Модальное окно "Поделиться приложением"
- `mini_app/static/css/donation.css` - Модальное окно Stripe для донатов
- `mini_app/static/css/profile.css` - Модальное окно редактирования профиля
- `mini_app/static/css/styles.css` - Общее модальное окно редактирования
- `mini_app/static/css/explanation-modal.css` - Модальное окно с объяснениями

#### Изменения:
Для всех модальных окон добавлены CSS переменные safe areas:

```css
/* Учитываем safe areas Telegram */
padding-top: var(--tg-safe-area-inset-top, var(--safe-area-top, env(safe-area-inset-top, 0px)));
padding-bottom: var(--tg-safe-area-inset-bottom, var(--safe-area-bottom, env(safe-area-inset-bottom, 0px)));
padding-left: var(--tg-safe-area-inset-left, var(--safe-area-left, env(safe-area-inset-left, 0px)));
padding-right: var(--tg-safe-area-inset-right, var(--safe-area-right, env(safe-area-inset-right, 0px)));
```

Также обновлены значения `max-height` для контента модальных окон:

```css
max-height: calc(80vh - var(--tg-safe-area-inset-top, var(--safe-area-top, env(safe-area-inset-top, 0px))) - var(--tg-safe-area-inset-bottom, var(--safe-area-bottom, env(safe-area-inset-bottom, 0px))));
```

### 2. Обновление JavaScript

#### Файл: `mini_app/static/js/platform-detector.js`

Добавлена установка Telegram-специфичных CSS переменных для совместимости:

```javascript
// Также устанавливаем Telegram-специфичные переменные для совместимости
document.documentElement.style.setProperty('--tg-safe-area-inset-top', `${platform.safeArea.top}px`);
document.documentElement.style.setProperty('--tg-safe-area-inset-bottom', `${platform.safeArea.bottom}px`);
document.documentElement.style.setProperty('--tg-safe-area-inset-left', `${platform.safeArea.left}px`);
document.documentElement.style.setProperty('--tg-safe-area-inset-right', `${platform.safeArea.right}px`);
```

## Механизм работы

### Приоритет переменных (fallback chain):

1. **`--tg-safe-area-inset-*`** - Переменные, устанавливаемые Telegram WebApp API
2. **`--safe-area-*`** - Кастомные переменные приложения
3. **`env(safe-area-inset-*)`** - Стандартные CSS env переменные (iOS)
4. **`0px`** - Значение по умолчанию

### Поддерживаемые области:

- `top` - Верхняя безопасная зона (например, вырез для камеры)
- `bottom` - Нижняя безопасная зона (например, индикатор home на iOS)
- `left` - Левая безопасная зона
- `right` - Правая безопасная зона

## Результат

Теперь все модальные окна в приложении корректно учитывают safe areas Telegram:
- ✅ Модальное окно "Поделиться приложением"
- ✅ Модальное окно с соцсетями
- ✅ Модальное окно Stripe для донатов
- ✅ Модальное окно редактирования профиля
- ✅ Общие модальные окна
- ✅ Модальное окно с объяснениями

## Тестирование

Для проверки работы safe areas:

1. Откройте приложение в Telegram на устройстве с вырезом (notch) или динамическим островом
2. Откройте любое модальное окно (например, "Поделиться приложением" в настройках)
3. Убедитесь, что контент не перекрывается системными элементами Telegram

## Совместимость

- ✅ Telegram iOS (с вырезом/динамическим островом)
- ✅ Telegram Android
- ✅ Telegram Desktop
- ✅ Браузерная версия (fallback к стандартным значениям)

