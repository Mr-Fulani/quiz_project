from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import logging
import stripe
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.decorators import api_view


from .forms import DonationForm
from .models import Donation
from .utils import send_donation_thank_you_email

logger = logging.getLogger(__name__)

# Настройка Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Проверяем что ключи настроены
if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith('sk_test_51234'):
    logger.warning("Stripe secret key not configured properly!")
if not settings.STRIPE_PUBLISHABLE_KEY or settings.STRIPE_PUBLISHABLE_KEY.startswith('pk_test_51234'):
    logger.warning("Stripe publishable key not configured properly!")


def donation_page(request):
    """Страница donation с формой оплаты"""
    # Теперь обработка платежей происходит через JavaScript + Stripe API
    # Этот view только отображает форму
    
    form = DonationForm()
    # Если пользователь авторизован, предзаполняем email
    if request.user.is_authenticated:
        form.initial['email'] = request.user.email
    
    context = {
        'form': form,
        'title': _('Support'),
        'page_title': _('Donation'),
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    }
    return render(request, 'donation/donation_page.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def create_payment_intent(request):
    """Создание Payment Intent для Stripe"""
    logger.info(f"Create payment intent request received: {request.body}")
    try:
        data = json.loads(request.body)
        amount = data.get('amount')
        currency = data.get('currency', 'usd')
        email = data.get('email', '')
        name = data.get('name', '')
        source = data.get('source', 'website')  # Получаем источник доната
        logger.info(f"Payment intent data: amount={amount}, currency={currency}, email={email}, name={name}, source={source}")
        
        # Валидация данных
        if not amount or float(amount) < 1:
            return JsonResponse({
                'success': False,
                'message': _('Invalid amount. Minimum amount is $1.00')
            }, status=400)
        
        if not name or not name.strip():
            return JsonResponse({
                'success': False,
                'message': _('Name is required')
            }, status=400)
        
        # Проверка поддерживаемых валют
        supported_currencies = ['usd', 'eur', 'rub']
        if currency not in supported_currencies:
            return JsonResponse({
                'success': False,
                'message': _('Unsupported currency')
            }, status=400)
        
        # Конвертируем в центы для Stripe (для RUB не нужно умножать на 100)
        if currency == 'rub':
            amount_cents = int(float(amount))
        else:
            amount_cents = int(float(amount) * 100)
        
        # Создаем Payment Intent
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            metadata={
                'user_email': email,
                'user_name': name,
                'source': source,  # Добавляем источник в metadata
            },
            automatic_payment_methods={
                'enabled': True,
            }
        )
        
        logger.info(f"Payment intent created: {intent.id} for {amount} {currency}")
        
        return JsonResponse({
            'success': True,
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id
        })
        
    except stripe.error.CardError as e:
        logger.error(f"Stripe card error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Card error: ') + str(e.user_message)
        }, status=400)
        
    except stripe.error.RateLimitError as e:
        logger.error(f"Stripe rate limit error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Too many requests. Please try again later.')
        }, status=429)
        
    except stripe.error.InvalidRequestError as e:
        logger.error(f"Stripe invalid request error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Invalid request parameters')
        }, status=400)
        
    except stripe.error.AuthenticationError as e:
        logger.error(f"Stripe authentication error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Authentication error. Please contact support.')
        }, status=500)
        
    except stripe.error.APIConnectionError as e:
        logger.error(f"Stripe API connection error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Network error. Please check your connection.')
        }, status=500)
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Payment service error. Please try again.')
        }, status=500)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({
            'success': False,
            'message': _('Invalid request format')
        }, status=400)
        
    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Invalid amount format')
        }, status=400)
        
    except Exception as e:
        logger.error(f"Unexpected error creating payment intent: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('An unexpected error occurred. Please try again.')
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_payment_method(request):
    """Создание payment method на сервере"""
    try:
        data = json.loads(request.body)
        
        # Получаем данные карты
        card_number = data.get('card_number')
        exp_month = data.get('exp_month')
        exp_year = data.get('exp_year')
        cvc = data.get('cvc')
        name = data.get('name', '')
        email = data.get('email', '')
        
        # Валидация
        if not all([card_number, exp_month, exp_year, cvc]):
            return JsonResponse({
                'success': False,
                'message': _('All card fields are required')
            }, status=400)
        
        # Создаем payment method в Stripe
        payment_method = stripe.PaymentMethod.create(
            type='card',
            card={
                'number': card_number,
                'exp_month': exp_month,
                'exp_year': exp_year,
                'cvc': cvc,
            },
            billing_details={
                'name': name,
                'email': email,
            }
        )
        
        return JsonResponse({
            'success': True,
            'payment_method_id': payment_method.id
        })
        
    except stripe.error.CardError as e:
        logger.error(f"Stripe card error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e.user_message)
        }, status=400)
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Payment method creation error')
        }, status=400)
        
    except Exception as e:
        logger.error(f"Payment method creation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('An error occurred')
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def confirm_payment(request):
    """Подтверждение успешного платежа"""
    logger.info(f"Confirm payment request received: {request.body}")
    try:
        data = json.loads(request.body)
        payment_intent_id = data.get('payment_intent_id')
        logger.info(f"Payment intent ID: {payment_intent_id}")
        
        if not payment_intent_id:
            return JsonResponse({
                'success': False,
                'message': _('Payment intent ID required')
            }, status=400)
        
        # Получаем Payment Intent из Stripe
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        if intent.status == 'succeeded':
            # Конвертируем сумму в зависимости от валюты
            if intent.currency == 'rub':
                amount = intent.amount  # RUB не конвертируем
            else:
                amount = intent.amount / 100  # USD/EUR конвертируем из центов
            
            # Создаем или обновляем donation
            donation, created = Donation.objects.get_or_create(
                stripe_payment_intent_id=payment_intent_id,
                defaults={
                    'amount': amount,
                    'currency': intent.currency,
                    'status': 'completed',
                    'name': intent.metadata.get('user_name', 'Anonymous'),
                    'email': intent.metadata.get('user_email', ''),
                    'payment_method': 'stripe',
                    'source': intent.metadata.get('source', 'website')  # Сохраняем источник
                }
            )
            
            if not created:
                donation.status = 'completed'
                donation.save()
            
            # Отправляем email благодарности
            try:
                send_donation_thank_you_email(donation)
                logger.info(f"Thank you email sent for donation {donation.id}")
            except Exception as e:
                logger.error(f"Failed to send thank you email for donation {donation.id}: {str(e)}")
            
            return JsonResponse({
                'success': True,
                'message': _('Payment confirmed successfully')
            })
        else:
            return JsonResponse({
                'success': False,
                'message': _('Payment not completed')
            }, status=400)
            
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Payment confirmation error')
        }, status=400)
    except Exception as e:
        logger.error(f"Payment confirmation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('An error occurred')
        }, status=500)


def test_stripe(request):
    """Тестовая страница для проверки Stripe"""
    return render(request, 'donation/test_stripe.html', {
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    })


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """Webhook для обработки событий Stripe"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    
    if not endpoint_secret:
        logger.warning("Stripe webhook secret not configured")
        return JsonResponse({'status': 'error', 'message': 'Webhook not configured'}, status=400)
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        logger.error("Invalid payload in webhook")
        return JsonResponse({'status': 'error', 'message': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in webhook")
        return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=400)
    
    # Обработка различных типов событий
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        logger.info(f"Webhook: Payment succeeded for {payment_intent['id']}")
        
        try:
            # Конвертируем сумму в зависимости от валюты
            if payment_intent['currency'] == 'rub':
                amount = payment_intent['amount']
            else:
                amount = payment_intent['amount'] / 100
            
            # Обновляем или создаем donation
            donation, created = Donation.objects.get_or_create(
                stripe_payment_intent_id=payment_intent['id'],
                defaults={
                    'amount': amount,
                    'currency': payment_intent['currency'],
                    'status': 'completed',
                    'name': payment_intent['metadata'].get('user_name', 'Anonymous'),
                    'email': payment_intent['metadata'].get('user_email', ''),
                    'payment_method': 'stripe',
                    'source': payment_intent['metadata'].get('source', 'website')  # Сохраняем источник
                }
            )
            
            if not created and donation.status != 'completed':
                donation.status = 'completed'
                donation.save()
                logger.info(f"Donation {donation.id} updated to completed via webhook")
                
                # Отправляем email благодарности
                try:
                    send_donation_thank_you_email(donation)
                    logger.info(f"Thank you email sent for donation {donation.id} via webhook")
                except Exception as e:
                    logger.error(f"Failed to send thank you email for donation {donation.id} via webhook: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error processing webhook payment_intent.succeeded: {str(e)}")
            
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        logger.info(f"Webhook: Payment failed for {payment_intent['id']}")
        
        try:
            donation = Donation.objects.filter(
                stripe_payment_intent_id=payment_intent['id']
            ).first()
            
            if donation and donation.status != 'failed':
                donation.status = 'failed'
                donation.save()
                logger.info(f"Donation {donation.id} marked as failed via webhook")
                
        except Exception as e:
            logger.error(f"Error processing webhook payment_intent.payment_failed: {str(e)}")
            
    elif event['type'] == 'payment_intent.canceled':
        payment_intent = event['data']['object']
        logger.info(f"Webhook: Payment canceled for {payment_intent['id']}")
        
        try:
            donation = Donation.objects.filter(
                stripe_payment_intent_id=payment_intent['id']
            ).first()
            
            if donation and donation.status not in ['completed', 'cancelled']:
                donation.status = 'cancelled'
                donation.save()
                logger.info(f"Donation {donation.id} marked as cancelled via webhook")
                
        except Exception as e:
            logger.error(f"Error processing webhook payment_intent.canceled: {str(e)}")
    
    else:
        logger.info(f"Webhook: Unhandled event type {event['type']}")
    
    return JsonResponse({'status': 'success'})


@require_http_methods(["GET"])
def get_stripe_publishable_key(request):
    """Получение публичного ключа Stripe для фронтенда"""
    try:
        publishable_key = settings.STRIPE_PUBLISHABLE_KEY
        if not publishable_key or publishable_key.startswith('pk_test_51234'):
            logger.warning("Stripe publishable key not configured properly")
            return JsonResponse({
                'success': False,
                'message': 'Stripe not configured'
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'publishable_key': publishable_key
        })
        
    except Exception as e:
        logger.error(f"Error getting Stripe publishable key: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error getting Stripe key'
        }, status=500)


# ==================== Крипто-платежи (CoinGate) ====================

@swagger_auto_schema(
    method='get',
    operation_description="Получение списка поддерживаемых криптовалют (стейблкоинов) для донатов",
    responses={
        200: openapi.Response(
            description="Список криптовалют",
            examples={
                'application/json': {
                    'success': True,
                    'currencies': [
                        {'code': 'USDT', 'name': 'USDT (Tether)'},
                        {'code': 'USDC', 'name': 'USDC (USD Coin)'},
                        {'code': 'BUSD', 'name': 'BUSD (Binance USD)'},
                        {'code': 'DAI', 'name': 'DAI'}
                    ]
                }
            }
        ),
        500: openapi.Response(description="Ошибка сервера")
    }
)
@api_view(['GET'])
def get_crypto_currencies(request):
    """
    Получение списка поддерживаемых криптовалют (стейблкоинов)
    """
    try:
        from .coingate_service import CoinGateService
        
        service = CoinGateService()
        currencies = service.get_available_currencies()
        
        return JsonResponse({
            'success': True,
            'currencies': currencies
        })
        
    except Exception as e:
        logger.error(f"Error getting crypto currencies: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error getting crypto currencies'
        }, status=500)


@swagger_auto_schema(
    method='post',
    operation_description="Создание крипто-платежа через CoinGate",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['amount', 'name'],
        properties={
            'amount': openapi.Schema(type=openapi.TYPE_NUMBER, description='Сумма доната в USD (минимум $1)'),
            'crypto_currency': openapi.Schema(type=openapi.TYPE_STRING, description='Криптовалюта (USDT, USDC, BUSD, DAI)', default='USDT'),
            'name': openapi.Schema(type=openapi.TYPE_STRING, description='Имя донатера'),
            'email': openapi.Schema(type=openapi.TYPE_STRING, description='Email для уведомлений (опционально)'),
            'source': openapi.Schema(type=openapi.TYPE_STRING, description='Источник (website или mini_app)', default='website'),
        },
    ),
    responses={
        200: openapi.Response(
            description="Платеж создан успешно",
            examples={
                'application/json': {
                    'success': True,
                    'order_id': '12345',
                    'payment_address': '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb',
                    'crypto_amount': '10.5',
                    'crypto_currency': 'USDT',
                    'amount_usd': '10.00',
                    'payment_url': 'https://coingate.com/pay/...',
                    'expire_at': '2024-01-01T12:00:00Z',
                    'donation_id': 123
                }
            }
        ),
        400: openapi.Response(description="Ошибка валидации данных"),
        500: openapi.Response(description="Ошибка сервера")
    }
)
@api_view(['POST'])
@csrf_exempt
def create_crypto_payment(request):
    """
    Создание крипто-платежа через CoinGate
    """
    logger.info(f"Create crypto payment request received: {request.body}")
    try:
        from .coingate_service import CoinGateService
        
        data = json.loads(request.body)
        amount = data.get('amount')
        crypto_currency = data.get('crypto_currency', 'USDT')
        email = data.get('email', '')
        name = data.get('name', 'Anonymous')
        source = data.get('source', 'website')
        
        logger.info(f"Crypto payment data: amount={amount}, currency={crypto_currency}, email={email}, name={name}, source={source}")
        
        # Валидация данных
        if not amount or float(amount) < 1:
            return JsonResponse({
                'success': False,
                'message': _('Invalid amount. Minimum amount is $1.00')
            }, status=400)
        
        if not name or not name.strip():
            return JsonResponse({
                'success': False,
                'message': _('Name is required')
            }, status=400)
        
        # Создаем запись в БД со статусом pending
        donation = Donation.objects.create(
            name=name,
            email=email,
            amount=amount,
            currency='usd',  # Цена всегда в USD
            payment_type='crypto',
            crypto_currency=crypto_currency.upper(),
            status='pending',
            payment_method='coingate',
            source=source
        )
        
        # Генерируем уникальный order_id
        order_id = f"donation_{donation.id}_{int(donation.created_at.timestamp())}"
        
        # Формируем URLs для callback
        if request.is_secure():
            protocol = 'https'
        else:
            protocol = 'http'
        
        host = request.get_host()
        callback_url = f"{protocol}://{host}/donation/crypto/callback/"
        cancel_url = f"{protocol}://{host}/donation/"
        success_url = f"{protocol}://{host}/donation/?payment=success"
        
        # Создаем заказ в CoinGate
        service = CoinGateService()
        result = service.create_order(
            amount_usd=amount,
            crypto_currency=crypto_currency,
            order_id=order_id,
            callback_url=callback_url,
            cancel_url=cancel_url,
            success_url=success_url,
            title=f"Donation from {name}",
            description=f"Donation #{donation.id}"
        )
        
        if not result.get('success'):
            # Удаляем donation при ошибке
            donation.delete()
            return JsonResponse({
                'success': False,
                'message': result.get('error', 'Failed to create payment')
            }, status=400)
        
        # Обновляем donation данными от CoinGate
        donation.coingate_order_id = result.get('order_id')
        donation.crypto_payment_address = result.get('payment_address')
        donation.crypto_amount = result.get('pay_amount')
        donation.coingate_status = result.get('status')
        donation.save()
        
        logger.info(f"Crypto payment created successfully: {donation.coingate_order_id}")
        
        return JsonResponse({
            'success': True,
            'order_id': donation.coingate_order_id,
            'payment_address': donation.crypto_payment_address,
            'crypto_amount': str(donation.crypto_amount),
            'crypto_currency': donation.crypto_currency,
            'amount_usd': str(donation.amount),
            'payment_url': result.get('payment_url'),
            'expire_at': result.get('expire_at'),
            'donation_id': donation.id
        })
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({
            'success': False,
            'message': _('Invalid request format')
        }, status=400)
        
    except Exception as e:
        logger.error(f"Unexpected error creating crypto payment: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('An unexpected error occurred. Please try again.')
        }, status=500)


@swagger_auto_schema(
    method='get',
    operation_description="Получение статуса крипто-платежа по ID заказа CoinGate",
    manual_parameters=[
        openapi.Parameter(
            'order_id',
            openapi.IN_PATH,
            description="ID заказа CoinGate",
            type=openapi.TYPE_STRING,
            required=True
        ),
    ],
    responses={
        200: openapi.Response(
            description="Статус платежа",
            examples={
                'application/json': {
                    'success': True,
                    'order_id': '12345',
                    'status': 'completed',
                    'coingate_status': 'paid',
                    'payment_address': '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb',
                    'crypto_amount': '10.5',
                    'crypto_currency': 'USDT'
                }
            }
        ),
        404: openapi.Response(description="Платеж не найден"),
        500: openapi.Response(description="Ошибка сервера")
    }
)
@api_view(['GET'])
def get_crypto_payment_status(request, order_id):
    """
    Получение статуса крипто-платежа
    """
    try:
        from .coingate_service import CoinGateService
        
        logger.info(f"Getting crypto payment status for order: {order_id}")
        
        # Находим donation по coingate_order_id
        try:
            donation = Donation.objects.get(coingate_order_id=order_id)
        except Donation.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Payment not found'
            }, status=404)
        
        # Получаем актуальный статус от CoinGate
        service = CoinGateService()
        result = service.get_order(order_id)
        
        if not result.get('success'):
            return JsonResponse({
                'success': False,
                'message': result.get('error', 'Failed to get payment status')
            }, status=400)
        
        # Обновляем статус в БД
        coingate_status = result.get('status')
        donation.coingate_status = coingate_status
        
        # Маппинг статусов CoinGate на наши статусы
        if coingate_status == 'paid':
            donation.status = 'completed'
            # Отправляем email благодарности
            try:
                send_donation_thank_you_email(donation)
                logger.info(f"Thank you email sent for donation {donation.id}")
            except Exception as e:
                logger.error(f"Failed to send thank you email: {str(e)}")
        elif coingate_status in ['invalid', 'expired', 'canceled']:
            donation.status = 'failed'
        elif coingate_status in ['pending', 'confirming']:
            donation.status = 'pending'
        
        donation.save()
        
        logger.info(f"Crypto payment status updated: {order_id} -> {donation.status}")
        
        return JsonResponse({
            'success': True,
            'order_id': order_id,
            'status': donation.status,
            'coingate_status': coingate_status,
            'payment_address': donation.crypto_payment_address,
            'crypto_amount': str(donation.crypto_amount) if donation.crypto_amount else None,
            'crypto_currency': donation.crypto_currency
        })
        
    except Exception as e:
        logger.error(f"Error getting crypto payment status: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error getting payment status'
        }, status=500)


@swagger_auto_schema(
    method='post',
    operation_description="Webhook callback от CoinGate для обновления статуса платежа (только для CoinGate сервера)",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_STRING, description='ID заказа'),
            'status': openapi.Schema(type=openapi.TYPE_STRING, description='Статус: new, pending, confirming, paid, invalid, expired, canceled'),
            'token': openapi.Schema(type=openapi.TYPE_STRING, description='Токен для верификации'),
        },
    ),
    responses={
        200: openapi.Response(
            description="Callback обработан успешно",
            examples={'application/json': {'status': 'success'}}
        ),
        400: openapi.Response(description="Некорректные данные"),
        404: openapi.Response(description="Платеж не найден"),
        500: openapi.Response(description="Ошибка сервера")
    }
)
@api_view(['POST'])
@csrf_exempt
def coingate_callback(request):
    """
    Webhook callback от CoinGate для обновления статуса платежа
    """
    logger.info(f"CoinGate callback received: {request.body}")
    try:
        from .coingate_service import CoinGateService
        
        # CoinGate отправляет данные в POST параметрах
        order_id = request.POST.get('id') or request.GET.get('id')
        status = request.POST.get('status') or request.GET.get('status')
        token = request.POST.get('token') or request.GET.get('token')
        
        if not order_id:
            logger.error("No order_id in callback")
            return JsonResponse({'status': 'error', 'message': 'No order_id'}, status=400)
        
        logger.info(f"CoinGate callback: order={order_id}, status={status}")
        
        # Находим donation
        try:
            donation = Donation.objects.get(coingate_order_id=order_id)
        except Donation.DoesNotExist:
            logger.error(f"Donation not found for order_id: {order_id}")
            return JsonResponse({'status': 'error', 'message': 'Donation not found'}, status=404)
        
        # Верификация callback (опционально, для дополнительной безопасности)
        # service = CoinGateService()
        # if not service.verify_callback(order_id, token):
        #     logger.error(f"Invalid callback token for order: {order_id}")
        #     return JsonResponse({'status': 'error', 'message': 'Invalid token'}, status=403)
        
        # Обновляем статус
        old_status = donation.status
        donation.coingate_status = status
        
        # Маппинг статусов
        if status == 'paid':
            donation.status = 'completed'
            # Отправляем email благодарности
            try:
                send_donation_thank_you_email(donation)
                logger.info(f"Thank you email sent for donation {donation.id}")
            except Exception as e:
                logger.error(f"Failed to send thank you email: {str(e)}")
        elif status in ['invalid', 'expired', 'canceled']:
            donation.status = 'failed'
        elif status in ['pending', 'confirming']:
            donation.status = 'pending'
        
        donation.save()
        
        logger.info(f"Donation {donation.id} status updated: {old_status} -> {donation.status}")
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error processing CoinGate callback: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
 