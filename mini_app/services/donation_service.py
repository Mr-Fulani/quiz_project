"""
Сервис для работы с системой донатов
Интегрируется с Django API для обработки платежей через Stripe
"""

import json
import logging
from typing import Dict, Optional, Any
from .django_api_service import DjangoAPIService

logger = logging.getLogger(__name__)


class DonationService:
    """Сервис для работы с донатами"""
    
    def __init__(self):
        from core.config import settings
        self.api_service = DjangoAPIService(settings.DJANGO_API_BASE_URL)
    
    async def create_payment_intent(
        self, 
        amount: float, 
        currency: str = 'usd', 
        email: str = '', 
        name: str = '',
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Создание Payment Intent для Stripe
        """
        try:
            url = "/donation/create-payment-intent/"
            data = {
                'amount': amount,
                'currency': currency,
                'email': email,
                'name': name,
                'source': 'mini_app'
            }
            
            logger.info(f"Creating payment intent: {amount} {currency}")
            response = await self.api_service._make_request("POST", url, json=data, headers=headers)
            
            if response.get('success'):
                return response
            else:
                logger.error(f"Failed to create payment intent: {response.get('message', 'Unknown error')}")
                return response
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return {'success': False, 'message': f'Ошибка создания платежа: {str(e)}'}
    
    async def confirm_payment(
        self, 
        payment_intent_id: str, 
        payment_method_id: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Подтверждение платежа
        """
        try:
            url = "/donation/confirm-payment/"
            data = {
                'payment_intent_id': payment_intent_id,
                'payment_method_id': payment_method_id
            }
            
            logger.info(f"Confirming payment: {payment_intent_id}")
            response = await self.api_service._make_request("POST", url, json=data, headers=headers)
            
            if response.get('success'):
                return response
            else:
                logger.error(f"Failed to confirm payment: {response.get('message', 'Unknown error')}")
                return response
        except Exception as e:
            logger.error(f"Error confirming payment: {str(e)}")
            return {'success': False, 'message': f'Ошибка подтверждения платежа: {str(e)}'}

    async def get_donation_stats(self) -> Dict[str, Any]:
        """
        Получение статистики донатов (если есть API endpoint)
        
        Returns:
            Dict со статистикой донатов
        """
        try:
            # Пока возвращаем базовую статистику
            # В будущем можно добавить API endpoint в Django
            return {
                'success': True,
                'total_donations': 0,
                'total_amount': 0,
                'currency': 'usd'
            }
        except Exception as e:
            logger.error(f"Error getting donation stats: {str(e)}")
            return {
                'success': False,
                'message': f'Ошибка получения статистики: {str(e)}'
            }
    
    def get_supported_currencies(self) -> Dict[str, str]:
        """
        Получение поддерживаемых валют
        
        Returns:
            Dict с кодами валют и их символами
        """
        return {
            'usd': 'USD ($)',
            'eur': 'EUR (€)',
            'rub': 'RUB (₽)'
        }
    
    def get_default_amounts(self) -> list:
        """
        Получение стандартных сумм для донатов
        
        Returns:
            List с суммами в долларах
        """
        return [1, 3, 5, 10, 25, 50]

    async def get_crypto_currencies(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Получение списка поддерживаемых криптовалют
        """
        try:
            url = "/donation/crypto/currencies/"
            logger.info("Getting crypto currencies list")
            response = await self.api_service._make_request("GET", url, headers=headers)
            
            if response.get('success'):
                return response
            else:
                logger.error(f"Failed to get crypto currencies: {response.get('message', 'Unknown error')}")
                return response
        except Exception as e:
            logger.error(f"Error getting crypto currencies: {str(e)}")
            return {'success': False, 'message': f'Ошибка получения списка криптовалют: {str(e)}'}
    
    async def create_crypto_payment(
        self,
        amount: float,
        crypto_currency: str,
        email: str = '',
        name: str = '',
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Создание крипто-платежа через CoinGate
        """
        try:
            url = "/donation/crypto/create-payment/"
            data = {
                'amount': amount,
                'crypto_currency': crypto_currency,
                'email': email,
                'name': name,
                'source': 'mini_app'
            }
            
            logger.info(f"Creating crypto payment: {amount} USD -> {crypto_currency}")
            response = await self.api_service._make_request("POST", url, json=data, headers=headers)
            
            if response.get('success'):
                return response
            else:
                logger.error(f"Failed to create crypto payment: {response.get('message', 'Unknown error')}")
                return response
        except Exception as e:
            logger.error(f"Error creating crypto payment: {str(e)}")
            return {'success': False, 'message': f'Ошибка создания крипто-платежа: {str(e)}'}
    
    async def check_crypto_payment_status(self, order_id: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Проверка статуса крипто-платежа
        """
        try:
            url = f"/donation/crypto/status/{order_id}/"
            logger.info(f"Checking crypto payment status: {order_id}")
            response = await self.api_service._make_request("GET", url, headers=headers)
            
            if response.get('success'):
                return response
            else:
                logger.error(f"Failed to get crypto payment status: {response.get('message', 'Unknown error')}")
                return response
        except Exception as e:
            logger.error(f"Error checking crypto payment status: {str(e)}")
            return {'success': False, 'message': f'Ошибка проверки статуса: {str(e)}'}

    async def create_wallet_pay_payment(
        self,
        amount: float,
        currency: str = 'USDT',
        email: str = '',
        name: str = '',
        telegram_id: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Создание платежа через Wallet Pay
        """
        try:
            url = "/donation/wallet-pay/create-payment/"
            data = {
                'amount': amount,
                'currency': currency,
                'email': email,
                'name': name,
                'telegram_id': telegram_id,
                'source': 'mini_app'
            }
            
            logger.info(f"Creating Wallet Pay payment: {amount} {currency}")
            response = await self.api_service._make_request("POST", url, json=data, headers=headers)
            
            if response.get('success'):
                return response
            else:
                logger.error(f"Failed to create Wallet Pay payment: {response.get('message', 'Unknown error')}")
                return response
        except Exception as e:
            logger.error(f"Error creating Wallet Pay payment: {str(e)}")
            return {'success': False, 'message': f'Ошибка создания платежа Wallet Pay: {str(e)}'} 