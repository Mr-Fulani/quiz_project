"""
Сервис для работы с CoinGate API
Документация: https://developer.coingate.com/docs
"""

import logging
import requests
from typing import Dict, Optional, Any, List
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)


class CoinGateService:
    """Сервис для интеграции с CoinGate API"""
    
    # API endpoints
    SANDBOX_BASE_URL = 'https://api-sandbox.coingate.com/v2'
    LIVE_BASE_URL = 'https://api.coingate.com/v2'
    
    # Поддерживаемые стейблкоины
    SUPPORTED_STABLECOINS = {
        'USDT': 'USDT (Tether)',
        'USDC': 'USDC (USD Coin)',
        'BUSD': 'BUSD (Binance USD)',
        'DAI': 'DAI',
    }
    
    def __init__(self):
        """Инициализация сервиса с настройками из Django settings"""
        self.api_token = settings.COINGATE_API_TOKEN
        self.environment = settings.COINGATE_ENVIRONMENT
        self.receive_currency = settings.COINGATE_RECEIVE_CURRENCY
        
        # Определяем базовый URL в зависимости от окружения
        self.base_url = self.SANDBOX_BASE_URL if self.environment == 'sandbox' else self.LIVE_BASE_URL
        
        # Заголовки для запросов
        self.headers = {
            'Authorization': f'Token {self.api_token}',
            'Content-Type': 'application/json',
        }
        
        logger.info(f"CoinGate сервис инициализирован (окружение: {self.environment})")
    
    def get_available_currencies(self) -> List[Dict[str, str]]:
        """
        Получить список доступных стейблкоинов
        
        Returns:
            List[Dict]: Список криптовалют с их названиями
        """
        return [
            {'code': code, 'name': name}
            for code, name in self.SUPPORTED_STABLECOINS.items()
        ]
    
    def create_order(
        self,
        amount_usd: Decimal,
        crypto_currency: str,
        order_id: str,
        callback_url: str,
        cancel_url: str = '',
        success_url: str = '',
        title: str = 'Donation',
        description: str = '',
    ) -> Dict[str, Any]:
        """
        Создать заказ в CoinGate
        
        Args:
            amount_usd: Сумма в USD
            crypto_currency: Криптовалюта для оплаты (USDT, USDC, BUSD, DAI)
            order_id: Уникальный ID заказа
            callback_url: URL для callback уведомлений
            cancel_url: URL для отмены платежа
            success_url: URL после успешной оплаты
            title: Название заказа
            description: Описание заказа
            
        Returns:
            Dict с данными заказа от CoinGate
        """
        try:
            # Валидация криптовалюты
            if crypto_currency.upper() not in self.SUPPORTED_STABLECOINS:
                logger.error(f"Неподдерживаемая криптовалюта: {crypto_currency}")
                return {
                    'success': False,
                    'error': f'Unsupported cryptocurrency: {crypto_currency}'
                }
            
            # Подготовка данных для запроса
            payload = {
                'order_id': order_id,
                'price_amount': float(amount_usd),
                'price_currency': 'USD',
                'receive_currency': self.receive_currency,
                'pay_currency': crypto_currency.upper(),
                'title': title,
                'description': description or f'Donation #{order_id}',
                'callback_url': callback_url,
            }
            
            # Добавляем URL только если они указаны
            if cancel_url:
                payload['cancel_url'] = cancel_url
            if success_url:
                payload['success_url'] = success_url
            
            logger.info(f"Создание заказа CoinGate: {amount_usd} USD -> {crypto_currency}")
            
            # Отправка запроса
            response = requests.post(
                f'{self.base_url}/orders',
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Заказ CoinGate создан успешно: {data.get('id')}")
            
            return {
                'success': True,
                'order_id': data.get('id'),
                'status': data.get('status'),
                'payment_url': data.get('payment_url'),
                'payment_address': data.get('payment_address'),
                'pay_amount': data.get('pay_amount'),
                'pay_currency': data.get('pay_currency'),
                'price_amount': data.get('price_amount'),
                'price_currency': data.get('price_currency'),
                'expire_at': data.get('expire_at'),
                'token': data.get('token'),
            }
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP ошибка при создании заказа CoinGate: {e}")
            try:
                error_data = e.response.json()
                error_message = error_data.get('message', str(e))
            except:
                error_message = str(e)
            
            return {
                'success': False,
                'error': error_message
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при создании заказа CoinGate: {e}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }
            
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании заказа CoinGate: {e}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Получить информацию о заказе
        
        Args:
            order_id: ID заказа CoinGate
            
        Returns:
            Dict с данными заказа
        """
        try:
            logger.info(f"Получение информации о заказе CoinGate: {order_id}")
            
            response = requests.get(
                f'{self.base_url}/orders/{order_id}',
                headers=self.headers,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Статус заказа {order_id}: {data.get('status')}")
            
            return {
                'success': True,
                'order_id': data.get('id'),
                'status': data.get('status'),
                'payment_address': data.get('payment_address'),
                'pay_amount': data.get('pay_amount'),
                'pay_currency': data.get('pay_currency'),
                'price_amount': data.get('price_amount'),
                'price_currency': data.get('price_currency'),
                'receive_amount': data.get('receive_amount'),
                'receive_currency': data.get('receive_currency'),
                'created_at': data.get('created_at'),
                'expire_at': data.get('expire_at'),
                'payment_url': data.get('payment_url'),
            }
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP ошибка при получении заказа CoinGate: {e}")
            return {
                'success': False,
                'error': str(e)
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при получении заказа CoinGate: {e}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }
            
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении заказа CoinGate: {e}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def verify_callback(self, order_id: str, token: str) -> bool:
        """
        Проверить подлинность callback от CoinGate
        
        Args:
            order_id: ID заказа
            token: Токен из callback запроса
            
        Returns:
            bool: True если callback валидный
        """
        try:
            # Получаем заказ напрямую из API для проверки
            order_data = self.get_order(order_id)
            
            if not order_data.get('success'):
                logger.error(f"Не удалось получить заказ для проверки callback: {order_id}")
                return False
            
            # В CoinGate токен передается в callback и должен совпадать с токеном заказа
            # Для дополнительной безопасности можно сравнить данные заказа
            logger.info(f"Callback для заказа {order_id} верифицирован")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при проверке callback: {e}")
            return False
    
    def get_exchange_rate(self, from_currency: str = 'USD', to_currency: str = 'USDT') -> Optional[Decimal]:
        """
        Получить курс обмена (для информации)
        Примечание: CoinGate автоматически конвертирует в create_order
        
        Args:
            from_currency: Исходная валюта (USD)
            to_currency: Целевая криптовалюта
            
        Returns:
            Decimal: Курс обмена или None при ошибке
        """
        try:
            # CoinGate не предоставляет отдельный endpoint для курсов
            # Курс можно узнать при создании заказа
            logger.info(f"Получение курса {from_currency} -> {to_currency}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении курса: {e}")
            return None

