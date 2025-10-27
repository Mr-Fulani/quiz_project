# 🪙 Руководство по тестированию системы крипто-платежей

## ✅ Что уже исправлено

1. ✅ Добавлены API endpoints для крипто-платежей в `quiz_backend/config/urls.py`
2. ✅ Исправлены пути в `mini_app/static/js/donation.js`
3. ✅ Обновлена версия кэша `donation.js` до `3.0`
4. ✅ CoinGateService готов к использованию

---

## 📝 Шаг 1: Настройка CoinGate (для production)

### 1.1. Получите API ключ CoinGate

1. Зарегистрируйтесь на https://coingate.com
2. Перейдите в API settings
3. Создайте новый API token
4. Скопируйте токен

### 1.2. Обновите `.env` файл

```bash
# В quiz_project/.env добавьте:

# CoinGate настройки
COINGATE_API_TOKEN=ваш_реальный_токен_здесь
COINGATE_ENVIRONMENT=sandbox  # sandbox для тестов, live для production
COINGATE_RECEIVE_CURRENCY=DO_NOT_CONVERT  # или USD/EUR если нужна конвертация
```

---

## 🧪 Шаг 2: Локальное тестирование

### 2.1. Проверка API endpoints

```bash
# 1. Перезапустите контейнеры для применения изменений
docker compose down
docker compose up -d

# 2. Проверьте логи
docker compose logs -f mini_app
docker compose logs -f quiz_backend
```

### 2.2. Тест 1: Проверка списка криптовалют

Откройте браузер и перейдите на страницу Settings.
Откройте консоль разработчика (F12) и проверьте:

**Должен быть запрос:**
```
GET http://localhost:8080/api/donation/crypto-currencies/
```

**Ожидаемый ответ (с реальным токеном):**
```json
{
  "success": true,
  "currencies": [
    {"code": "USDT", "name": "USDT (Tether)"},
    {"code": "USDC", "name": "USDC (USD Coin)"},
    {"code": "BUSD", "name": "BUSD (Binance USD)"},
    {"code": "DAI", "name": "DAI"}
  ]
}
```

**Ожидаемый ответ (без токена - sandbox):**
```json
{
  "success": true,
  "currencies": [...]
}
```

### 2.3. Тест 2: Создание тестового крипто-платежа

**Важно:** Для полного теста нужен реальный CoinGate API token.

#### С реальным токеном:

1. Откройте http://localhost:8080/settings?lang=ru
2. Переключитесь на "Crypto Payment"
3. Выберите криптовалюту (например, USDT)
4. Введите сумму (минимум $1)
5. Введите имя
6. Нажмите "Отправить донат"

**Ожидаемое поведение:**
- Должен появиться QR-код
- Должен отобразиться адрес для оплаты
- Должна отображаться сумма в выбранной криптовалюте
- Статус должен быть "Ожидание оплаты..."

#### Без реального токена (mock mode):

Можно проверить только UI/UX:
- Форма должна корректно переключаться между Card/Crypto
- Валидация должна работать
- Кнопки должны быть активны

---

## 🔍 Шаг 3: Проверка интеграции

### 3.1. Проверьте логи backend

```bash
docker compose logs quiz_backend | grep -i coingate
```

**Что искать:**
- ✅ "CoinGate сервис инициализирован (окружение: sandbox)"
- ✅ "Создание заказа CoinGate: ..."
- ❌ "HTTP ошибка при создании заказа CoinGate" (если есть - проблема с токеном)

### 3.2. Проверьте консоль браузера

Откройте DevTools → Console и ищите:

```
✅ Положительные сигналы:
🪙 Loading crypto currencies...
✅ Crypto currencies loaded: [...]
📡 Creating crypto payment with data: ...
✅ Crypto payment details displayed

❌ Ошибки, если есть проблемы:
❌ Error loading crypto currencies: ...
❌ Error processing crypto payment: ...
```

---

## 🎯 Шаг 4: Функциональное тестирование

### Тестовые сценарии:

#### ✅ Сценарий 1: Успешное создание платежа
1. Откройте Settings
2. Переключитесь на "Crypto Payment"
3. Выберите USDT
4. Введите $5
5. Введите имя "Test User"
6. Нажмите кнопку
7. **Ожидание:** QR-код отображается, адрес копируется, статус polling запущен

#### ✅ Сценарий 2: Валидация формы
1. Попробуйте отправить без имени → должна быть ошибка
2. Попробуйте сумму $0.50 → должна быть ошибка "минимум $1"
3. Попробуйте без выбора криптовалюты → должна быть ошибка

#### ✅ Сценарий 3: Переключение методов оплаты
1. Выберите "Card Payment" → должна показаться форма карты
2. Выберите "Crypto Payment" → должна показаться форма крипто
3. Переключайтесь несколько раз → UI должен корректно обновляться

---

## 🚨 Типичные проблемы и решения

### Проблема 1: 404 на `/api/donation/crypto-currencies/`
**Решение:** ✅ УЖЕ ИСПРАВЛЕНО в этом коммите

### Проблема 2: "Error getting crypto currencies"
**Причина:** CoinGate API token не настроен или невалидный
**Решение:** 
- Проверьте `.env` файл
- Убедитесь, что `COINGATE_API_TOKEN` не содержит `your_api_token_here`
- Перезапустите контейнеры: `docker compose restart`

### Проблема 3: QR-код не отображается
**Причина:** Библиотека QRCode не загружена
**Проверка:** В консоли должно быть: `QRCode library not loaded`
**Решение:** Проверьте загрузку `https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js`

### Проблема 4: Статус платежа не обновляется
**Причина:** Polling не работает или CoinGate callback не настроен
**Решение:** 
- Проверьте в консоли: `🔍 Checking crypto payment status for: ...`
- Убедитесь, что endpoint `/api/donation/crypto/status/<id>/` отвечает

---

## 📊 Проверка готовности системы

### Минимальная готовность (без CoinGate токена):

- [x] API endpoints добавлены
- [x] Frontend правильно вызывает API
- [x] UI корректно отображается
- [x] Переключение между Card/Crypto работает
- [x] Валидация формы работает

### Полная готовность (с CoinGate токеном):

- [ ] CoinGate API токен настроен в `.env`
- [ ] `/api/donation/crypto-currencies/` возвращает список валют
- [ ] Создание платежа работает (POST `/api/donation/crypto/create-payment/`)
- [ ] QR-код генерируется
- [ ] Адрес для оплаты отображается
- [ ] Status polling работает (GET `/api/donation/crypto/status/<id>/`)
- [ ] Callback от CoinGate обрабатывается

---

## 🔥 Быстрый тест (30 секунд)

```bash
# 1. Перезапустите mini_app (чтобы применить новую версию donation.js)
docker compose restart mini_app

# 2. Откройте в браузере
open http://localhost:8080/settings?lang=ru

# 3. Откройте консоль разработчика (F12)

# 4. Проверьте, что НЕТ ошибки 404 для crypto-currencies
# Должен быть успешный запрос:
# GET /api/donation/crypto-currencies/ → 200 OK
```

---

## ✅ Система готова, если:

1. ✅ **НЕТ 404 ошибки** на `/api/donation/crypto-currencies/`
2. ✅ **Форма отображается** корректно (Card/Crypto переключение)
3. ✅ **Валидация работает** (имя, сумма)
4. ✅ **Кэш обновлен** (donation.js v3.0 загружается)

Для **полнофункциональной работы** с реальными платежами:
- 📌 Нужен реальный CoinGate API token
- 📌 Настроить webhook в CoinGate dashboard
- 📌 Протестировать с реальным тестовым платежом

---

## 🎓 Дополнительная информация

### CoinGate документация:
- https://developer.coingate.com/docs
- https://developer.coingate.com/docs/create-order

### Поддерживаемые стейблкоины:
- USDT (Tether)
- USDC (USD Coin)  
- BUSD (Binance USD)
- DAI

### Sandbox mode:
- Можно тестировать без реальных денег
- Используйте `COINGATE_ENVIRONMENT=sandbox` в `.env`

---

**📌 Важно:** Текущая версия (после этого фикса) готова к базовому тестированию.
Для production использования нужно настроить CoinGate API token.

