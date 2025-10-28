# 💳 Интеграция Telegram Wallet для донатов

## 🎯 Рекомендуемый подход: Wallet Pay + CoinGate

### Почему два метода?

1. **Wallet Pay** - для пользователей Telegram (быстро, удобно)
2. **CoinGate** - для всех остальных (больше криптовалют)

---

## 🚀 Интеграция Wallet Pay

### Шаг 1: Регистрация в Wallet Pay

1. Откройте https://pay.wallet.tg/
2. Войдите через Telegram
3. Создайте Store (магазин)
4. Получите API ключ

### Шаг 2: Настройка Backend

#### 2.1. Добавьте в `.env`:
```bash
# Wallet Pay настройки
WALLET_PAY_API_KEY=ваш_api_ключ_здесь
WALLET_PAY_STORE_ID=ваш_store_id_здесь
```

#### 2.2. Создайте сервис:
```python
# quiz_backend/donation/wallet_pay_service.py

import logging
import requests
import hmac
import hashlib
import time
from typing import Dict, Any
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)


class WalletPayService:
    """Сервис для работы с Wallet Pay API"""
    
    BASE_URL = 'https://pay.wallet.tg/wpay/store-api/v1'
    
    def __init__(self):
        self.api_key = settings.WALLET_PAY_API_KEY
        self.store_id = settings.WALLET_PAY_STORE_ID
        
        self.headers = {
            'Wpay-Store-Api-Key': self.api_key,
            'Content-Type': 'application/json',
        }
        
        logger.info("Wallet Pay сервис инициализирован")
    
    def create_order(
        self,
        amount: Decimal,
        currency: str = 'USDT',
        description: str = 'Donation',
        external_id: str = '',
        customer_telegram_id: int = None,
        return_url: str = '',
        fail_return_url: str = '',
    ) -> Dict[str, Any]:
        """
        Создать заказ в Wallet Pay
        
        Args:
            amount: Сумма
            currency: Валюта (TON, USDT, BTC)
            description: Описание платежа
            external_id: Ваш внутренний ID заказа
            customer_telegram_id: Telegram ID пользователя
            return_url: URL для возврата после оплаты
            fail_return_url: URL для возврата при ошибке
            
        Returns:
            Dict с данными заказа
        """
        try:
            payload = {
                'amount': {
                    'amount': str(amount),
                    'currencyCode': currency
                },
                'description': description,
                'externalId': external_id,
                'timeoutSeconds': 3600,  # 1 час на оплату
            }
            
            # Опциональные параметры
            if customer_telegram_id:
                payload['customerTelegramUserId'] = customer_telegram_id
            
            if return_url:
                payload['returnUrl'] = return_url
                
            if fail_return_url:
                payload['failReturnUrl'] = fail_return_url
            
            logger.info(f"Создание заказа Wallet Pay: {amount} {currency}")
            
            response = requests.post(
                f'{self.BASE_URL}/order',
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'SUCCESS':
                order_data = data.get('data', {})
                logger.info(f"Заказ Wallet Pay создан: {order_data.get('id')}")
                
                return {
                    'success': True,
                    'order_id': order_data.get('id'),
                    'status': order_data.get('status'),
                    'pay_link': order_data.get('payLink'),
                    'direct_pay_link': order_data.get('directPayLink'),
                }
            else:
                error_msg = data.get('message', 'Unknown error')
                logger.error(f"Ошибка создания заказа Wallet Pay: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP ошибка Wallet Pay: {e}")
            try:
                error_data = e.response.json()
                error_message = error_data.get('message', str(e))
            except:
                error_message = str(e)
            
            return {
                'success': False,
                'error': error_message
            }
            
        except Exception as e:
            logger.error(f"Ошибка при создании заказа Wallet Pay: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_order_preview(self, order_id: str) -> Dict[str, Any]:
        """
        Получить информацию о заказе
        
        Args:
            order_id: ID заказа Wallet Pay
            
        Returns:
            Dict с данными заказа
        """
        try:
            response = requests.get(
                f'{self.BASE_URL}/order/preview',
                params={'id': order_id},
                headers=self.headers,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'SUCCESS':
                order = data.get('data', {})
                return {
                    'success': True,
                    'order_id': order.get('id'),
                    'status': order.get('status'),
                    'amount': order.get('amount'),
                    'created_at': order.get('createdDateTime'),
                    'paid_at': order.get('paidDateTime'),
                }
            
            return {
                'success': False,
                'error': data.get('message', 'Unknown error')
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении заказа Wallet Pay: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_webhook(self, signature: str, body: str) -> bool:
        """
        Проверить подпись webhook от Wallet Pay
        
        Args:
            signature: Подпись из заголовка X-Wallet-Pay-Signature
            body: Тело запроса (raw string)
            
        Returns:
            bool: True если подпись валидна
        """
        try:
            expected_signature = hmac.new(
                self.api_key.encode('utf-8'),
                body.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Ошибка проверки webhook: {e}")
            return False
```

#### 2.3. Добавьте view:
```python
# quiz_backend/donation/views.py

from .wallet_pay_service import WalletPayService

@api_view(['POST'])
@csrf_exempt
def create_wallet_pay_payment(request):
    """Создание платежа через Wallet Pay"""
    try:
        from .wallet_pay_service import WalletPayService
        
        data = json.loads(request.body)
        amount = data.get('amount')
        currency = data.get('currency', 'USDT')
        name = data.get('name', 'Anonymous')
        telegram_id = data.get('telegram_id')
        source = data.get('source', 'mini_app')
        
        # Валидация
        if not amount or float(amount) < 1:
            return JsonResponse({
                'success': False,
                'message': 'Invalid amount'
            }, status=400)
        
        # Создаем запись в БД
        donation = Donation.objects.create(
            name=name,
            amount=amount,
            currency='usd',  # Wallet Pay конвертирует автоматически
            status='pending',
            payment_type='crypto',
            payment_method='wallet_pay',
            source=source,
        )
        
        # Создаем заказ в Wallet Pay
        service = WalletPayService()
        result = service.create_order(
            amount=Decimal(amount),
            currency=currency,
            description=f'Donation #{donation.id}',
            external_id=str(donation.id),
            customer_telegram_id=telegram_id,
            return_url=f'https://ваш-домен/donation/success?order_id={donation.id}',
            fail_return_url=f'https://ваш-домен/donation/failed?order_id={donation.id}',
        )
        
        if result.get('success'):
            # Сохраняем данные заказа
            donation.wallet_pay_order_id = result.get('order_id')
            donation.save()
            
            return JsonResponse({
                'success': True,
                'order_id': result.get('order_id'),
                'pay_link': result.get('pay_link'),
                'direct_pay_link': result.get('direct_pay_link'),
                'donation_id': donation.id,
            })
        else:
            donation.status = 'failed'
            donation.save()
            
            return JsonResponse({
                'success': False,
                'message': result.get('error', 'Failed to create payment')
            }, status=400)
            
    except Exception as e:
        logger.error(f"Error creating Wallet Pay payment: {e}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def wallet_pay_webhook(request):
    """Webhook для уведомлений от Wallet Pay"""
    try:
        signature = request.headers.get('X-Wallet-Pay-Signature')
        body = request.body.decode('utf-8')
        
        service = WalletPayService()
        
        if not service.verify_webhook(signature, body):
            logger.warning("Invalid Wallet Pay webhook signature")
            return JsonResponse({'error': 'Invalid signature'}, status=400)
        
        data = json.loads(body)
        event_type = data.get('eventType')
        order_data = data.get('order', {})
        
        external_id = order_data.get('externalId')
        status = order_data.get('status')
        
        if external_id:
            try:
                donation = Donation.objects.get(id=int(external_id))
                
                if status == 'PAID':
                    donation.status = 'completed'
                    donation.save()
                    
                    # Отправляем email
                    if donation.email:
                        send_donation_thank_you_email(donation)
                    
                    logger.info(f"Wallet Pay payment completed: {external_id}")
                    
                elif status == 'EXPIRED' or status == 'CANCELLED':
                    donation.status = 'failed'
                    donation.save()
                    
            except Donation.DoesNotExist:
                logger.error(f"Donation not found: {external_id}")
        
        return JsonResponse({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"Error processing Wallet Pay webhook: {e}")
        return JsonResponse({'error': str(e)}, status=500)
```

#### 2.4. Обновите URLs:
```python
# quiz_backend/config/urls.py

from donation.views import create_wallet_pay_payment, wallet_pay_webhook

urlpatterns = [
    # ... существующие URLs ...
    
    # Wallet Pay endpoints
    path('api/donation/wallet-pay/create-payment/', create_wallet_pay_payment, name='wallet_pay_create'),
    path('api/donation/wallet-pay/webhook/', wallet_pay_webhook, name='wallet_pay_webhook'),
]
```

#### 2.5. Обновите модель:
```python
# quiz_backend/donation/models.py

class Donation(models.Model):
    # ... существующие поля ...
    
    # Wallet Pay
    wallet_pay_order_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Wallet Pay Order ID'
    )
```

### Шаг 3: Обновите Frontend

#### 3.1. Добавьте кнопку Telegram Wallet:
```javascript
// mini_app/static/js/donation.js

class DonationSystem {
    constructor() {
        // ... существующий код ...
        this.paymentMethod = 'card';  // 'card', 'crypto', 'telegram_wallet'
    }
    
    bindEvents() {
        // ... существующий код ...
        
        // Telegram Wallet button
        const telegramWalletBtn = document.querySelector('.telegram-wallet-btn');
        if (telegramWalletBtn) {
            telegramWalletBtn.addEventListener('click', () => {
                this.processTelegramWalletPayment();
            });
        }
    }
    
    async processTelegramWalletPayment() {
        if (this.isProcessing) return;
        
        // Валидация
        if (!this.validateForm()) {
            return;
        }
        
        this.isProcessing = true;
        
        try {
            const formData = {
                amount: this.selectedAmount,
                currency: 'USDT',  // или выбранная пользователем
                name: document.querySelector('.donation-name').value.trim(),
                telegram_id: window.currentUser?.telegram_id,
                source: 'mini_app'
            };
            
            // Создаем платеж
            const response = await fetch('/api/donation/wallet-pay/create-payment/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Открываем Telegram Wallet для оплаты
                if (window.Telegram?.WebApp) {
                    // Используем direct_pay_link для прямого открытия в кошельке
                    window.Telegram.WebApp.openTelegramLink(data.direct_pay_link);
                    
                    this.showNotification('success',
                        'Открыт Telegram Wallet',
                        'Завершите платеж в кошельке'
                    );
                } else {
                    // Fallback для браузера
                    window.open(data.pay_link, '_blank');
                }
                
                // Показываем статус ожидания
                this.showPaymentWaiting(data.order_id);
                
            } else {
                throw new Error(data.message || 'Failed to create payment');
            }
            
        } catch (error) {
            console.error('❌ Error:', error);
            this.showNotification('error', 'Ошибка', error.message);
        } finally {
            this.isProcessing = false;
        }
    }
    
    showPaymentWaiting(orderId) {
        // Показываем UI ожидания платежа
        // Можно добавить polling для проверки статуса
    }
}
```

#### 3.2. Обновите HTML:
```html
<!-- mini_app/templates/donation_section.html -->

<div class="payment-methods">
    <label class="payment-method-option">
        <input type="radio" name="payment_method" value="card" checked>
        <span>💳 Card Payment</span>
    </label>
    
    <label class="payment-method-option">
        <input type="radio" name="payment_method" value="crypto">
        <span>🪙 Crypto (CoinGate)</span>
    </label>
    
    <label class="payment-method-option">
        <input type="radio" name="payment_method" value="telegram_wallet">
        <span>💎 Telegram Wallet</span>
    </label>
</div>

<!-- Форма для Telegram Wallet -->
<div class="telegram-wallet-form" style="display: none;">
    <div class="currency-selector">
        <label>Выберите валюту:</label>
        <select class="wallet-currency">
            <option value="TON">TON</option>
            <option value="USDT" selected>USDT</option>
            <option value="BTC">Bitcoin</option>
        </select>
    </div>
    
    <button class="telegram-wallet-btn">
        💎 Оплатить через Telegram Wallet
    </button>
</div>
```

### Шаг 4: Настройте Webhook в Wallet Pay

1. Откройте https://pay.wallet.tg/
2. Перейдите в настройки Store
3. Добавьте Webhook URL:
```
https://ваш-домен/api/donation/wallet-pay/webhook/
```

---

## 📊 Сравнение методов

| Метод | Комиссия | Сложность | Автоматизация | Валюты |
|-------|----------|-----------|---------------|--------|
| **Wallet Pay** | ~1% | Средняя | ✅ Полная | TON, USDT, BTC |
| **CoinGate** (текущий) | ~1% | Средняя | ✅ Полная | USDT, USDC, BUSD, DAI |
| **TON Connect** | Gas only | Высокая | ⚠️ Частичная | Только TON |
| **@wallet вручную** | Минимальная | Низкая | ❌ Ручная | Все |

---

## 🎯 Рекомендуемая стратегия

1. **Оставьте CoinGate** - для широкого выбора стейблкоинов
2. **Добавьте Wallet Pay** - для пользователей Telegram (удобнее)
3. **Опционально TON Connect** - если хотите принимать TON

---

## ✅ Чек-лист внедрения

- [ ] Зарегистрироваться в Wallet Pay
- [ ] Получить API ключ
- [ ] Добавить в `.env`
- [ ] Создать `wallet_pay_service.py`
- [ ] Добавить views и URLs
- [ ] Обновить модель Donation
- [ ] Обновить frontend (donation.js)
- [ ] Настроить webhook
- [ ] Протестировать платеж
- [ ] Задеплоить на production

---

## 📚 Полезные ссылки

- **Wallet Pay Docs:** https://docs.wallet.tg/
- **TON Connect:** https://docs.ton.org/develop/dapps/ton-connect/
- **Telegram Wallet Bot:** https://t.me/wallet
- **Примеры интеграции:** https://github.com/wallet-pay

---

**💡 Совет:** Начните с Wallet Pay - это самый простой способ интегрировать Telegram криптокошелек с автоматической обработкой платежей!

