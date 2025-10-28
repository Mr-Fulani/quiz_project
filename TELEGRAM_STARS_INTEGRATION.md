# Интеграция Telegram Stars ⭐️

## Обзор

Добавлена полная интеграция оплаты через **Telegram Stars** — встроенную валюту Telegram для Mini Apps.

## Что было реализовано

### 1. Backend (Django)

#### Модель Donation (`quiz_backend/donation/models.py`)
Добавлены поля:
- `telegram_payment_charge_id` - ID платежа от Telegram
- `stars_amount` - Сумма в Stars (XTR)
- `telegram_invoice_payload` - Payload для идентификации инвойса

#### Сервис (`quiz_backend/donation/telegram_stars_service.py`)
Новый сервис для работы с Telegram Stars API:
- `create_invoice_link()` - создание инвойса через Bot API
- `refund_star_payment()` - возврат Stars платежа

#### Views (`quiz_backend/donation/views.py`)
- `create_telegram_stars_invoice()` - эндпоинт создания инвойса
- Конвертация USD → Stars (1$ = 100 Stars)
- Swagger документация

#### URLs (`quiz_backend/donation/urls.py`)
- `donation/stars/create-invoice/` - новый endpoint

### 2. Mini App (FastAPI)

#### API Router (`mini_app/routers/api.py`)
- `/api/donation/telegram-stars/create-invoice/` - проксирование запросов к Django

#### Frontend (`mini_app/static/js/donation.js`)
- Добавлен метод `processTelegramStarsPayment()`
- Интеграция с `window.Telegram.WebApp.openInvoice()`
- Обработка статусов: `paid`, `cancelled`, `failed`

#### Шаблон (`mini_app/templates/settings.html`)
- Добавлена кнопка выбора "⭐️ Telegram Stars"

#### Локализация (`mini_app/services/localization.py`)
- Переводы на английский и русский: `stars_payment`

### 3. Bot (Aiogram)

#### Payment Handler (`bot/handlers/payment_handler.py`)
Новый обработчик платежей:
- `process_pre_checkout_query()` - валидация перед оплатой
- `process_successful_payment()` - обработка успешного платежа
- Автоматическое обновление статуса donation в БД
- Отправка благодарственного сообщения

#### Main (`bot/main.py`)
- Подключен `payment_router` к диспетчеру

### 4. База данных
- Создана и применена миграция `0005_donation_stars_amount_and_more.py`

### 5. Django Admin

#### Интеграция в админке (`quiz_backend/donation/admin.py`)
Добавлены:
- ✅ **Поиск** по `telegram_payment_charge_id` и `telegram_invoice_payload`
- ✅ **Readonly поля**: `telegram_payment_charge_id`, `stars_amount`, `telegram_invoice_payload`
- ✅ **Fieldset "Telegram Stars ⭐️"** с полной информацией о платеже
- ✅ **Иконка ⭐️** в колонке "Тип платежа"
- ✅ **Форматирование суммы** с отображением Stars (например: "⭐️ 500 Stars (≈$5)")
- ✅ **Метод `telegram_stars_info()`** - детальная информация о платеже
- ✅ **Массовое действие** "⭐️ Возврат Telegram Stars платежей" (refund)
- ✅ **Статистика** в change_list с отдельной секцией для Stars:
  - Всего донатов через Stars
  - Завершенных/Ожидающих
  - Общее количество Stars
  - Эквивалент в USD

#### Кастомный шаблон (`change_list.html`)
- Красивая карточка со статистикой Stars
- Градиентный заголовок в желто-золотых тонах
- Отображение всех метрик в удобном формате

## Как это работает

```
1. Пользователь выбирает сумму и способ оплаты "Telegram Stars"
2. Frontend создает запрос к /api/donation/telegram-stars/create-invoice/
3. Django создает инвойс через Bot API (createInvoiceLink)
4. Frontend открывает инвойс через WebApp.openInvoice()
5. Пользователь оплачивает в Telegram
6. Telegram отправляет successful_payment боту
7. Bot обновляет статус donation в БД
8. Пользователь получает благодарственное сообщение
```

## Курс конвертации

**1 USD = 100 Stars**

Это примерный курс. Актуальный курс можно уточнить в документации Telegram.

## Важные замечания

1. **Только в Telegram WebApp** - Stars доступны только внутри Telegram приложения
2. **Provider token** - для Stars всегда пустая строка (`''`)
3. **Currency code** - для Stars используется `'XTR'`
4. **Payload** - имеет формат `donation_{id}` для идентификации

## Тестирование

Для тестирования:
1. Откройте Mini App в Telegram
2. Перейдите в "Настройки" → "Поддержать проект"
3. Выберите сумму и способ оплаты "⭐️ Telegram Stars"
4. Введите имя и нажмите "Пожертвовать"
5. Завершите оплату в Telegram

## Мониторинг

Логи можно найти в:
- Django: `/app/logs/debug.log` в контейнере `quiz_backend`
- Bot: консольный вывод контейнера `bot`
- Mini App: консольный вывод контейнера `mini_app`

## Документация

- [Telegram Bot API - Payments](https://core.telegram.org/bots/api#payments)
- [Telegram Mini Apps - openInvoice](https://core.telegram.org/bots/webapps#initializing-mini-apps)
- [Telegram Stars Guide](https://core.telegram.org/bots/payments#stars)

## Автор

Интеграция выполнена: 28 октября 2025

