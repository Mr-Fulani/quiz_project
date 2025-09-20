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
        name: str = ''
    ) -> Dict[str, Any]:
        """
        Создание Payment Intent для Stripe
        
        Args:
            amount: Сумма доната
            currency: Валюта (usd, eur, rub)
            email: Email донатера
            name: Имя донатера
            
        Returns:
            Dict с данными Payment Intent или ошибкой
        """
        try:
            url = "/donation/create-payment-intent/"
            data = {
                'amount': amount,
                'currency': currency,
                'email': email,
                'name': name
            }
            
            logger.info(f"Creating payment intent: {amount} {currency}")
            response = await self.api_service._make_request("POST", url, json=data)
            
            if response.get('success'):
                logger.info(f"Payment intent created successfully: {response.get('client_secret', '')[:20]}...")
                return response
            else:
                logger.error(f"Failed to create payment intent: {response.get('message', 'Unknown error')}")
                return response
                
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return {
                'success': False,
                'message': f'Ошибка создания платежа: {str(e)}'
            }
    
    async def confirm_payment(
        self, 
        payment_intent_id: str, 
        payment_method_id: str
    ) -> Dict[str, Any]:
        """
        Подтверждение платежа
        
        Args:
            payment_intent_id: ID Payment Intent от Stripe
            payment_method_id: ID Payment Method от Stripe
            
        Returns:
            Dict с результатом подтверждения
        """
        try:
            url = "/donation/confirm-payment/"
            data = {
                'payment_intent_id': payment_intent_id,
                'payment_method_id': payment_method_id
            }
            
            logger.info(f"Confirming payment: {payment_intent_id}")
            response = await self.api_service._make_request("POST", url, json=data)
            
            if response.get('success'):
                logger.info("Payment confirmed successfully")
                return response
            else:
                logger.error(f"Failed to confirm payment: {response.get('message', 'Unknown error')}")
                return response
                
        except Exception as e:
            logger.error(f"Error confirming payment: {str(e)}")
            return {
                'success': False,
                'message': f'Ошибка подтверждения платежа: {str(e)}'
            }
    
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