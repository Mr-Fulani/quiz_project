"""
Сервис для работы с Telegram Wallet Pay API.

Все докстринги и комментарии на русском языке в соответствии с требованиями проекта.
"""

from __future__ import annotations

import logging
import hmac
import hashlib
from decimal import Decimal
from typing import Any, Dict, Optional

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class WalletPayService:
    """Сервис интеграции с Wallet Pay API (Telegram)."""

    BASE_URL = 'https://pay.wallet.tg/wpay/store-api/v1'

    def __init__(self) -> None:
        """Инициализирует сервис с использованием настроек из Django."""
        self.api_key: str = settings.WALLET_PAY_API_KEY or ''
        self.store_id: str = settings.WALLET_PAY_STORE_ID or ''

        self.headers: Dict[str, str] = {
            'Wpay-Store-Api-Key': self.api_key,
            'Content-Type': 'application/json',
        }

        logger.info("Wallet Pay сервис инициализирован")

    def create_order(
        self,
        *,
        amount: Decimal,
        currency: str = 'USDT',
        description: str = 'Donation',
        external_id: str = '',
        customer_telegram_id: Optional[int] = None,
        return_url: str = '',
        fail_return_url: str = '',
        timeout_seconds: int = 3600,
    ) -> Dict[str, Any]:
        """
        Создаёт заказ в Wallet Pay.

        Args:
            amount: Сумма доната.
            currency: Валюта (например, 'USDT', 'TON', 'BTC').
            description: Описание платежа.
            external_id: Ваш внутренний идентификатор заказа (для сопоставления с Donation).
            customer_telegram_id: Telegram ID пользователя (если есть).
            return_url: URL возврата при успехе.
            fail_return_url: URL возврата при ошибке.
            timeout_seconds: Таймаут оплаты в секундах.

        Returns:
            Словарь с результатом создания заказа.
        """
        try:
            payload: Dict[str, Any] = {
                'amount': {
                    'amount': str(amount),
                    'currencyCode': currency,
                },
                'description': description,
                'externalId': external_id,
                'timeoutSeconds': timeout_seconds,
            }

            if customer_telegram_id:
                payload['customerTelegramUserId'] = customer_telegram_id
            if return_url:
                payload['returnUrl'] = return_url
            if fail_return_url:
                payload['failReturnUrl'] = fail_return_url

            response = requests.post(
                f'{self.BASE_URL}/order',
                json=payload,
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json()

            if data.get('status') == 'SUCCESS':
                order = data.get('data', {})
                return {
                    'success': True,
                    'order_id': order.get('id'),
                    'status': order.get('status'),
                    'pay_link': order.get('payLink'),
                    'direct_pay_link': order.get('directPayLink'),
                }

            return {'success': False, 'error': data.get('message', 'Unknown error')}

        except requests.exceptions.HTTPError as e:  # pragma: no cover - сетевые ошибки
            try:
                err = e.response.json().get('message', str(e))
            except Exception:  # noqa: BLE001
                err = str(e)
            logger.error(f"HTTP ошибка Wallet Pay: {err}")
            return {'success': False, 'error': err}
        except Exception as e:  # noqa: BLE001
            logger.error(f"Ошибка при создании заказа Wallet Pay: {e}")
            return {'success': False, 'error': str(e)}

    def get_order_preview(self, order_id: str) -> Dict[str, Any]:
        """
        Получает информацию о заказе Wallet Pay.

        Args:
            order_id: Идентификатор заказа Wallet Pay.

        Returns:
            Словарь с данными заказа.
        """
        try:
            response = requests.get(
                f'{self.BASE_URL}/order/preview',
                params={'id': order_id},
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'SUCCESS':
                return {'success': True, 'data': data.get('data', {})}

            return {'success': False, 'error': data.get('message', 'Unknown error')}

        except Exception as e:  # noqa: BLE001
            logger.error(f"Ошибка при получении заказа Wallet Pay: {e}")
            return {'success': False, 'error': str(e)}

    def verify_webhook(self, signature: str, body: str) -> bool:
        """
        Проверяет подпись webhook от Wallet Pay через HMAC SHA-256.

        Args:
            signature: Подпись из заголовка X-Wallet-Pay-Signature.
            body: Исходное тело запроса (строка).

        Returns:
            True если подпись валидна, иначе False.
        """
        try:
            expected = hmac.new(self.api_key.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest()
            return hmac.compare_digest(signature or '', expected)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Ошибка проверки подписи Wallet Pay webhook: {e}")
            return False


