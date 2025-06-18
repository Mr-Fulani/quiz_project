# 🔧 Настройка Stripe для Production

## 📋 Чек-лист готовности

### ✅ Что уже готово:
- [x] Stripe интеграция в основную страницу donation
- [x] Поддержка трех валют: USD, EUR, RUB
- [x] Улучшенная обработка ошибок
- [x] Webhook для надежности платежей
- [x] Красивый дизайн с SVG картами
- [x] Тестовая страница для проверки

### 🔧 Что нужно настроить для production:

## 1. 🌐 Настройка Stripe Dashboard

### Получение ключей:
1. Зайдите на https://dashboard.stripe.com
2. Переключитесь в **Live mode** (правый верхний угол)
3. Перейдите в **Developers** → **API keys**
4. Скопируйте:
   - **Publishable key** (начинается с `pk_live_`)
   - **Secret key** (начинается с `sk_live_`)

### Настройка Webhook:
1. Перейдите в **Developers** → **Webhooks**
2. Нажмите **Add endpoint**
3. URL: `https://ваш-домен.com/donation/stripe-webhook/`
4. Выберите события:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `payment_intent.canceled`
5. Скопируйте **Webhook signing secret** (начинается с `whsec_`)

## 2. 🔐 Переменные окружения

Добавьте в ваш `.env` файл:

```bash
# Stripe Production Keys
STRIPE_PUBLISHABLE_KEY=pk_live_ваш_публичный_ключ
STRIPE_SECRET_KEY=sk_live_ваш_секретный_ключ
STRIPE_WEBHOOK_SECRET=whsec_ваш_webhook_секрет
```

## 3. 🚀 Доступные функции

### 💳 Поддерживаемые валюты:
- **USD** ($) - доллары США
- **EUR** (€) - евро
- **RUB** (₽) - российские рубли

### 🃏 Тестовые карты:
- **Успешная оплата:** `4242 4242 4242 4242`
- **Отклонена:** `4000 0000 0000 0002`
- **Недостаточно средств:** `4000 0000 0000 9995`
- **Требует аутентификации:** `4000 0000 0000 3220`

### 📱 Страницы:
- **Основная:** `/donation/` - красивая страница с SVG анимацией
- **Тестовая:** `/donation/test/` - простая страница для тестирования

## 4. 🔍 Мониторинг и логи

### Проверка статуса платежей:
- Админка Django: `/admin/donation/donation/`
- Stripe Dashboard: https://dashboard.stripe.com/payments

### Логи webhook:
- Stripe Dashboard → **Developers** → **Webhooks** → выберите ваш endpoint
- Логи Django в консоли сервера

## 5. 🛡️ Безопасность

### Обязательные проверки:
- [ ] HTTPS включен на production
- [ ] Webhook secret настроен
- [ ] Live ключи не попали в git
- [ ] CSRF защита включена
- [ ] Rate limiting настроен

### Рекомендации:
- Используйте разные ключи для development/production
- Регулярно ротируйте webhook secret
- Мониторьте подозрительную активность в Stripe Dashboard

## 6. 🐛 Отладка

### Частые проблемы:

**"Stripe not available":**
- Проверьте что publishable key передается в шаблон
- Убедитесь что Stripe.js загружается

**"Invalid signature" в webhook:**
- Проверьте webhook secret в .env
- Убедитесь что URL webhook правильный

**"Card declined":**
- Проверьте в Stripe Dashboard причину отклонения
- Убедитесь что карта поддерживает валюту

**Платеж завис в "pending":**
- Проверьте webhook логи
- Убедитесь что webhook endpoint доступен

### Тестирование webhook локально:
```bash
# Установите Stripe CLI
stripe login
stripe listen --forward-to localhost:8001/donation/stripe-webhook/
```

## 7. 📊 Аналитика

В Stripe Dashboard доступны:
- Графики платежей по времени
- Конверсия по странам
- Анализ отклоненных платежей
- Отчеты по валютам

## 8. 🔄 Обновления

### При изменении кода:
1. Протестируйте на тестовой странице
2. Проверьте webhook в Stripe CLI
3. Деплойте изменения
4. Проверьте production webhook

### Мониторинг:
- Настройте алерты в Stripe Dashboard
- Мониторьте логи Django
- Проверяйте успешность webhook

---

## 🎯 Готово к использованию!

Ваша donation система полностью интегрирована с Stripe и готова к production использованию. Все платежи будут обрабатываться надежно с поддержкой webhook для максимальной надежности. 