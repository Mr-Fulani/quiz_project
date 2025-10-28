"""
Сервис для работы с Telegram Stars - встроенной валютой Telegram.

Все докстринги и комментарии на русском языке в соответствии с требованиями проекта.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class TelegramStarsService:
    """Сервис интеграции с Telegram Stars (встроенная валюта Telegram)."""

    def __init__(self) -> None:
        """Инициализирует сервис с использованием настроек из Django."""
        self.bot_token: str = settings.TELEGRAM_BOT_TOKEN or ''
        self.base_url: str = f'https://api.telegram.org/bot{self.bot_token}'

        logger.info("Telegram Stars сервис инициализирован")

    def create_invoice_link(
        self,
        *,
        title: str,
        description: str,
        payload: str,
        currency: str = 'XTR',
        prices: list[Dict[str, Any]],
        provider_token: str = '',
        photo_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Создаёт ссылку на инвойс для оплаты Telegram Stars.

        Args:
            title: Название продукта (максимум 32 символа).
            description: Описание продукта (максимум 255 символов).
            payload: Bot-defined invoice payload (до 128 байт) для идентификации платежа.
            currency: Валюта (для Stars всегда 'XTR').
            prices: Список цен в формате [{"label": "Donation", "amount": 100}].
            provider_token: Пустая строка для Stars (не требуется).
            photo_url: URL изображения для инвойса (опционально).

        Returns:
            Словарь с результатом создания инвойса.
        """
        try:
            payload_data: Dict[str, Any] = {
                'title': title[:32],  # Ограничение Telegram API
                'description': description[:255],  # Ограничение Telegram API
                'payload': payload,
                'currency': currency,
                'prices': prices,
            }

            # Для Telegram Stars provider_token должен быть пустой строкой
            if currency == 'XTR':
                payload_data['provider_token'] = ''
            elif provider_token:
                payload_data['provider_token'] = provider_token

            if photo_url:
                payload_data['photo_url'] = photo_url

            logger.info(f"Создание инвойса Telegram Stars: {title}, сумма: {prices}")

            response = requests.post(
                f'{self.base_url}/createInvoiceLink',
                json=payload_data,
                timeout=30,
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json()

            if data.get('ok'):
                invoice_link = data.get('result')
                logger.info(f"Инвойс Telegram Stars создан: {invoice_link[:50]}...")
                return {
                    'success': True,
                    'invoice_link': invoice_link,
                    'payload': payload,
                }

            error_msg = data.get('description', 'Unknown error')
            logger.error(f"Ошибка создания инвойса: {error_msg}")
            return {'success': False, 'error': error_msg}

        except requests.exceptions.HTTPError as e:
            try:
                err = e.response.json().get('description', str(e))
            except Exception:  # noqa: BLE001
                err = str(e)
            logger.error(f"HTTP ошибка Telegram Stars API: {err}")
            return {'success': False, 'error': err}
        except Exception as e:  # noqa: BLE001
            logger.error(f"Ошибка при создании инвойса Telegram Stars: {e}")
            return {'success': False, 'error': str(e)}

    def refund_star_payment(
        self,
        *,
        user_id: int,
        telegram_payment_charge_id: str,
    ) -> Dict[str, Any]:
        """
        Возвращает оплату Telegram Stars пользователю.

        Args:
            user_id: Telegram ID пользователя.
            telegram_payment_charge_id: ID платежа из successful_payment.

        Returns:
            Словарь с результатом возврата.
        """
        try:
            payload_data: Dict[str, Any] = {
                'user_id': user_id,
                'telegram_payment_charge_id': telegram_payment_charge_id,
            }

            logger.info(f"Возврат Stars платежа: {telegram_payment_charge_id}")

            response = requests.post(
                f'{self.base_url}/refundStarPayment',
                json=payload_data,
                timeout=30,
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json()

            if data.get('ok'):
                logger.info(f"Stars платеж успешно возвращен: {telegram_payment_charge_id}")
                return {'success': True}

            error_msg = data.get('description', 'Unknown error')
            logger.error(f"Ошибка возврата Stars: {error_msg}")
            return {'success': False, 'error': error_msg}

        except Exception as e:  # noqa: BLE001
            logger.error(f"Ошибка при возврате Stars платежа: {e}")
            return {'success': False, 'error': str(e)}

